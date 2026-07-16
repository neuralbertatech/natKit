from __future__ import annotations

from natvr.libnatkit_core import build_topic
from natvr.models import EMG_TOPIC_SCHEMA_NAME


def _kafka_topic(
    stream_type: str,
    namespace: str,
    identifier: str,
    schema_name: str,
    serialization: str = "Json",
) -> str:
    # Single source of truth: stream-id hashing and topic formatting (and
    # identifier validation) all live in the shared libnatkit-core C ABI, so
    # this no longer reimplements the FNV-1a hash that C++ also computes. An
    # invalid identifier raises ValueError, as the old local validator did.
    return build_topic(stream_type, namespace, identifier, schema_name, serialization)


def emg_raw(device_id: str) -> str:
    return _kafka_topic("Data", "device_id", device_id, EMG_TOPIC_SCHEMA_NAME)


def imu_quat(device_id: str) -> str:
    return _kafka_topic("Data", "device_id", device_id, "NatImuDataSchema")


def hand_state(session_id: str) -> str:
    return _kafka_topic("Data", "session_id", session_id, "HandStateV1")


def marker_stream(session_id: str) -> str:
    return _kafka_topic("Marker", "session_id", session_id, "MarkerEventV1")


def cue_marker(session_id: str) -> str:
    return marker_stream(session_id)


def meta_session(session_id: str) -> str:
    return _kafka_topic("Meta", "session_id", session_id, "MetaRecord")


def device_status(device_id: str) -> str:
    return _kafka_topic("Status", "device_id", device_id, "DeviceStatusV1")


def device_firmware_status(device_id: str) -> str:
    return _kafka_topic(
        "Heartbeat", "status_device_id", device_id, "DeviceFirmwareStatusV1"
    )
