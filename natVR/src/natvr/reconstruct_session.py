from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, TypeVar

from natvr.kafka_transport import list_broker_topics as _list_broker_topics
from natvr.emg_consumer import (
    EmgFrameEnvelope,
    EmgKafkaConsumer,
    MarkerEventEnvelope,
    SessionMetadataEnvelope,
    StreamKafkaConsumer,
    decode_emg_message,
    decode_marker_message,
    decode_session_metadata_message,
)
from natvr.markers import write_marker_jsonl
from natvr.models import MarkerEventV1, SessionMetadataRecord
from natvr.recording import (
    ParquetSessionRecorder,
    SessionMetadata,
    load_extra_metadata,
)
from natvr.topics import marker_stream, meta_session

T = TypeVar("T")
META_TOPIC_SUFFIX = "-Json-MetaRecord"
MARKER_TOPIC_SUFFIX = "-Json-MarkerEventV1"
# record_type_id of a SessionMetadataRecord on a `-Json-MetaRecord` topic. Other
# MetaRecord kinds (e.g. TransformProvenanceRecord == 2) share the same topic
# suffix; discovery must skip them rather than fail to decode.
_SESSION_METADATA_RECORD_TYPE_ID = 1
EMG_TOPIC_SUFFIXES = (
    "-Json-ExgPillEmgDataSchemaV1",
)


@dataclass(frozen=True, slots=True)
class DiscoveredRun:
    session_id: str
    run_index: int
    start_us: int
    end_us: int | None
    device_ids: tuple[str, ...]
    purpose: str
    participant_id: str
    protocol_id: str
    tags: tuple[str, ...]
    notes: str
    marker_count: int
    last_activity_us: int
    selected_record: SessionMetadataRecord | None = None


@dataclass(frozen=True, slots=True)
class ReconstructedRunArtifacts:
    session_id: str
    run_index: int
    device_id: str
    output_path: Path
    marker_path: Path
    metadata_path: Path
    frame_count: int
    marker_count: int


def build_reconstruction_stem(
    session_id: str,
    device_id: str,
    *,
    run_index: int | None = None,
    include_run_index: bool = False,
) -> str:
    stem = f"{session_id}__{device_id}"
    if include_run_index and run_index is not None:
        stem = f"{stem}__run-{run_index:02d}"
    return stem


def build_marker_output_path(
    output_dir: Path,
    session_id: str,
    device_id: str,
    *,
    run_index: int | None = None,
    include_run_index: bool = False,
) -> Path:
    stem = build_reconstruction_stem(
        session_id,
        device_id,
        run_index=run_index,
        include_run_index=include_run_index,
    )
    return output_dir / f"{stem}.markers.jsonl"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reconstruct one historical EMG training session from Kafka into "
            "Parquet plus marker JSONL."
        )
    )
    parser.add_argument("--broker", default="127.0.0.1:29092")
    parser.add_argument(
        "--session-id",
        help="Session to reconstruct. When omitted on a TTY, prompt from broker-discovered sessions.",
    )
    parser.add_argument(
        "--device-id",
        help="Device to reconstruct. When omitted, use session metadata or prompt on a TTY.",
    )
    parser.add_argument(
        "--run-index",
        type=int,
        help=(
            "1-based recorded-run index inside the selected session_id. "
            "Useful when one session topic contains multiple captures."
        ),
    )
    parser.add_argument("--input-topic")
    parser.add_argument("--marker-topic")
    parser.add_argument("--meta-topic")
    parser.add_argument("--output-dir", default="captures/reconstructed")
    parser.add_argument("--group-id", default="natvr-emg-reconstruct")
    parser.add_argument(
        "--idle-timeout-s",
        type=float,
        default=2.0,
        help=(
            "Stop polling a historical topic after this many idle seconds. "
            "Used for marker, meta, and EMG scans."
        ),
    )
    parser.add_argument(
        "--no-direct-assign",
        action="store_true",
        help="Use normal consumer-group subscription instead of direct partition assignment.",
    )
    parser.add_argument("--partition", type=int, default=0)
    parser.add_argument("--metadata-json")
    parser.add_argument("--allow-missing-session-end", action="store_true")
    parser.add_argument(
        "--post-roll-us",
        type=int,
        default=1_000_000,
        help=(
            "When scanning a live device topic, stop once enough frames have "
            "arrived past session_end_us + post_roll_us."
        ),
    )
    return parser.parse_args(argv)


