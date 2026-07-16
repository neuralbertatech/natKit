"""Unit tests for the serial backup ingest shim's pure routing logic.

Exercises frame parsing/validation/topic-routing without a serial port or an
MQTT broker (those are I/O and mocked out in run_bridge). Confirms the shim
forwards well-formed EMG frames verbatim onto the standard MQTT topic, tolerates
interleaved firmware log lines, and drops corrupt frames.
"""

from __future__ import annotations

import json

from natvr.bridge.serial_bridge import (
    EMG_SCHEMA_VERSION,
    STATUS_SCHEMA_VERSION,
    _load_emg_required,
    _route_line,
    _Stats,
)


_REQUIRED = _load_emg_required()


def _emg_frame(device_id: str = "emg01", n_channels: int = 3) -> dict:
    return {
        "schema_version": EMG_SCHEMA_VERSION,
        "device_id": device_id,
        "seq_no": 7,
        "device_ts_us": 123456,
        "n_channels": n_channels,
        "samples_per_channel": 2,
        "sample_rate_hz": 1000,
        "channel_labels": [f"ch{i}" for i in range(n_channels)],
        "payload": [[1, -2] for _ in range(n_channels)],
    }


def test_emg_frame_routes_to_standard_topic_verbatim() -> None:
    stats = _Stats()
    line = json.dumps(_emg_frame(device_id="forearm-a"))
    routed = _route_line(line, _REQUIRED, stats)
    assert routed is not None
    topic, payload = routed
    assert topic == "natKit/sending/emg/raw/emg.raw.forearm-a"
    # Published payload is the original line bytes, byte-for-byte.
    assert payload == line.encode("utf-8")
    assert stats.published == 0  # _route_line does not itself count publishes
    assert stats.skipped_nonjson == 0
    assert stats.skipped_invalid == 0


def test_status_frame_routes_to_status_topic() -> None:
    stats = _Stats()
    frame = {
        "schema_version": STATUS_SCHEMA_VERSION,
        "device_id": "emg01",
        "status_device_id": "emg01-fw",
    }
    line = json.dumps(frame)
    routed = _route_line(line, _REQUIRED, stats)
    assert routed is not None
    topic, _payload = routed
    assert topic == "natKit/sending/emg/status/device.status.emg01-fw"


def test_non_json_log_line_is_skipped() -> None:
    stats = _Stats()
    assert _route_line("I (1234) natvr-emg-fw: booting", _REQUIRED, stats) is None
    assert stats.skipped_nonjson == 1
    assert stats.skipped_invalid == 0


def test_channel_count_mismatch_is_dropped() -> None:
    stats = _Stats()
    frame = _emg_frame(n_channels=3)
    frame["payload"] = [[1, -2], [3, 4]]  # only 2 channels, n_channels says 3
    routed = _route_line(json.dumps(frame), _REQUIRED, stats)
    assert routed is None
    assert stats.skipped_invalid == 1


def test_sample_count_mismatch_is_dropped() -> None:
    stats = _Stats()
    frame = _emg_frame(n_channels=1)
    frame["payload"] = [[1, 2, 3]]  # 3 samples, samples_per_channel says 2
    routed = _route_line(json.dumps(frame), _REQUIRED, stats)
    assert routed is None
    assert stats.skipped_invalid == 1


def test_missing_required_key_is_dropped() -> None:
    stats = _Stats()
    frame = _emg_frame()
    del frame["device_ts_us"]
    routed = _route_line(json.dumps(frame), _REQUIRED, stats)
    assert routed is None
    assert stats.skipped_invalid == 1


def test_unknown_schema_version_is_skipped() -> None:
    stats = _Stats()
    line = json.dumps({"schema_version": "some.other.schema.v1", "device_id": "x"})
    assert _route_line(line, _REQUIRED, stats) is None
    assert stats.skipped_nonjson == 1


def test_required_keys_loaded_from_schema() -> None:
    # Confirms the shim tracks the real schema contract, not just the fallback.
    assert "schema_version" in _REQUIRED
    assert "payload" in _REQUIRED
    assert "device_ts_us" in _REQUIRED
