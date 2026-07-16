"""Python side of the libnatkit-core stream-identity golden-vector test.

Reads the SAME fixture the C++ test binary reads
(``libnatkit/lib/libnatkit-core/tests/stream_id_golden.json``) so the ctypes
binding and the native implementation are checked against one shared source of
truth. The fixture is checked in once and never regenerated per run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_INT64_MAX = (1 << 63) - 1
_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE = (
    _REPO_ROOT
    / "libnatkit"
    / "lib"
    / "libnatkit-core"
    / "tests"
    / "stream_id_golden.json"
)


def _load_binding():
    from natvr import libnatkit_core

    try:
        libnatkit_core._load_library()
    except FileNotFoundError as error:
        pytest.skip(f"libnatkit-core shared library unavailable: {error}")
    return libnatkit_core


def _fixture() -> dict:
    if not _FIXTURE.exists():
        pytest.skip(f"golden fixture missing: {_FIXTURE}")
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_stream_id_golden_vectors() -> None:
    core = _load_binding()
    vectors = _fixture()["stream_id_vectors"]
    assert vectors, "fixture has no stream_id_vectors"
    for vector in vectors:
        actual = core.stable_stream_id(vector["namespace"], vector["identifier"])
        assert actual == vector["stream_id"], vector
        # Post-condition of the 63-bit mask and 0->1 fallback.
        assert 1 <= actual <= _INT64_MAX, vector


def test_topic_build_and_parse_golden_vectors() -> None:
    core = _load_binding()
    vectors = _fixture()["topic_vectors"]
    assert vectors, "fixture has no topic_vectors"
    for vector in vectors:
        topic = core.build_topic(
            vector["stream_type"],
            vector["namespace"],
            vector["identifier"],
            vector["schema_name"],
            vector["serialization"],
        )
        assert topic == vector["topic"], vector

        parsed = core.parse_topic(topic)
        assert parsed.stream_type == vector["stream_type"]
        assert parsed.serialization == vector["serialization"]
        assert parsed.schema_name == vector["schema_name"]
        assert parsed.stream_id == core.stable_stream_id(
            vector["namespace"], vector["identifier"]
        )


def test_invalid_identifier_raises() -> None:
    core = _load_binding()
    with pytest.raises(ValueError):
        core.build_topic("Data", "device_id", "bad id!", "SchemaV1")