def drain_historical(
    poll,
    *,
    idle_timeout_s: float,
) -> list[object]:
    items: list[object] = []
    idle_polls = max(1, int(idle_timeout_s / 0.25))
    idle_count = 0
    while True:
        item = poll(timeout=0.25)
        if item is None:
            idle_count += 1
            if idle_count >= idle_polls:
                break
            continue
        idle_count = 0
        items.append(item)
    return items


def list_broker_topics(*, bootstrap_servers: str) -> list[str]:
    return _list_broker_topics(bootstrap_servers=bootstrap_servers)


def format_timestamp_us(timestamp_us: int) -> str:
    if timestamp_us <= 0:
        return "-"
    instant = datetime.fromtimestamp(timestamp_us / 1_000_000.0, tz=timezone.utc)
    return instant.strftime("%Y-%m-%d %H:%M:%SZ")


def prompt_select(name: str, options: list[T], *, render: Callable[[T], str]) -> T:
    if not options:
        raise RuntimeError(f"no {name} options available")

    print(f"Available {name}s:")
    for index, option in enumerate(options, start=1):
        print(f"  {index}. {render(option)}")

    while True:
        raw = input(f"Select {name} [1-{len(options)}]: ").strip()
        if not raw:
            continue
        try:
            choice = int(raw)
        except ValueError:
            print(f"Enter a number between 1 and {len(options)}.")
            continue
        if 1 <= choice <= len(options):
            return options[choice - 1]
        print(f"Enter a number between 1 and {len(options)}.")


def prompt_text(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value


def truncate_text(value: str, *, limit: int = 48) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3]}..."


def _marker_attr_text(marker: MarkerEventV1 | None, key: str) -> str:
    if marker is None:
        return ""
    raw = marker.attributes.get(key)
    return str(raw).strip() if raw is not None else ""


def _marker_attr_tuple(marker: MarkerEventV1 | None, key: str) -> tuple[str, ...]:
    if marker is None:
        return ()
    raw = marker.attributes.get(key)
    if raw is None:
        return ()
    if isinstance(raw, (list, tuple)):
        return tuple(str(item) for item in raw if str(item))
    raw_text = str(raw).strip()
    return (raw_text,) if raw_text else ()


def _decode_session_metadata_or_skip(payload: bytes, **kwargs: object):
    # discover_runs points this at EVERY `-Json-MetaRecord` topic, but transform
    # nodes publish TransformProvenanceRecords (record_type_id 2) on such topics
    # too. Peek at the record type and skip anything that isn't session metadata,
    # so one provenance record doesn't abort the whole discovery scan.
    try:
        header = json.loads(payload)
    except (ValueError, TypeError):
        return None
    if (
        not isinstance(header, dict)
        or header.get("record_type_id") != _SESSION_METADATA_RECORD_TYPE_ID
    ):
        return None
    return decode_session_metadata_message(payload, **kwargs)


def load_stream_history(
    args: argparse.Namespace,
    *,
    marker_topics: list[str],
    meta_topics: list[str],
) -> tuple[list[MarkerEventV1], list[SessionMetadataRecord]]:
    marker_envelopes: list[object] = []
    meta_envelopes: list[object] = []

    if marker_topics:
        marker_consumer = StreamKafkaConsumer(
            bootstrap_servers=args.broker,
            group_id=f"{args.group_id}-discover-marker",
            topics=marker_topics,
            decoders={topic: decode_marker_message for topic in marker_topics},
            auto_offset_reset="earliest",
            direct_assign=args.direct_assign,
            partition=args.partition,
        )
        try:
            marker_envelopes = drain_historical(
                marker_consumer.poll,
                idle_timeout_s=args.idle_timeout_s,
            )
        finally:
            marker_consumer.close()

    if meta_topics:
        meta_consumer = StreamKafkaConsumer(
            bootstrap_servers=args.broker,
            group_id=f"{args.group_id}-discover-meta",
            topics=meta_topics,
            decoders={topic: _decode_session_metadata_or_skip for topic in meta_topics},
            auto_offset_reset="earliest",
            direct_assign=args.direct_assign,
            partition=args.partition,
        )
        try:
            meta_envelopes = drain_historical(
                meta_consumer.poll,
                idle_timeout_s=args.idle_timeout_s,
            )
        finally:
            meta_consumer.close()

    markers = [
        envelope.marker
        for envelope in marker_envelopes
        if isinstance(envelope, MarkerEventEnvelope)
    ]
    records = [
        envelope.record
        for envelope in meta_envelopes
        if isinstance(envelope, SessionMetadataEnvelope)
    ]
    return markers, records


