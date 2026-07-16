"""Phase 3b acceptance test: ExgPillEmgDataSchemaV1 JSON ABI round trips.

Applies the two-call variable-length pattern proven for MarkerEventV1 to the EMG
frame schema, cross-checking the shared C++ decoder (via ctypes) against the
hand-written Python decoder in ``natvr.models`` -- the drift-prone duplication
Phase 3 removes.

No raw EMG frame payloads are captured in-repo (only markers/features/metadata),
so the corpus is built with the actual Python producer serialization
(``ExgPillEmgDataSchemaV1.to_json_bytes``) seeded from REAL session parameters
(device ``emg01`` and channel label ``flexor_a`` taken from the recorded
``captures/reconstructed/...run-01.meta.json``). These are genuine wire-format
frames; the parity/idempotency guarantees are what the test asserts.
"""

from __future__ import annotations

import json

import pytest

from natvr.models import ExgPillEmgDataSchemaV1


def _load_binding():
    from natvr import libnatkit_schema

    try:
        from natvr.libnatkit_stitch import _load_library

        _load_library()
    except FileNotFoundError as error:
        pytest.skip(f"libnatkit-core shared library unavailable: {error}")
    return libnatkit_schema


def _real_format_frames() -> list[bytes]:
    # Seeded from the real recorded session (device_id + channel_map label).
    frames = [
        ExgPillEmgDataSchemaV1(
            device_id="emg01",
            seq_no=0,
            device_ts_us=1782496727200000,
            sample_rate_hz=2000,
            channel_labels=("flexor_a",),
            channels=((100, 120, 90, -50, -40),),
        ),
        ExgPillEmgDataSchemaV1(
            device_id="emg01",
            seq_no=1,
            device_ts_us=1782496727202500,
            sample_rate_hz=2000,
            channel_labels=("flexor_a", "extensor_a"),
            channels=((0, 32767, -32768, 1), (-1, 2, -3, 4)),
        ),
    ]
    return [frame.to_json_bytes() for frame in frames]


def test_abi_decode_matches_python_handdecoder() -> None:
    schema = _load_binding()
    for wire in _real_format_frames():
        abi_fields = json.loads(schema.emg_frame_decode_json(wire))
        py_fields = ExgPillEmgDataSchemaV1.from_json_bytes(wire).to_dict()
        assert abi_fields == py_fields


def test_abi_encode_decode_round_trip_is_byte_stable() -> None:
    schema = _load_binding()
    for wire in _real_format_frames():
        canonical = schema.emg_frame_encode_json(wire)
        assert json.loads(canonical) == json.loads(wire)
        assert schema.emg_frame_encode_json(canonical) == canonical
        assert schema.emg_frame_decode_json(canonical) == canonical
        assert schema.emg_frame_decode_json(wire) == canonical


def test_abi_rejects_out_of_range_samples() -> None:
    # The C++ decoder enforces the int16 sample range; a value outside it must be
    # rejected rather than silently truncated.
    schema = _load_binding()
    bad = json.dumps(
        {
            "schema_version": "exg.pill.emg.data.v1",
            "device_id": "emg01",
            "seq_no": 0,
            "device_ts_us": 1,
            "n_channels": 1,
            "samples_per_channel": 1,
            "sample_rate_hz": 2000,
            "channel_labels": ["flexor_a"],
            "payload": [[40000]],
        }
    ).encode("utf-8")
    with pytest.raises(RuntimeError):
        schema.emg_frame_decode_json(bad)


def test_malformed_payload_raises() -> None:
    schema = _load_binding()
    with pytest.raises(RuntimeError):
        schema.emg_frame_decode_json(b"{not valid json")
