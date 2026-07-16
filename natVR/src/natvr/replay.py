from __future__ import annotations

import argparse
from dataclasses import replace
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Iterator, Literal

from natvr._optional import require_pyarrow
from natvr.kafka_transport import open_producer
from natvr.marker_context import MarkerContextTracker as ReplayMarkerContextTracker
from natvr.markers import load_cue_file_markers, load_marker_jsonl
from natvr.models import ExgPillEmgDataSchemaV1, MarkerEventV1
from natvr.stream_alignment import interleave_timestamped_streams
from natvr.topics import marker_stream


@dataclass(frozen=True, slots=True)
class ReplayFrame:
    frame: ExgPillEmgDataSchemaV1
    topic: str
    sequence_gap: int = 0


@dataclass(frozen=True, slots=True)
class ReplayCueMarker:
    delay_s: float
    marker: MarkerEventV1


@dataclass(frozen=True, slots=True)
class ReplayTimelineEvent:
    kind: Literal["emg", "marker"]
    timestamp_us: int
    frame: ReplayFrame | None = None
    marker: MarkerEventV1 | None = None


def load_replay_frames(parquet_path: Path) -> list[ReplayFrame]:
    _, pq = require_pyarrow()
    table = pq.read_table(parquet_path)
    rows = table.to_pylist()
    frames: list[ReplayFrame] = []
    for row in rows:
        channel_count = int(row["n_channels"])
        frame = ExgPillEmgDataSchemaV1(
            schema_version=str(row["schema_version"]),
            device_id=str(row["device_id"]),
            seq_no=int(row["seq_no"]),
            device_ts_us=int(row["device_ts_us"]),
            sample_rate_hz=int(row["sample_rate_hz"]),
            channel_labels=tuple(str(label) for label in row["channel_labels"]),
            channels=tuple(
                tuple(int(sample) for sample in row[f"channel_{idx}"])
                for idx in range(channel_count)
            ),
        )
        frames.append(
            ReplayFrame(
                frame=frame,
                topic=str(row["topic"]),
                sequence_gap=int(row.get("sequence_gap") or 0),
            )
        )
    return frames


def load_replay_marker_events(
    marker_path: Path,
    *,
    session_id: str | None = None,
) -> list[MarkerEventV1]:
    if marker_path.name.endswith(".cues.json"):
        markers = load_cue_file_markers(marker_path)
        if session_id is None:
            return markers
        return [
            replace(marker, session_id=session_id)
            for marker in markers
        ]
    markers = load_marker_jsonl(marker_path)
    if session_id is None:
        return markers
    return [
        replace(marker, session_id=session_id)
        for marker in markers
    ]


def load_replay_timeline(
    parquet_path: Path,
    *,
    marker_path: Path | None = None,
    session_id: str | None = None,
) -> list[ReplayTimelineEvent]:
    frames = load_replay_frames(parquet_path)
    markers = (
        load_replay_marker_events(marker_path, session_id=session_id)
        if marker_path is not None
        else []
    )
    streams = {
        "emg": [
            {
                "device_ts_us": replay_frame.frame.device_ts_us,
                "payload": replay_frame,
            }
            for replay_frame in frames
        ],
        "marker": [
            {
                "device_ts_us": marker.emitted_at_us,
                "payload": marker,
            }
            for marker in markers
        ],
    }
    merged = interleave_timestamped_streams(streams)
    timeline: list[ReplayTimelineEvent] = []
    for item in merged:
        if item["stream_name"] == "emg":
            replay_frame = item["payload"]
            assert isinstance(replay_frame, ReplayFrame)
            timeline.append(
                ReplayTimelineEvent(
                    kind="emg",
                    timestamp_us=replay_frame.frame.device_ts_us,
                    frame=replay_frame,
                )
            )
        else:
            marker = item["payload"]
            assert isinstance(marker, MarkerEventV1)
            timeline.append(
                ReplayTimelineEvent(
                    kind="marker",
                    timestamp_us=marker.emitted_at_us,
                    marker=marker,
                )
            )
    return timeline


def replay_intervals(frames: list[ReplayFrame], speed: float = 1.0) -> Iterator[float]:
    if speed <= 0:
        raise ValueError("speed must be > 0")
    if len(frames) < 2:
        return iter(())
    return (
        max(0.0, (curr.frame.device_ts_us - prev.frame.device_ts_us) / 1_000_000 / speed)
        for prev, curr in zip(frames, frames[1:])
    )