def choose_run_metadata_record(
    records: list[SessionMetadataRecord],
    *,
    start_us: int,
    end_us: int | None,
    last_activity_us: int,
) -> SessionMetadataRecord | None:
    if not records:
        return None

    window_end_us = end_us if end_us is not None else last_activity_us
    exact_start = [record for record in records if record.created_at_us == start_us]
    if exact_start:
        exact_covering = [
            record
            for record in exact_start
            if max(record.updated_at_us, record.created_at_us) >= window_end_us
        ]
        if exact_covering:
            exact_covering.sort(
                key=lambda record: (record.updated_at_us, record.created_at_us)
            )
            return exact_covering[-1]
        exact_start.sort(key=lambda record: (record.updated_at_us, record.created_at_us))
        return exact_start[-1]

    covering = [
        record
        for record in records
        if record.created_at_us <= start_us
        and max(record.updated_at_us, record.created_at_us) >= window_end_us
    ]
    if covering:
        covering.sort(key=lambda record: (record.updated_at_us, record.created_at_us))
        return covering[-1]

    preceding = [record for record in records if record.created_at_us <= start_us]
    if preceding:
        preceding.sort(key=lambda record: (record.created_at_us, record.updated_at_us))
        return preceding[-1]

    records.sort(key=lambda record: (record.updated_at_us, record.created_at_us))
    return records[-1]


def build_discovered_run(
    *,
    session_id: str,
    run_index: int,
    start_us: int,
    end_us: int | None,
    last_activity_us: int,
    marker_count: int,
    selected_record: SessionMetadataRecord | None,
    start_marker: MarkerEventV1 | None,
) -> DiscoveredRun:
    purpose = (
        selected_record.purpose
        or _marker_attr_text(start_marker, "purpose")
        or "training"
    )
    participant_id = selected_record.participant_id or _marker_attr_text(
        start_marker,
        "participant_id",
    )
    protocol_id = selected_record.protocol_id or _marker_attr_text(
        start_marker,
        "protocol_id",
    )
    device_ids = tuple(selected_record.device_ids) if selected_record else ()
    if not device_ids:
        device_ids = _marker_attr_tuple(start_marker, "device_ids")
    tags = tuple(selected_record.tags) if selected_record else ()
    if not tags:
        tags = _marker_attr_tuple(start_marker, "tags")
    notes = (
        selected_record.notes
        if selected_record and selected_record.notes
        else _marker_attr_text(start_marker, "notes")
    )
    return DiscoveredRun(
        session_id=session_id,
        run_index=run_index,
        start_us=start_us,
        end_us=end_us,
        device_ids=device_ids,
        purpose=purpose,
        participant_id=participant_id,
        protocol_id=protocol_id,
        tags=tags,
        notes=notes,
        marker_count=marker_count,
        last_activity_us=last_activity_us,
        selected_record=selected_record,
    )


def build_runs_from_metadata_records(
    session_id: str,
    records: list[SessionMetadataRecord],
) -> list[DiscoveredRun]:
    if not records:
        return []

    grouped: dict[int, list[SessionMetadataRecord]] = {}
    for record in records:
        grouped.setdefault(int(record.created_at_us), []).append(record)

    runs: list[DiscoveredRun] = []
    for start_us in sorted(grouped):
        matching = grouped[start_us]
        matching.sort(key=lambda record: (record.updated_at_us, record.created_at_us))
        selected_record = matching[-1]
        end_us = max(selected_record.updated_at_us, selected_record.created_at_us)
        runs.append(
            build_discovered_run(
                session_id=session_id,
                run_index=len(runs) + 1,
                start_us=start_us,
                end_us=end_us,
                last_activity_us=end_us,
                marker_count=0,
                selected_record=selected_record,
                start_marker=None,
            )
        )
    return runs


