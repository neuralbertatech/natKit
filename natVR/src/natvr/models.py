from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Literal, Mapping

from natvr.libnatkit_meta import (
    decode_session_metadata_record_json,
    encode_session_metadata_record_json,
)


def _require_uint(name: str, value: int) -> int:
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _require_positive_int(name: str, value: int) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _require_probability(name: str, value: float) -> float:
    if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"{name} must be between 0.0 and 1.0")
    return float(value)


def _require_samples(channels: tuple[tuple[int, ...], ...]) -> tuple[int, int]:
    if not channels:
        raise ValueError("channels must not be empty")
    sample_count = len(channels[0])
    if sample_count == 0:
        raise ValueError("channels must contain at least one sample")
    for idx, channel in enumerate(channels):
        if len(channel) != sample_count:
            raise ValueError(
                f"channel {idx} has {len(channel)} samples, expected {sample_count}"
            )
        for sample in channel:
            if not isinstance(sample, int):
                raise ValueError("all channel samples must be integers")
            if not -32768 <= sample <= 32767:
                raise ValueError("all channel samples must fit in signed int16")
    return len(channels), sample_count


EMG_PAYLOAD_SCHEMA_VERSION = "exg.pill.emg.data.v1"
EMG_TOPIC_SCHEMA_NAME = "ExgPillEmgDataSchemaV1"


@dataclass(frozen=True, slots=True)
class ExgPillEmgDataSchemaV1:
    device_id: str
    seq_no: int
    device_ts_us: int
    sample_rate_hz: int
    channel_labels: tuple[str, ...]
    channels: tuple[tuple[int, ...], ...]
    schema_version: str = EMG_PAYLOAD_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.device_id:
            raise ValueError("device_id must not be empty")
        _require_uint("seq_no", self.seq_no)
        _require_uint("device_ts_us", self.device_ts_us)
        _require_positive_int("sample_rate_hz", self.sample_rate_hz)
        channel_count, sample_count = _require_samples(self.channels)
        if len(self.channel_labels) != channel_count:
            raise ValueError("channel_labels length must match channels length")
        if not all(label for label in self.channel_labels):
            raise ValueError("channel_labels must not contain empty values")
        if sample_count <= 0:
            raise ValueError("samples_per_channel must be positive")

    @property
    def n_channels(self) -> int:
        return len(self.channels)

    @property
    def samples_per_channel(self) -> int:
        return len(self.channels[0])

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "device_id": self.device_id,
            "seq_no": self.seq_no,
            "device_ts_us": self.device_ts_us,
            "n_channels": self.n_channels,
            "samples_per_channel": self.samples_per_channel,
            "sample_rate_hz": self.sample_rate_hz,
            "channel_labels": list(self.channel_labels),
            "payload": [list(channel) for channel in self.channels],
        }

    def to_json_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), separators=(",", ":")).encode("utf-8")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ExgPillEmgDataSchemaV1":
        channels = tuple(tuple(int(sample) for sample in channel) for channel in payload["payload"])
        return cls(
            schema_version=str(payload.get("schema_version", EMG_PAYLOAD_SCHEMA_VERSION)),
            device_id=str(payload["device_id"]),
            seq_no=int(payload["seq_no"]),
            device_ts_us=int(payload["device_ts_us"]),
            sample_rate_hz=int(payload["sample_rate_hz"]),
            channel_labels=tuple(str(label) for label in payload["channel_labels"]),
            channels=channels,
        )

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> "ExgPillEmgDataSchemaV1":
        return cls.from_dict(json.loads(payload.decode("utf-8")))


@dataclass(frozen=True, slots=True)
class MarkerEventV1:
    session_id: str
    marker_type: str
    marker_id: str
    event: str
    label: str
    emitted_at_us: int
    attributes: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "marker.event.v1"

    def __post_init__(self) -> None:
        if not self.session_id:
            raise ValueError("session_id must not be empty")
        if not self.marker_type:
            raise ValueError("marker_type must not be empty")
        if not self.marker_id:
            raise ValueError("marker_id must not be empty")
        if not self.event:
            raise ValueError("event must not be empty")
        if not self.label:
            raise ValueError("label must not be empty")
        _require_uint("emitted_at_us", self.emitted_at_us)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "marker_type": self.marker_type,
            "marker_id": self.marker_id,
            "event": self.event,
            "label": self.label,
            "emitted_at_us": self.emitted_at_us,
            "attributes": dict(self.attributes),
        }

    def to_json_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), separators=(",", ":")).encode("utf-8")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MarkerEventV1":
        return cls(
            schema_version=str(payload.get("schema_version", "marker.event.v1")),
            session_id=str(payload["session_id"]),
            marker_type=str(payload["marker_type"]),
            marker_id=str(payload["marker_id"]),
            event=str(payload["event"]),
            label=str(payload["label"]),
            emitted_at_us=int(payload["emitted_at_us"]),
            attributes=dict(payload.get("attributes") or {}),
        )

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> "MarkerEventV1":
        return cls.from_dict(json.loads(payload.decode("utf-8")))


