from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Iterable

from natvr.kafka_transport import open_producer
from natvr.models import MarkerEventV1, SessionMetadataRecord
from natvr.topics import marker_stream, meta_session

__all__ = ["open_producer"]


def utc_now_us() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp() * 1_000_000)


def build_session_metadata_record(
    *,
    session_id: str,
    purpose: str = "training",
    participant_id: str = "",
    protocol_id: str = "",
    device_ids: Iterable[str] = (),
    tags: Iterable[str] = (),
    notes: str = "",
    created_at_us: int | None = None,
    updated_at_us: int | None = None,
) -> SessionMetadataRecord:
    created = int(created_at_us if created_at_us is not None else utc_now_us())
    updated = int(updated_at_us if updated_at_us is not None else created)
    return SessionMetadataRecord(
        session_id=session_id,
        purpose=purpose,
        participant_id=participant_id,
        protocol_id=protocol_id,
        device_ids=tuple(str(device_id) for device_id in device_ids if str(device_id)),
        tags=tuple(str(tag) for tag in tags if str(tag)),
        notes=notes,
        created_at_us=created,
        updated_at_us=updated,
    )


def build_session_lifecycle_marker(
    record: SessionMetadataRecord,
    *,
    event: str,
    emitted_at_us: int | None = None,
) -> MarkerEventV1:
    timestamp_us = int(emitted_at_us if emitted_at_us is not None else utc_now_us())
    if event not in {"start", "end"}:
        raise ValueError("event must be 'start' or 'end'")
    attributes: dict[str, object] = {
        "purpose": record.purpose,
        "participant_id": record.participant_id,
        "protocol_id": record.protocol_id,
    }
    if record.device_ids:
        attributes["device_ids"] = list(record.device_ids)
    if record.tags:
        attributes["tags"] = list(record.tags)
    if record.notes:
        attributes["notes"] = record.notes
    return MarkerEventV1(
        session_id=record.session_id,
        marker_type="session",
        marker_id=f"session:{record.session_id}",
        event=event,
        label=record.purpose or "session",
        emitted_at_us=timestamp_us,
        attributes=attributes,
    )


def publish_session_metadata_record(
    producer: object,
    record: SessionMetadataRecord,
    *,
    topic_name: str | None = None,
) -> str:
    resolved_topic = topic_name or meta_session(record.session_id)
    producer.produce(resolved_topic, record.to_meta_record_json_bytes())
    return resolved_topic


def publish_marker_events(
    producer: object,
    markers: Iterable[MarkerEventV1],
    *,
    topic_name: str | None = None,
) -> list[str]:
    topics: list[str] = []
    for marker in markers:
        resolved_topic = topic_name or marker_stream(marker.session_id)
        producer.produce(resolved_topic, marker.to_json_bytes())
        topics.append(resolved_topic)
    return topics


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish session metadata and optional lifecycle markers to Kafka."
    )
    parser.add_argument("--broker", default="127.0.0.1:29092")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--purpose", default="training")
    parser.add_argument("--participant-id", default="")
    parser.add_argument("--protocol-id", default="")
    parser.add_argument("--device-id", action="append", dest="device_ids", default=[])
    parser.add_argument("--tag", action="append", dest="tags", default=[])
    parser.add_argument("--notes", default="")
    parser.add_argument("--created-at-us", type=int)
    parser.add_argument("--updated-at-us", type=int)
    parser.add_argument("--emit-start-marker", action="store_true")
    parser.add_argument("--emit-end-marker", action="store_true")
    parser.add_argument("--meta-topic")
    parser.add_argument("--marker-topic")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    record = build_session_metadata_record(
        session_id=args.session_id,
        purpose=args.purpose,
        participant_id=args.participant_id,
        protocol_id=args.protocol_id,
        device_ids=args.device_ids,
        tags=args.tags,
        notes=args.notes,
        created_at_us=args.created_at_us,
        updated_at_us=args.updated_at_us,
    )
    markers: list[MarkerEventV1] = []
    if args.emit_start_marker:
        markers.append(build_session_lifecycle_marker(record, event="start"))
    if args.emit_end_marker:
        markers.append(build_session_lifecycle_marker(record, event="end"))

    if args.dry_run:
        print(record.to_meta_record_json_bytes().decode("utf-8"))
        for marker in markers:
            print(marker.to_json_bytes().decode("utf-8"))
        return

    producer = open_producer(args.broker)
    try:
        meta_topic_name = publish_session_metadata_record(
            producer,
            record,
            topic_name=args.meta_topic,
        )
        marker_topic_names = publish_marker_events(
            producer,
            markers,
            topic_name=args.marker_topic,
        )
        producer.flush()
    finally:
        close = getattr(producer, "close", None)
        if callable(close):
            close()
    print(f"Published SessionMetadataRecord to {meta_topic_name}")
    for topic_name, marker in zip(marker_topic_names, markers, strict=True):
        print(
            f"Published session {marker.event} marker to {topic_name} "
            f"at {marker.emitted_at_us}"
        )