def record_matches_run_window(
    record: SessionMetadataRecord,
    run: DiscoveredRun,
) -> bool:
    run_end_us = run.end_us if run.end_us is not None else run.last_activity_us
    record_end_us = max(record.updated_at_us, record.created_at_us)
    return (
        run.start_us <= record.created_at_us <= run_end_us
        and run.start_us <= record_end_us <= run_end_us
    )


def build_runs_for_session(
    session_id: str,
    markers: list[MarkerEventV1],
    records: list[SessionMetadataRecord],
) -> list[DiscoveredRun]:
    session_markers = sorted(
        (marker for marker in markers if marker.session_id == session_id),
        key=lambda marker: marker.emitted_at_us,
    )
    if not session_markers:
        return build_runs_from_metadata_records(session_id, records)

    lifecycle_markers = [
        marker
        for marker in session_markers
        if marker.marker_type == "session" and marker.event in {"start", "end"}
    ]
    if not lifecycle_markers:
        start_us = session_markers[0].emitted_at_us
        end_us = session_markers[-1].emitted_at_us
        selected_record = choose_run_metadata_record(
            list(records),
            start_us=start_us,
            end_us=end_us,
            last_activity_us=end_us,
        )
        runs = [
            build_discovered_run(
                session_id=session_id,
                run_index=1,
                start_us=start_us,
                end_us=end_us,
                last_activity_us=end_us,
                marker_count=len(session_markers),
                selected_record=selected_record,
                start_marker=None,
            )
        ]
        uncovered_records = [
            record
            for record in records
            if not any(record_matches_run_window(record, run) for run in runs)
        ]
        runs.extend(build_runs_from_metadata_records(session_id, uncovered_records))
        runs.sort(key=lambda run: (run.start_us, run.last_activity_us, run.end_us or 0))
        return [
            DiscoveredRun(
                session_id=run.session_id,
                run_index=index,
                start_us=run.start_us,
                end_us=run.end_us,
                device_ids=run.device_ids,
                purpose=run.purpose,
                participant_id=run.participant_id,
                protocol_id=run.protocol_id,
                tags=run.tags,
                notes=run.notes,
                marker_count=run.marker_count,
                last_activity_us=run.last_activity_us,
                selected_record=run.selected_record,
            )
            for index, run in enumerate(runs, start=1)
        ]

    runs: list[DiscoveredRun] = []
    open_start: MarkerEventV1 | None = None
    for marker in lifecycle_markers:
        if marker.event == "start":
            open_start = marker
            continue
        if open_start is None:
            continue
        start_us = open_start.emitted_at_us
        end_us = marker.emitted_at_us
        run_markers = filter_markers_to_window(
            session_markers,
            start_us=start_us,
            end_us=end_us,
        )
        selected_record = choose_run_metadata_record(
            list(records),
            start_us=start_us,
            end_us=end_us,
            last_activity_us=end_us,
        )
        runs.append(
            build_discovered_run(
                session_id=session_id,
                run_index=len(runs) + 1,
                start_us=start_us,
                end_us=end_us,
                last_activity_us=end_us,
                marker_count=len(run_markers),
                selected_record=selected_record,
                start_marker=open_start,
            )
        )
        open_start = None

    if open_start is not None:
        start_us = open_start.emitted_at_us
        run_markers = [marker for marker in session_markers if marker.emitted_at_us >= start_us]
        last_activity_us = max(marker.emitted_at_us for marker in run_markers)
        selected_record = choose_run_metadata_record(
            list(records),
            start_us=start_us,
            end_us=None,
            last_activity_us=last_activity_us,
        )
        runs.append(
            build_discovered_run(
                session_id=session_id,
                run_index=len(runs) + 1,
                start_us=start_us,
                end_us=None,
                last_activity_us=last_activity_us,
                marker_count=len(run_markers),
                selected_record=selected_record,
                start_marker=open_start,
            )
        )

    uncovered_records = [
        record
        for record in records
        if not any(record_matches_run_window(record, run) for run in runs)
    ]
    runs.extend(build_runs_from_metadata_records(session_id, uncovered_records))
    runs.sort(key=lambda run: (run.start_us, run.last_activity_us, run.end_us or 0))

    normalized_runs: list[DiscoveredRun] = []
    for index, run in enumerate(runs, start=1):
        normalized_runs.append(
            DiscoveredRun(
                session_id=run.session_id,
                run_index=index,
                start_us=run.start_us,
                end_us=run.end_us,
                device_ids=run.device_ids,
                purpose=run.purpose,
                participant_id=run.participant_id,
                protocol_id=run.protocol_id,
                tags=run.tags,
                notes=run.notes,
                marker_count=run.marker_count,
                last_activity_us=run.last_activity_us,
                selected_record=run.selected_record,
            )
        )

    return normalized_runs