@dataclass(frozen=True, slots=True)
class SessionMetadataRecord:
    session_id: str
    purpose: str = ""
    participant_id: str = ""
    protocol_id: str = ""
    device_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    notes: str = ""
    created_at_us: int = 0
    updated_at_us: int = 0
    schema_version: str = "session.metadata.record.v1"

    def __post_init__(self) -> None:
        if not self.session_id:
            raise ValueError("session_id must not be empty")
        _require_uint("created_at_us", self.created_at_us)
        _require_uint("updated_at_us", self.updated_at_us)
        if self.updated_at_us and self.updated_at_us < self.created_at_us:
            raise ValueError("updated_at_us must be >= created_at_us")
        for field_name, values in (
            ("device_ids", self.device_ids),
            ("tags", self.tags),
        ):
            for value in values:
                if not value:
                    raise ValueError(f"{field_name} must not contain empty values")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "purpose": self.purpose,
            "participant_id": self.participant_id,
            "protocol_id": self.protocol_id,
            "device_ids": list(self.device_ids),
            "tags": list(self.tags),
            "notes": self.notes,
            "created_at_us": self.created_at_us,
            "updated_at_us": self.updated_at_us,
        }

    def to_json_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), separators=(",", ":")).encode("utf-8")

    def to_meta_record_json_bytes(self) -> bytes:
        return encode_session_metadata_record_json(self.to_json_bytes())

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SessionMetadataRecord":
        return cls(
            schema_version=str(
                payload.get("schema_version", "session.metadata.record.v1")
            ),
            session_id=str(payload["session_id"]),
            purpose=str(payload.get("purpose") or ""),
            participant_id=str(payload.get("participant_id") or ""),
            protocol_id=str(payload.get("protocol_id") or ""),
            device_ids=tuple(str(value) for value in payload.get("device_ids") or ()),
            tags=tuple(str(value) for value in payload.get("tags") or ()),
            notes=str(payload.get("notes") or ""),
            created_at_us=int(payload.get("created_at_us") or 0),
            updated_at_us=int(payload.get("updated_at_us") or 0),
        )

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> "SessionMetadataRecord":
        return cls.from_dict(json.loads(payload.decode("utf-8")))

    @classmethod
    def from_meta_record_json_bytes(cls, payload: bytes) -> "SessionMetadataRecord":
        return cls.from_json_bytes(decode_session_metadata_record_json(payload))


@dataclass(frozen=True, slots=True)
class HandStateV1:
    session_id: str
    gesture_id: str
    confidence: float
    curls: tuple[float, float, float, float, float]
    source_window_start_us: int
    source_window_end_us: int
    emitted_at_us: int
    source_device_id: str | None = None
    schema_version: str = "hand.state.v1"

    def __post_init__(self) -> None:
        if not self.session_id:
            raise ValueError("session_id must not be empty")
        if not self.gesture_id:
            raise ValueError("gesture_id must not be empty")
        _require_probability("confidence", self.confidence)
        _require_uint("source_window_start_us", self.source_window_start_us)
        _require_uint("source_window_end_us", self.source_window_end_us)
        _require_uint("emitted_at_us", self.emitted_at_us)
        if self.source_window_end_us < self.source_window_start_us:
            raise ValueError("source_window_end_us must be >= source_window_start_us")
        if len(self.curls) != 5:
            raise ValueError("curls must contain exactly five values")
        for idx, value in enumerate(self.curls):
            _require_probability(f"curls[{idx}]", value)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "gesture_id": self.gesture_id,
            "confidence": self.confidence,
            "curls": list(self.curls),
            "source_window_start_us": self.source_window_start_us,
            "source_window_end_us": self.source_window_end_us,
            "emitted_at_us": self.emitted_at_us,
        }
        if self.source_device_id:
            payload["source_device_id"] = self.source_device_id
        return payload

    def to_bridge_dict(self) -> dict[str, Any]:
        payload = {
            "type": "hand_state",
            "ts": self.emitted_at_us,
            "gesture": self.gesture_id,
            "conf": self.confidence,
            "curls": list(self.curls),
            "window": {
                "start_us": self.source_window_start_us,
                "end_us": self.source_window_end_us,
            },
        }
        if self.source_device_id:
            payload["device_id"] = self.source_device_id
        return payload

    def to_json_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), separators=(",", ":")).encode("utf-8")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "HandStateV1":
        curls = tuple(float(value) for value in payload["curls"])
        return cls(
            schema_version=str(payload.get("schema_version", "hand.state.v1")),
            session_id=str(payload["session_id"]),
            gesture_id=str(payload["gesture_id"]),
            confidence=float(payload["confidence"]),
            curls=curls,  # type: ignore[arg-type]
            source_window_start_us=int(payload["source_window_start_us"]),
            source_window_end_us=int(payload["source_window_end_us"]),
            emitted_at_us=int(payload["emitted_at_us"]),
            source_device_id=(
                str(payload["source_device_id"])
                if payload.get("source_device_id") is not None
                else None
            ),
        )

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> "HandStateV1":
        return cls.from_dict(json.loads(payload.decode("utf-8")))