def load_replay_markers(
    cue_path: Path,
    *,
    session_id: str | None = None,
) -> list[ReplayCueMarker]:
    payload = json.loads(cue_path.read_text(encoding="utf-8"))
    resolved_session_id = session_id or str(payload["session_id"])
    markers: list[ReplayCueMarker] = []
    for event in payload.get("events", []):
        cue_id = int(event["cue_id"])
        phase = str(event["phase"])
        gesture = str(event["gesture"])
        prompt = str(event["prompt"])
        markers.append(
            ReplayCueMarker(
                delay_s=float(event["start_offset_s"]),
                marker=MarkerEventV1(
                    session_id=resolved_session_id,
                    marker_type="cue",
                    marker_id=f"cue:{cue_id}",
                    event="start",
                    label=prompt,
                    emitted_at_us=0,
                    attributes={
                        "cue_id": cue_id,
                        "phase": phase,
                        "gesture": gesture,
                        "prompt": prompt,
                        "rep_index": int(event.get("rep_index", -1)),
                    },
                ),
            )
        )
        markers.append(
            ReplayCueMarker(
                delay_s=float(event["end_offset_s"]),
                marker=MarkerEventV1(
                    session_id=resolved_session_id,
                    marker_type="cue",
                    marker_id=f"cue:{cue_id}",
                    event="end",
                    label=prompt,
                    emitted_at_us=0,
                    attributes={
                        "cue_id": cue_id,
                        "phase": phase,
                        "gesture": gesture,
                        "prompt": prompt,
                        "rep_index": int(event.get("rep_index", -1)),
                    },
                ),
            )
        )
    return sorted(
        markers,
        key=lambda item: (
            item.delay_s,
            0 if item.marker.event == "end" else 1,
        ),
    )


def publish_replay_frames(
    frames: list[ReplayFrame],
    *,
    bootstrap_servers: str,
    topic_override: str | None = None,
    replay_markers: list[ReplayCueMarker] | None = None,
    marker_topic: str | None = None,
    speed: float = 1.0,
    dry_run: bool = False,
) -> int:
    if not frames:
        return 0
    if dry_run:
        return len(frames)
    producer = open_producer(bootstrap_servers)
    first_frame_ts_us = frames[0].frame.device_ts_us
    timeline: list[tuple[float, int, str, bytes]] = []
    for frame in frames:
        delay_s = max(0.0, (frame.frame.device_ts_us - first_frame_ts_us) / 1_000_000 / speed)
        timeline.append(
            (
                delay_s,
                2,
                topic_override or frame.topic,
                frame.frame.to_json_bytes(),
            )
        )
    for replay_marker in replay_markers or []:
        delay_s = max(0.0, replay_marker.delay_s / speed)
        timeline.append(
            (
                delay_s,
                0 if replay_marker.marker.event == "end" else 1,
                marker_topic or marker_stream(replay_marker.marker.session_id),
                b"",
            )
        )
    timeline.sort(key=lambda item: (item[0], item[1]))
    try:
        started = time.monotonic()
        marker_index = 0
        for delay_s, priority, topic_name, payload in timeline:
            sleep_s = delay_s - (time.monotonic() - started)
            if sleep_s > 0:
                time.sleep(sleep_s)
            if priority == 2:
                producer.produce(topic_name, payload)
            else:
                assert replay_markers is not None
                marker = replay_markers[marker_index]
                marker_index += 1
                emitted_at_us = int(
                    datetime.now(tz=timezone.utc).timestamp() * 1_000_000
                )
                producer.produce(
                    topic_name,
                    replace(marker.marker, emitted_at_us=emitted_at_us).to_json_bytes(),
                )
            producer.poll(0)
        producer.flush()
    finally:
        producer.flush()
        close = getattr(producer, "close", None)
        if callable(close):
            close()
    return len(frames)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay recorded EMG frames to Kafka.")
    parser.add_argument("parquet_path")
    parser.add_argument("--broker", default="127.0.0.1:29092")
    parser.add_argument("--topic")
    parser.add_argument("--cue-path")
    parser.add_argument("--marker-topic")
    parser.add_argument("--session-id")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    frames = load_replay_frames(Path(args.parquet_path))
    replay_markers = (
        load_replay_markers(Path(args.cue_path), session_id=args.session_id)
        if args.cue_path
        else None
    )
    count = publish_replay_frames(
        frames,
        bootstrap_servers=args.broker,
        topic_override=args.topic,
        replay_markers=replay_markers,
        marker_topic=args.marker_topic,
        speed=args.speed,
        dry_run=args.dry_run,
    )
    marker_count = len(replay_markers or [])
    print(
        f"Prepared {count} replay frames from {args.parquet_path}"
        + (
            f" and {marker_count} cue markers from {args.cue_path}"
            if replay_markers is not None
            else ""
        )
    )