def discover_runs(args: argparse.Namespace) -> list[DiscoveredRun]:
    topics = list_broker_topics(bootstrap_servers=args.broker)
    marker_topics = [topic for topic in topics if topic.endswith(MARKER_TOPIC_SUFFIX)]
    meta_topics = [topic for topic in topics if topic.endswith(META_TOPIC_SUFFIX)]

    markers, records = load_stream_history(
        args,
        marker_topics=marker_topics,
        meta_topics=meta_topics,
    )
    runs: list[DiscoveredRun] = []
    session_ids = sorted(
        {marker.session_id for marker in markers}
        | {record.session_id for record in records}
    )
    for session_id in session_ids:
        session_records = [record for record in records if record.session_id == session_id]
        runs.extend(build_runs_for_session(session_id, markers, session_records))
    runs.sort(key=lambda run: (-run.last_activity_us, run.session_id, -run.run_index))
    return runs


def render_run_choice(run: DiscoveredRun) -> str:
    devices = ", ".join(run.device_ids) if run.device_ids else "unknown"
    end_label = format_timestamp_us(run.end_us) if run.end_us is not None else "open"
    details = [
        f"{run.session_id}",
        f"run={run.run_index}",
        f"{format_timestamp_us(run.start_us)} -> {end_label}",
        f"devices=[{devices}]",
        f"markers={run.marker_count}",
    ]
    if run.participant_id:
        details.append(f"participant={run.participant_id}")
    if run.protocol_id:
        details.append(f"protocol={run.protocol_id}")
    if run.tags:
        details.append(f"tags={','.join(run.tags)}")
    if run.notes:
        details.append(f"notes={truncate_text(run.notes)}")
    return "  ".join(details)


def find_matching_run(
    runs: list[DiscoveredRun],
    *,
    session_id: str,
    run_index: int,
    start_us: int,
) -> DiscoveredRun | None:
    for run in runs:
        if (
            run.session_id == session_id
            and run.run_index == run_index
            and run.start_us == start_us
        ):
            return run
    return None


def resolve_discovered_run(args: argparse.Namespace) -> DiscoveredRun | None:
    if args.session_id:
        return None
    if not sys.stdin.isatty():
        raise RuntimeError("--session-id is required when stdin is not a TTY")

    runs = discover_runs(args)
    if not runs:
        raise RuntimeError(
            "no reconstructable recorded runs were discovered on the broker"
        )
    return prompt_select("recorded run", runs, render=render_run_choice)


def resolve_session_run(
    args: argparse.Namespace,
    runs: list[DiscoveredRun],
    *,
    preselected_run: DiscoveredRun | None = None,
) -> DiscoveredRun:
    if preselected_run is not None:
        matched = find_matching_run(
            runs,
            session_id=preselected_run.session_id,
            run_index=preselected_run.run_index,
            start_us=preselected_run.start_us,
        )
        if matched is None:
            raise RuntimeError("selected recorded run no longer exists in session history")
        return matched

    if args.run_index is not None:
        for run in runs:
            if run.run_index == args.run_index:
                return run
        raise RuntimeError(
            f"run_index={args.run_index} does not exist for session_id={args.session_id}"
        )

    if len(runs) == 1:
        return runs[0]
    if not sys.stdin.isatty():
        raise RuntimeError(
            f"multiple recorded runs were found for session_id={args.session_id}; "
            "rerun with --run-index or use an interactive TTY"
        )
    return prompt_select("recorded run", runs, render=render_run_choice)


