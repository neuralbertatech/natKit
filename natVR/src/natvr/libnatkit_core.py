"""ctypes binding for the libnatkit-core stream-identity C ABI.

Mirrors the ``libnatkit_stitch`` pattern: it loads the same ``libnatkit-core``
shared library (reusing that module's discovery so the search logic lives in one
place) and declares ``argtypes``/``restype`` for the ``nat_core_v1_*`` symbols.

This is the single source of truth for stream ids and Kafka topic strings, used
by :mod:`natvr.topics`. It deliberately calls the shared C++ implementation
rather than reimplementing the FNV-1a hash in Python.
"""

from __future__ import annotations

import ctypes
from typing import NamedTuple

from natvr.libnatkit_stitch import find_libnatkit_core

# Status codes from libnatkit-core-abi.h. 0 is success.
_NAT_OK = 0
_NAT_ERR_INVALID_ARGUMENT = 2

_UNSET = object()
_LIB_HANDLE: ctypes.CDLL | object = _UNSET


def _load_library() -> ctypes.CDLL:
    global _LIB_HANDLE
    if _LIB_HANDLE is not _UNSET:
        return _LIB_HANDLE  # type: ignore[return-value]

    path = find_libnatkit_core()
    if path is None:
        raise FileNotFoundError(
            "libnatkit-core shared library not found. Set LIBNATKIT_CORE_PATH "
            "or build libnatkit/lib/libnatkit-core."
        )
    handle = ctypes.CDLL(str(path))

    handle.nat_core_v1_stream_id.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_uint64),
    ]
    handle.nat_core_v1_stream_id.restype = ctypes.c_int

    handle.nat_core_v1_topic_build.argtypes = [
        ctypes.c_char_p,  # stream_type
        ctypes.c_char_p,  # topic_namespace
        ctypes.c_char_p,  # identifier
        ctypes.c_char_p,  # serialization
        ctypes.c_char_p,  # schema_name
        ctypes.c_char_p,  # out_topic (NULL to size)
        ctypes.POINTER(ctypes.c_size_t),  # inout_topic_size
    ]
    handle.nat_core_v1_topic_build.restype = ctypes.c_int

    handle.nat_core_v1_topic_parse.argtypes = [
        ctypes.c_char_p,  # topic
        ctypes.POINTER(ctypes.c_uint64),  # out_stream_id
        ctypes.c_char_p,  # out_stream_type
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.c_char_p,  # out_serialization
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.c_char_p,  # out_schema_name
        ctypes.POINTER(ctypes.c_size_t),
    ]
    handle.nat_core_v1_topic_parse.restype = ctypes.c_int

    _LIB_HANDLE = handle
    return handle


def stable_stream_id(namespace: str, identifier: str) -> int:
    """Return the stable FNV-1a stream id for ``(namespace, identifier)``."""
    handle = _load_library()
    out = ctypes.c_uint64(0)
    status = handle.nat_core_v1_stream_id(
        namespace.encode("utf-8"),
        identifier.encode("utf-8"),
        ctypes.byref(out),
    )
    if status != _NAT_OK:
        raise RuntimeError(f"nat_core_v1_stream_id failed with status {status}")
    return int(out.value)


def build_topic(
    stream_type: str,
    namespace: str,
    identifier: str,
    schema_name: str,
    serialization: str = "Json",
) -> str:
    """Build the Kafka topic string for the given components.

    Uses the two-call size/fill ABI pattern. Raises ``ValueError`` for an
    invalid identifier segment or unknown stream type / serialization (mirroring
    the validation ``topics.py`` performed before this moved into C++).
    """
    handle = _load_library()
    type_bytes = stream_type.encode("utf-8")
    namespace_bytes = namespace.encode("utf-8")
    identifier_bytes = identifier.encode("utf-8")
    serialization_bytes = serialization.encode("utf-8")
    schema_bytes = schema_name.encode("utf-8")

    size = ctypes.c_size_t(0)
    status = handle.nat_core_v1_topic_build(
        type_bytes,
        namespace_bytes,
        identifier_bytes,
        serialization_bytes,
        schema_bytes,
        None,
        ctypes.byref(size),
    )
    _raise_for_build_status(status)

    buffer = ctypes.create_string_buffer(size.value)
    status = handle.nat_core_v1_topic_build(
        type_bytes,
        namespace_bytes,
        identifier_bytes,
        serialization_bytes,
        schema_bytes,
        buffer,
        ctypes.byref(size),
    )
    _raise_for_build_status(status)
    return buffer.value.decode("utf-8")


class ParsedTopic(NamedTuple):
    stream_type: str
    serialization: str
    stream_id: int
    schema_name: str


def parse_topic(topic: str) -> ParsedTopic:
    """Parse a Kafka topic string into its components via the C ABI."""
    handle = _load_library()
    topic_bytes = topic.encode("utf-8")

    stream_id = ctypes.c_uint64(0)
    type_size = ctypes.c_size_t(0)
    ser_size = ctypes.c_size_t(0)
    schema_size = ctypes.c_size_t(0)

    # Sizing pass (NULL string buffers).
    status = handle.nat_core_v1_topic_parse(
        topic_bytes,
        ctypes.byref(stream_id),
        None,
        ctypes.byref(type_size),
        None,
        ctypes.byref(ser_size),
        None,
        ctypes.byref(schema_size),
    )
    if status != _NAT_OK:
        raise ValueError(f"cannot parse topic {topic!r} (status {status})")

    type_buf = ctypes.create_string_buffer(type_size.value)
    ser_buf = ctypes.create_string_buffer(ser_size.value)
    schema_buf = ctypes.create_string_buffer(schema_size.value)
    status = handle.nat_core_v1_topic_parse(
        topic_bytes,
        ctypes.byref(stream_id),
        type_buf,
        ctypes.byref(type_size),
        ser_buf,
        ctypes.byref(ser_size),
        schema_buf,
        ctypes.byref(schema_size),
    )
    if status != _NAT_OK:
        raise ValueError(f"cannot parse topic {topic!r} (status {status})")

    return ParsedTopic(
        stream_type=type_buf.value.decode("utf-8"),
        serialization=ser_buf.value.decode("utf-8"),
        stream_id=int(stream_id.value),
        schema_name=schema_buf.value.decode("utf-8"),
    )


def _raise_for_build_status(status: int) -> None:
    if status == _NAT_OK:
        return
    if status == _NAT_ERR_INVALID_ARGUMENT:
        raise ValueError(
            "invalid topic component (identifier must match "
            "[A-Za-z0-9][A-Za-z0-9_-]* and stream type / serialization must be "
            "known)"
        )
    raise RuntimeError(f"nat_core_v1_topic_build failed with status {status}")
