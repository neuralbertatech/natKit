"""ctypes bindings for libnatkit-core schema JSON transcoding ABI.

Home of the shared two-call size/fill machinery (``docs/ABI_CONVENTIONS.md``)
and the per-schema wrappers built on it. Each ``*_encode_json`` /
``*_decode_json`` pair round-trips through the shared C++ schema so the field
decoding Python's ``natvr.models`` hand-writes has a single source of truth.

Phase 3a piloted the pattern with MarkerEventV1; Phase 3b adds
ExgPillEmgDataSchemaV1. SessionMetadataRecord keeps its older
callee-allocates binding in :mod:`natvr.libnatkit_meta`.
"""

from __future__ import annotations

import ctypes

from natvr.libnatkit_stitch import _load_library

_NAT_OK = 0


def _bytes_to_array(data: bytes) -> ctypes.Array[ctypes.c_uint8]:
    if not data:
        return (ctypes.c_uint8 * 1)()
    return (ctypes.c_uint8 * len(data)).from_buffer_copy(data)


def _transcoder(handle: ctypes.CDLL, name: str):
    configured = getattr(handle, "_natvr_transcoders", None)
    if configured is None:
        configured = set()
        setattr(handle, "_natvr_transcoders", configured)
    fn = getattr(handle, name)
    if name not in configured:
        fn.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),  # input
            ctypes.c_size_t,  # input size
            ctypes.POINTER(ctypes.c_uint8),  # output (NULL to size)
            ctypes.POINTER(ctypes.c_size_t),  # in/out output size
        ]
        fn.restype = ctypes.c_int
        configured.add(name)
    return fn


def _transcode(symbol: str, data: bytes, what: str) -> bytes:
    handle = _load_library()
    fn = _transcoder(handle, symbol)
    input_array = _bytes_to_array(data)
    size = ctypes.c_size_t(0)

    # Sizing call: NULL output buffer -> required byte count in `size`.
    status = fn(input_array, len(data), None, ctypes.byref(size))
    if status != _NAT_OK:
        raise RuntimeError(f"{what} sizing call failed with status {status}")

    # Fill call.
    out = (ctypes.c_uint8 * size.value)() if size.value else (ctypes.c_uint8 * 1)()
    status = fn(input_array, len(data), out, ctypes.byref(size))
    if status != _NAT_OK:
        raise RuntimeError(f"{what} fill call failed with status {status}")
    return bytes(out[: size.value])


def marker_event_encode_json(payload: bytes) -> bytes:
    """Canonical MarkerEventV1 wire message for a logical field-JSON payload."""
    return _transcode(
        "nat_core_v1_marker_event_encode_json", payload, "marker encode"
    )


def marker_event_decode_json(message: bytes) -> bytes:
    """Canonical MarkerEventV1 field JSON for a wire message."""
    return _transcode(
        "nat_core_v1_marker_event_decode_json", message, "marker decode"
    )


def emg_frame_encode_json(payload: bytes) -> bytes:
    """Canonical ExgPillEmgDataSchemaV1 wire message for a field-JSON payload."""
    return _transcode("nat_core_v1_emg_frame_encode_json", payload, "emg encode")


def emg_frame_decode_json(message: bytes) -> bytes:
    """Canonical ExgPillEmgDataSchemaV1 field JSON for a wire message."""
    return _transcode("nat_core_v1_emg_frame_decode_json", message, "emg decode")