def discover_device_ids_for_window(
    args: argparse.Namespace,
    *,
    start_us: int,
    end_us: int,
) -> list[str]:
    topics = [args.input_topic] if args.input_topic else [
        topic
        for topic in list_broker_topics(bootstrap_servers=args.broker)
        if topic.endswith(EMG_TOPIC_SUFFIXES)
    ]
    if not topics:
        return []

    consumer = StreamKafkaConsumer(
        bootstrap_servers=args.broker,
        group_id=f"{args.group_id}-discover-device-{args.session_id}",
        topics=topics,
        decoders={topic: decode_emg_message for topic in topics},
        auto_offset_reset="earliest",
        direct_assign=args.direct_assign,
        partition=args.partition,
    )
    # Stop once we scan past the session window (8 frames beyond end_us), NOT just
    # on idle: the live source publishes continuously, so an idle-only drain would
    # never terminate (it would chase the live tail forever). We only need the
    # device(s) active inside [start_us, end_us].
    device_ids: set[str] = set()
    idle_polls = max(1, int(args.idle_timeout_s / 0.25))
    idle_count = 0
    overrun_streak = 0
    end_streak_required = 8
    try:
        while True:
            item = consumer.poll(timeout=0.25)
            if item is None:
                idle_count += 1
                if idle_count >= idle_polls:
                    break
                continue
            idle_count = 0
            if not isinstance(item, EmgFrameEnvelope):
                continue
            frame_ts_us = int(item.frame.device_ts_us)
            if start_us <= frame_ts_us <= end_us:
                device_ids.add(item.frame.device_id)
            if frame_ts_us > end_us:
                overrun_streak += 1
                if overrun_streak >= end_streak_required:
                    break
            else:
                overrun_streak = 0
    finally:
        consumer.close()

    return sorted(device_ids)


def resolve_run_end_us(
    run: DiscoveredRun,
    *,
    allow_missing_end: bool,
) -> int:
    if run.end_us is not None:
        return run.end_us
    if allow_missing_end:
        return run.last_activity_us
    raise RuntimeError(
        "session end marker is missing for the selected recorded run; rerun with "
        "--allow-missing-session-end to fall back to the last marker timestamp"
    )


def resolve_device_id(
    args: argparse.Namespace,
    *,
    selected_run: DiscoveredRun,
    start_us: int,
    end_us: int,
) -> str:
    if args.device_id:
        return args.device_id

    metadata_device_ids = list(selected_run.device_ids)
    if len(metadata_device_ids) == 1:
        return metadata_device_ids[0]
    if len(metadata_device_ids) > 1:
        if not sys.stdin.isatty():
            raise RuntimeError(
                "--device-id is required when the selected session metadata contains multiple devices"
            )
        return prompt_select("device", metadata_device_ids, render=str)

    discovered_device_ids = discover_device_ids_for_window(
        args,
        start_us=start_us,
        end_us=end_us,
    )
    if len(discovered_device_ids) == 1:
        return discovered_device_ids[0]
    if len(discovered_device_ids) > 1:
        if not sys.stdin.isatty():
            raise RuntimeError(
                "--device-id is required when multiple device IDs are active in the selected session window"
            )
        return prompt_select("device", discovered_device_ids, render=str)
    if not sys.stdin.isatty():
        raise RuntimeError(
            "device_id is required when the session metadata stream does not provide one"
        )
    return prompt_text(
        "No device IDs were discoverable for this session. Enter device id: "
    )


def drain_emg_frames_for_window(
    poll,
    *,
    device_id: str,
    start_us: int,
    end_us: int,
    idle_timeout_s: float,
    post_roll_us: int,
    end_streak_required: int = 8,
) -> list[EmgFrameEnvelope]:
    frames: list[EmgFrameEnvelope] = []
    idle_polls = max(1, int(idle_timeout_s / 0.25))
    idle_count = 0
    overrun_streak = 0
    cutoff_us = end_us + max(0, int(post_roll_us))

    while True:
        item = poll(timeout=0.25)
        if item is None:
            idle_count += 1
            if idle_count >= idle_polls:
                break
            continue

        idle_count = 0
        if item.frame.device_id != device_id:
            continue

        frame_ts_us = int(item.frame.device_ts_us)
        if frame_ts_us >= start_us:
            frames.append(item)

        if frame_ts_us > cutoff_us:
            overrun_streak += 1
            if overrun_streak >= end_streak_required:
                break
        else:
            overrun_streak = 0

    return frames


