from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import signal
import sys
from typing import Any

from natvr._optional import require_pyarrow
from natvr.emg_consumer import EmgFrameEnvelope, EmgKafkaConsumer


@dataclass(slots=True)
class SessionMetadata:
    session_id: str
    device_id: str
    topic: str
    subject: str | None = None
    arm: str | None = None
    electrode_photo_ref: str | None = None
    channel_map: list[str] = field(default_factory=list)
    sensor_serials: list[str] = field(default_factory=list)
    skin_prep_notes: str | None = None
    notes: str | None = None
    date_utc: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["extra"] = dict(self.extra)
        return payload

    def write_json(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")


def frame_to_row(
    envelope: EmgFrameEnvelope,
    annotations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema_version": envelope.frame.schema_version,
        "device_id": envelope.frame.device_id,
        "topic": envelope.topic,
        "partition": envelope.partition,
        "offset": envelope.offset,
        "broker_received_at_us": envelope.broker_received_at_us,
        "seq_no": envelope.frame.seq_no,
        "device_ts_us": envelope.frame.device_ts_us,
        "sample_rate_hz": envelope.frame.sample_rate_hz,
        "n_channels": envelope.frame.n_channels,
        "samples_per_channel": envelope.frame.samples_per_channel,
        "sequence_gap": envelope.sequence_gap,
        "channel_labels": list(envelope.frame.channel_labels),
    }
    for idx, channel in enumerate(envelope.frame.channels):
        row[f"channel_{idx}"] = list(channel)
    if annotations:
        row.update(annotations)
    return row


class ParquetSessionRecorder:
    def __init__(self, output_path: Path, metadata_path: Path, metadata: SessionMetadata):
        self.output_path = output_path
        self.metadata_path = metadata_path
        self.metadata = metadata
        self._rows: list[dict[str, Any]] = []

    def append(
        self,
        envelope: EmgFrameEnvelope,
        annotations: dict[str, Any] | None = None,
    ) -> None:
        if not self.metadata.channel_map:
            self.metadata.channel_map = list(envelope.frame.channel_labels)
        self._rows.append(frame_to_row(envelope, annotations=annotations))

    @property
    def frame_count(self) -> int:
        return len(self._rows)

    def finalize(self) -> None:
        if not self._rows:
            raise RuntimeError("no EMG frames captured; refusing to write empty session")
        pa, pq = require_pyarrow()
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        table = pa.Table.from_pylist(self._rows)
        pq.write_table(table, self.output_path)
        self.metadata.write_json(self.metadata_path)


def build_output_paths(output_dir: Path, session_id: str, device_id: str) -> tuple[Path, Path]:
    stem = f"{session_id}__{device_id}"
    return output_dir / f"{stem}.parquet", output_dir / f"{stem}.meta.json"


def build_cue_path(output_dir: Path, session_id: str, device_id: str) -> Path:
    stem = f"{session_id}__{device_id}"
    return output_dir / f"{stem}.cues.json"


def load_extra_metadata(raw_json: str | None) -> dict[str, Any]:
    if not raw_json:
        return {}
    return json.loads(raw_json)


def add_recording_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--broker", default="127.0.0.1:29092")
    parser.add_argument("--device-id", required=True)
    parser.add_argument(
        "--input-topic",
        help="Optional Kafka topic override for EMG input; defaults to the canonical emg_raw(device_id) topic.",
    )
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--output-dir", default="captures")
    parser.add_argument("--group-id", default="natvr-emg-recorder")
    parser.add_argument("--direct-assign", action="store_true")
    parser.add_argument("--partition", type=int, default=0)
    parser.add_argument("--max-frames", type=int)
    return parser


def add_metadata_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--subject")
    parser.add_argument("--arm")
    parser.add_argument("--electrode-photo-ref")
    parser.add_argument("--sensor-serial", action="append", dest="sensor_serials")
    parser.add_argument("--skin-prep-notes")
    parser.add_argument("--notes")
    parser.add_argument("--date-utc")
    parser.add_argument("--metadata-json")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record EMG frames from Kafka to Parquet.")
    add_recording_args(parser)
    add_metadata_args(parser)
    return parser.parse_args(argv)


def build_session_metadata(args: argparse.Namespace, *, topic: str) -> SessionMetadata:
    return SessionMetadata(
        session_id=args.session_id,
        device_id=args.device_id,
        topic=topic,
        subject=getattr(args, "subject", None),
        arm=getattr(args, "arm", None),
        electrode_photo_ref=getattr(args, "electrode_photo_ref", None),
        sensor_serials=getattr(args, "sensor_serials", None) or [],
        skin_prep_notes=getattr(args, "skin_prep_notes", None),
        notes=getattr(args, "notes", None),
        date_utc=getattr(args, "date_utc", None),
        extra=load_extra_metadata(getattr(args, "metadata_json", None)),
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    output_dir = Path(args.output_dir)
    consumer = EmgKafkaConsumer(
        bootstrap_servers=args.broker,
        device_id=args.device_id,
        group_id=args.group_id,
        topic=getattr(args, "input_topic", None),
        direct_assign=args.direct_assign,
        partition=args.partition,
    )
    output_path, metadata_path = build_output_paths(
        output_dir,
        args.session_id,
        args.device_id,
    )
    metadata = build_session_metadata(args, topic=consumer.topic)
    recorder = ParquetSessionRecorder(output_path, metadata_path, metadata)
    stopping = False

    def handle_stop(_sig: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    previous_int = signal.signal(signal.SIGINT, handle_stop)
    previous_term = signal.signal(signal.SIGTERM, handle_stop)
    try:
        while not stopping:
            envelope = consumer.poll(timeout=1.0)
            if envelope is None:
                continue
            recorder.append(envelope)
            if args.max_frames and recorder.frame_count >= args.max_frames:
                break
        recorder.finalize()
        print(
            f"Recorded {recorder.frame_count} frames to {output_path} with metadata {metadata_path}",
            file=sys.stderr,
        )
    finally:
        signal.signal(signal.SIGINT, previous_int)
        signal.signal(signal.SIGTERM, previous_term)
        consumer.close()
