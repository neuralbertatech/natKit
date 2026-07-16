from __future__ import annotations

import ctypes

from natvr.libnatkit_stitch import _load_library


def _configure_meta_abi(handle: ctypes.CDLL) -> None:
    if getattr(handle, "_natvr_meta_configured", False):
        return
    handle.nat_session_metadata_record_encode_json.argtypes = [
        ctypes.POINTER(ctypes.c_uint8),
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_uint8)),
        ctypes.POINTER(ctypes.c_size_t),
    ]
    handle.nat_session_metadata_record_encode_json.restype = ctypes.c_int
    handle.nat_session_metadata_record_decode_json.argtypes = [
        ctypes.POINTER(ctypes.c_uint8),
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_uint8)),
        ctypes.POINTER(ctypes.c_size_t),
    ]
    handle.nat_session_metadata_record_decode_json.restype = ctypes.c_int
    handle.nat_free_bytes.argtypes = [ctypes.POINTER(ctypes.c_uint8)]
    handle.nat_free_bytes.restype = None
    setattr(handle, "_natvr_meta_configured", True)


def _bytes_to_array(data: bytes) -> ctypes.Array[ctypes.c_uint8]:
    if not data:
        return (ctypes.c_uint8 * 1)()
    return (ctypes.c_uint8 * len(data)).from_buffer_copy(data)


def encode_session_metadata_record_json(payload: bytes) -> bytes:
    handle = _load_library()
    _configure_meta_abi(handle)
    payload_array = _bytes_to_array(payload)
    out_ptr = ctypes.POINTER(ctypes.c_uint8)()
    out_size = ctypes.c_size_t()
    status = handle.nat_session_metadata_record_encode_json(
        payload_array,
        len(payload),
        ctypes.byref(out_ptr),
        ctypes.byref(out_size),
    )
    if status != 0:
        raise RuntimeError(
            f"libnatkit session metadata encode failed with status {status}"
        )
    try:
        return bytes(ctypes.string_at(out_ptr, out_size.value))
    finally:
        handle.nat_free_bytes(out_ptr)


def decode_session_metadata_record_json(message: bytes) -> bytes:
    handle = _load_library()
    _configure_meta_abi(handle)
    message_array = _bytes_to_array(message)
    out_ptr = ctypes.POINTER(ctypes.c_uint8)()
    out_size = ctypes.c_size_t()
    status = handle.nat_session_metadata_record_decode_json(
        message_array,
        len(message),
        ctypes.byref(out_ptr),
        ctypes.byref(out_size),
    )
    if status != 0:
        raise RuntimeError(
            f"libnatkit session metadata decode failed with status {status}"
        )
    try:
        return bytes(ctypes.string_at(out_ptr, out_size.value))
    finally:
        handle.nat_free_bytes(out_ptr)