def choose_session_metadata_record(
    records: Iterable[SessionMetadataRecord],
    *,
    session_id: str,
) -> SessionMetadataRecord | None:
    matching = [record for record in records if record.session_id == session_id]
    if not matching:
        return None
    matching.sort(key=lambda record: (record.updated_at_us, record.created_at_us))
    return matching[-1]


def infer_session_window_us(
    markers: list[MarkerEventV1],
    *,
    allow_missing_end: bool = False,
) -> tuple[int, int]:
    if not markers:
        raise RuntimeError("no marker events found for session")

    session_markers = [marker for marker in markers if marker.marker_type == "session"]
    start_candidates = [
        marker.emitted_at_us for marker in session_markers if marker.event == "start"
    ]
    end_candidates = [
        marker.emitted_at_us for marker in session_markers if marker.event == "end"
    ]

    start_us = min(start_candidates) if start_candidates else min(
        marker.emitted_at_us for marker in markers
    )
    if end_candidates:
        end_us = max(end_candidates)
    elif allow_missing_end:
        end_us = max(marker.emitted_at_us for marker in markers)
    else:
        raise RuntimeError(
            "session end marker is missing; rerun with --allow-missing-session-end "
            "to fall back to the last marker timestamp"
        )

    if end_us < start_us:
        raise RuntimeError("invalid marker timeline: session end precedes start")
    return start_us, end_us


def filter_markers_to_window(
    markers: list[MarkerEventV1],
    *,
    start_us: int,
    end_us: int,
) -> list[MarkerEventV1]:
    return [
        marker
        for marker in sorted(markers, key=lambda item: item.emitted_at_us)
        if start_us <= marker.emitted_at_us <= end_us
    ]


def filter_frames_to_window(
    frames: list[EmgFrameEnvelope],
    *,
    device_id: str,
    start_us: int,
    end_us: int,
) -> list[EmgFrameEnvelope]:
    return [
        frame
        for frame in frames
        if frame.frame.device_id == device_id
        and start_us <= frame.frame.device_ts_us <= end_us
    ]


def build_session_metadata_sidecar(
    *,
    args: argparse.Namespace,
    selected_run: DiscoveredRun,
    device_id: str,
    emg_topic: str,
    marker_topic: str,
    selected_record: SessionMetadataRecord | None,
    marker_count: int,
    frame_count: int,
    start_us: int,
    end_us: int,
) -> SessionMetadata:
    record_extra: dict[str, object] = {}
    if selected_record is not None:
        record_extra = {
            "purpose": selected_record.purpose,
            "participant_id": selected_record.participant_id,
            "protocol_id": selected_record.protocol_id,
            "device_ids": list(selected_record.device_ids),
            "tags": list(selected_record.tags),
            "notes": selected_record.notes,
            "created_at_us": selected_record.created_at_us,
            "updated_at_us": selected_record.updated_at_us,
        }

    extra = load_extra_metadata(args.metadata_json)
    extra.update(
        {
            "reconstructed_from_kafka": True,
            "marker_topic": marker_topic,
            "meta_topic": args.meta_topic or meta_session(args.session_id),
            "session_run_index": selected_run.run_index,
            "marker_count": marker_count,
            "frame_count": frame_count,
            "session_start_us": start_us,
            "session_end_us": end_us,
            "session_duration_s": (end_us - start_us) / 1_000_000.0,
            "session_record": record_extra,
        }
    )

    started_at = datetime.fromtimestamp(start_us / 1_000_000.0, tz=timezone.utc)
    return SessionMetadata(
        session_id=args.session_id,
        device_id=device_id,
        topic=emg_topic,
        subject=selected_record.participant_id if selected_record else None,
        arm=None,
        notes=selected_record.notes if selected_record and selected_record.notes else None,
        date_utc=started_at.isoformat(),
        extra=extra,
    )


