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
    _FrameDeduper,
    _HostTimeStamper,
    _load_emg_required,
    _pick_autodetect_port,
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


# --- De-dupe (switchover-overlap safety net) ------------------------------


def test_duplicate_frame_dropped_across_switchover() -> None:
    stats = _Stats()
    deduper = _FrameDeduper(window=16)
    frame = _emg_frame(device_id="emg01")
    frame["seq_no"] = 42
    line = json.dumps(frame)

    first = _route_line(line, _REQUIRED, stats, deduper=deduper)
    second = _route_line(line, _REQUIRED, stats, deduper=deduper)

    assert first is not None  # first copy forwarded
    assert second is None  # duplicate (same device_id, seq_no) dropped
    assert stats.skipped_duplicate == 1


def test_same_seq_no_different_device_not_deduped() -> None:
    stats = _Stats()
    deduper = _FrameDeduper(window=16)
    a = _emg_frame(device_id="left")
    a["seq_no"] = 7
    b = _emg_frame(device_id="right")
    b["seq_no"] = 7
    assert _route_line(json.dumps(a), _REQUIRED, stats, deduper=deduper) is not None
    assert _route_line(json.dumps(b), _REQUIRED, stats, deduper=deduper) is not None
    assert stats.skipped_duplicate == 0


def test_deduper_window_evicts_old_seq_nos() -> None:
    deduper = _FrameDeduper(window=2)
    assert deduper.is_duplicate("d", 1) is False
    assert deduper.is_duplicate("d", 2) is False
    assert deduper.is_duplicate("d", 3) is False  # evicts seq 1
    assert deduper.is_duplicate("d", 1) is False  # seq 1 no longer remembered
    assert deduper.is_duplicate("d", 3) is True  # still within window


def test_no_deduper_forwards_duplicates_verbatim() -> None:
    stats = _Stats()
    frame = _emg_frame()
    frame["seq_no"] = 5
    line = json.dumps(frame)
    assert _route_line(line, _REQUIRED, stats) is not None
    assert _route_line(line, _REQUIRED, stats) is not None  # no dedupe -> both pass
    assert stats.skipped_duplicate == 0


# --- Host-timestamp rewrite -----------------------------------------------


def test_stamp_host_time_rewrites_device_ts_us() -> None:
    stats = _Stats()
    stamper = _HostTimeStamper(now_us=lambda: 5_000_000)
    frame = _emg_frame(device_id="emg01")
    frame["device_ts_us"] = 123  # firmware's unsynced monotonic value
    routed = _route_line(json.dumps(frame), _REQUIRED, stats, stamper=stamper)
    assert routed is not None
    _topic, payload = routed
    rewritten = json.loads(payload)
    assert rewritten["device_ts_us"] == 5_000_000
    # Frame is re-serialized (not byte-identical) but still valid + routable.
    assert rewritten["schema_version"] == EMG_SCHEMA_VERSION


def test_stamp_host_time_is_monotonic_per_device() -> None:
    stats = _Stats()
    # A clock that returns the same value twice would otherwise produce a
    # non-increasing device_ts_us; the stamper must bump it.
    stamper = _HostTimeStamper(now_us=lambda: 1_000)
    frame = _emg_frame(device_id="emg01")
    ts = []
    for _ in range(3):
        routed = _route_line(json.dumps(frame), _REQUIRED, stats, stamper=stamper)
        assert routed is not None
        ts.append(json.loads(routed[1])["device_ts_us"])
    assert ts == sorted(ts) and len(set(ts)) == 3  # strictly increasing


# --- Port auto-detect ------------------------------------------------------


class _FakePort:
    def __init__(self, device: str, vid: int | None = None) -> None:
        self.device = device
        self.vid = vid


def test_autodetect_prefers_known_usb_vid() -> None:
    ports = [
        _FakePort("/dev/ttyACM0", vid=0x1234),  # unknown vendor
        _FakePort("/dev/ttyACM1", vid=0x303A),  # Espressif
    ]
    assert _pick_autodetect_port(ports) == "/dev/ttyACM1"


def test_autodetect_falls_back_to_tty_name() -> None:
    ports = [
        _FakePort("/dev/ttyS0"),  # onboard serial, not a USB device
        _FakePort("/dev/ttyACM0"),
    ]
    assert _pick_autodetect_port(ports) == "/dev/ttyACM0"


def test_autodetect_returns_none_when_nothing_plausible() -> None:
    assert _pick_autodetect_port([_FakePort("/dev/ttyS0")]) is None
    assert _pick_autodetect_port([]) is None