@dataclass(frozen=True, slots=True)
class DeviceStatusV1:
    device_id: str
    session_id: str
    sample_rate_hz: int
    windows_processed: int
    states_emitted: int
    mean_compute_ms: float
    max_compute_ms: float
    mean_end_to_end_ms: float
    last_compute_ms: float
    last_end_to_end_ms: float
    last_gesture_id: str | None
    emitted_at_us: int
    schema_version: str = "device.status.v1"

    def __post_init__(self) -> None:
        if not self.device_id:
            raise ValueError("device_id must not be empty")
        if not self.session_id:
            raise ValueError("session_id must not be empty")
        _require_positive_int("sample_rate_hz", self.sample_rate_hz)
        _require_uint("windows_processed", self.windows_processed)
        _require_uint("states_emitted", self.states_emitted)
        _require_uint("emitted_at_us", self.emitted_at_us)
        for name, value in (
            ("mean_compute_ms", self.mean_compute_ms),
            ("max_compute_ms", self.max_compute_ms),
            ("mean_end_to_end_ms", self.mean_end_to_end_ms),
            ("last_compute_ms", self.last_compute_ms),
            ("last_end_to_end_ms", self.last_end_to_end_ms),
        ):
            if not isinstance(value, (int, float)) or float(value) < 0.0:
                raise ValueError(f"{name} must be a non-negative number")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "device_id": self.device_id,
            "session_id": self.session_id,
            "sample_rate_hz": self.sample_rate_hz,
            "windows_processed": self.windows_processed,
            "states_emitted": self.states_emitted,
            "mean_compute_ms": self.mean_compute_ms,
            "max_compute_ms": self.max_compute_ms,
            "mean_end_to_end_ms": self.mean_end_to_end_ms,
            "last_compute_ms": self.last_compute_ms,
            "last_end_to_end_ms": self.last_end_to_end_ms,
            "emitted_at_us": self.emitted_at_us,
        }
        if self.last_gesture_id:
            payload["last_gesture_id"] = self.last_gesture_id
        return payload

    def to_json_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), separators=(",", ":")).encode("utf-8")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DeviceStatusV1":
        return cls(
            schema_version=str(payload.get("schema_version", "device.status.v1")),
            device_id=str(payload["device_id"]),
            session_id=str(payload["session_id"]),
            sample_rate_hz=int(payload["sample_rate_hz"]),
            windows_processed=int(payload["windows_processed"]),
            states_emitted=int(payload["states_emitted"]),
            mean_compute_ms=float(payload["mean_compute_ms"]),
            max_compute_ms=float(payload["max_compute_ms"]),
            mean_end_to_end_ms=float(payload["mean_end_to_end_ms"]),
            last_compute_ms=float(payload["last_compute_ms"]),
            last_end_to_end_ms=float(payload["last_end_to_end_ms"]),
            last_gesture_id=(
                str(payload["last_gesture_id"])
                if payload.get("last_gesture_id") is not None
                else None
            ),
            emitted_at_us=int(payload["emitted_at_us"]),
        )

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> "DeviceStatusV1":
        return cls.from_dict(json.loads(payload.decode("utf-8")))