def reconstruct_run(
    args: argparse.Namespace,
    selected_run: DiscoveredRun,
    *,
    markers: list[MarkerEventV1] | None = None,
    session_run_count: int = 1,
) -> ReconstructedRunArtifacts:
    if markers is None:
        marker_topic = args.marker_topic or marker_stream(args.session_id)
        meta_topic = args.meta_topic or meta_session(args.session_id)
        loaded_markers, _ = load_stream_history(
            args,
            marker_topics=[marker_topic],
            meta_topics=[meta_topic],
        )
        markers = [marker for marker in loaded_markers if marker.session_id == args.session_id]
    start_us = selected_run.start_us
    end_us = resolve_run_end_us(
        selected_run,
        allow_missing_end=args.allow_missing_session_end,
    )
    selected_markers = filter_markers_to_window(markers, start_us=start_us, end_us=end_us)
    device_id = resolve_device_id(
        args,
        selected_run=selected_run,
        start_us=start_us,
        end_us=end_us,
    )

    emg_consumer = EmgKafkaConsumer(
        bootstrap_servers=args.broker,
        device_id=device_id,
        group_id=f"{args.group_id}-emg-{args.session_id}",
        topic=args.input_topic,
        auto_offset_reset="earliest",
        direct_assign=args.direct_assign,
        partition=args.partition,
    )
    try:
        frame_envelopes = drain_emg_frames_for_window(
            emg_consumer.poll,
            device_id=device_id,
            start_us=start_us,
            end_us=end_us,
            idle_timeout_s=args.idle_timeout_s,
            post_roll_us=args.post_roll_us,
        )
    finally:
        emg_consumer.close()

    selected_frames = filter_frames_to_window(
        [frame for frame in frame_envelopes if isinstance(frame, EmgFrameEnvelope)],
        device_id=device_id,
        start_us=start_us,
        end_us=end_us,
    )
    if not selected_frames:
        raise RuntimeError(
            "no EMG frames found inside the session window; check session_id, "
            "device_id, topic overrides, and broker retention"
        )

    output_dir = Path(args.output_dir)
    include_run_index = session_run_count > 1
    stem = build_reconstruction_stem(
        args.session_id,
        device_id,
        run_index=selected_run.run_index,
        include_run_index=include_run_index,
    )
    output_path = output_dir / f"{stem}.parquet"
    metadata_path = output_dir / f"{stem}.meta.json"
    marker_path = build_marker_output_path(
        output_dir,
        args.session_id,
        device_id,
        run_index=selected_run.run_index,
        include_run_index=include_run_index,
    )
    metadata = build_session_metadata_sidecar(
        args=args,
        selected_run=selected_run,
        device_id=device_id,
        emg_topic=emg_consumer.topic,
        marker_topic=args.marker_topic or marker_stream(args.session_id),
        selected_record=selected_run.selected_record,
        marker_count=len(selected_markers),
        frame_count=len(selected_frames),
        start_us=start_us,
        end_us=end_us,
    )
    recorder = ParquetSessionRecorder(output_path, metadata_path, metadata)
    for frame in selected_frames:
        recorder.append(frame)
    recorder.finalize()
    write_marker_jsonl(marker_path, selected_markers)
    return ReconstructedRunArtifacts(
        session_id=args.session_id,
        run_index=selected_run.run_index,
        device_id=device_id,
        output_path=output_path,
        marker_path=marker_path,
        metadata_path=metadata_path,
        frame_count=len(selected_frames),
        marker_count=len(selected_markers),
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    args.direct_assign = not args.no_direct_assign
    preselected_run = resolve_discovered_run(args)
    if preselected_run is not None:
        args.session_id = preselected_run.session_id
    if not args.session_id:
        raise RuntimeError("--session-id is required")
    marker_topic = args.marker_topic or marker_stream(args.session_id)
    meta_topic = args.meta_topic or meta_session(args.session_id)

    markers, records = load_stream_history(
        args,
        marker_topics=[marker_topic],
        meta_topics=[meta_topic],
    )
    markers = [marker for marker in markers if marker.session_id == args.session_id]
    records = [record for record in records if record.session_id == args.session_id]
    session_runs = build_runs_for_session(args.session_id, markers, records)
    if not session_runs:
        raise RuntimeError(f"no marker events found for session_id={args.session_id}")

    selected_run = resolve_session_run(
        args,
        session_runs,
        preselected_run=preselected_run,
    )
    artifacts = reconstruct_run(
        args,
        selected_run,
        markers=markers,
        session_run_count=len(session_runs),
    )
    print(
        f"Reconstructed {artifacts.frame_count} EMG frames and {artifacts.marker_count} markers "
        f"for session={args.session_id} run={selected_run.run_index} device={artifacts.device_id} into {artifacts.output_path}, "
        f"{artifacts.marker_path}, and {artifacts.metadata_path}"
    )


if __name__ == "__main__":
    main()
