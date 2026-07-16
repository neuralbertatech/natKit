"""Phase 3a acceptance test: MarkerEventV1 JSON ABI round trips.

Exercises the two-call variable-length ABI against REAL captured Kafka marker
payloads (``tests/data/marker_events_real.jsonl``, a slice of a recorded
session), not synthetic ones. It cross-checks the shared C++ implementation
(reached through ctypes) against the hand-written Python decoder in
``natvr.models`` that ``emg_consumer.py`` uses today -- the duplication Phase 3
removes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from natvr.models import MarkerEventV1

_FIXTURE = Path(__file__).resolve().parent / "data" / "marker_events_real.jsonl"


def _load_binding():
    from natvr import libnatkit_marker

    try:
        from natvr.libnatkit_stitch import _load_library

        _load_library()
    except FileNotFoundError as error:
        pytest.skip(f"libnatkit-core shared library unavailable: {error}")
    return libnatkit_marker


def _real_payloads() -> list[bytes]:
    if not _FIXTURE.exists():
        pytest.skip(f"marker fixture missing: {_FIXTURE}")
    lines = [line for line in _FIXTURE.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines, "fixture has no marker payloads"
    return [line.encode("utf-8") for line in lines]


def test_abi_decode_matches_python_handdecoder() -> None:
    """C++ decode (via ctypes) agrees field-for-field with the Python model."""
    marker = _load_binding()
    for wire in _real_payloads():
        abi_fields = json.loads(marker.marker_event_decode_json(wire))
        py_fields = MarkerEventV1.from_json_bytes(wire).to_dict()
        assert abi_fields == py_fields


def test_abi_encode_decode_round_trip_is_byte_stable() -> None:
    """encode/decode are canonicalizing and idempotent byte-for-byte."""
    marker = _load_binding()
    for wire in _real_payloads():
        # Real capture -> canonical wire (semantic equality; key order may
        # differ between the capture's producer and nlohmann).
        canonical = marker.marker_event_encode_json(wire)
        assert json.loads(canonical) == json.loads(wire)

        # Canonical form is a fixed point of both directions, byte-for-byte.
        assert marker.marker_event_encode_json(canonical) == canonical
        assert marker.marker_event_decode_json(canonical) == canonical
        assert marker.marker_event_decode_json(wire) == canonical


def test_cross_direction_matches_python_encoder() -> None:
    """C++ encode of the Python model's payload == C++ canonical wire."""
    marker = _load_binding()
    for wire in _real_payloads():
        model = MarkerEventV1.from_json_bytes(wire)
        abi_from_model = marker.marker_event_encode_json(model.to_json_bytes())
        assert json.loads(abi_from_model) == json.loads(wire)


def test_malformed_payload_raises() -> None:
    marker = _load_binding()
    with pytest.raises(RuntimeError):
        marker.marker_event_decode_json(b"not json at all")
