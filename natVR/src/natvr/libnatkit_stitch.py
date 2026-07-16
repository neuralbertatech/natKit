from __future__ import annotations

import ctypes
from ctypes.util import find_library
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True, slots=True)
class StitchInterval:
    start_time_us: int
    end_time_us: int
    value: int


@dataclass(frozen=True, slots=True)
class StitchPoint:
    time_us: int
    value: int


class _NativeInterval(ctypes.Structure):
    _fields_ = [
        ("start_time_us", ctypes.c_int64),
        ("end_time_us", ctypes.c_int64),
        ("value", ctypes.c_int32),
    ]


class _NativePoint(ctypes.Structure):
    _fields_ = [
        ("time_us", ctypes.c_int64),
        ("value", ctypes.c_int32),
    ]


_UNSET = object()
_LIB_HANDLE: ctypes.CDLL | object = _UNSET


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _candidate_library_paths() -> list[str]:
    names = (
        "libnatkit-core.so",
        "libnatkit-core.dylib",
        "libnatkit-core.dll",
        "liblibnatkit-core.so",
        "liblibnatkit-core.dylib",
        "liblibnatkit-core.dll",
    )
    candidates: list[str] = []

    env_path = os.environ.get("LIBNATKIT_CORE_PATH")
    if env_path:
        candidates.append(env_path)

    build_root = _repo_root() / "libnatkit" / "lib" / "libnatkit-core" / "build"
    for name in names:
        candidates.extend(
            [
                str(build_root / name),
                str(build_root / "Debug" / name),
                str(build_root / "Release" / name),
                str(build_root / "RelWithDebInfo" / name),
            ]
        )

    system_name = find_library("natkit-core")
    if system_name:
        candidates.append(system_name)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
    return deduped


def find_libnatkit_core() -> str | None:
    for candidate in _candidate_library_paths():
        if Path(candidate).exists() or os.path.sep not in candidate:
            return candidate
    return None


def _load_library() -> ctypes.CDLL:
    global _LIB_HANDLE
    if _LIB_HANDLE is not _UNSET:
        return _LIB_HANDLE
    path = find_libnatkit_core()
    if path is None:
        raise FileNotFoundError(
            "libnatkit-core shared library not found. Set LIBNATKIT_CORE_PATH or build libnatkit/lib/libnatkit-core."
        )
    handle = ctypes.CDLL(str(path))
    handle.nat_assign_intervals_to_timeline.argtypes = [
        ctypes.POINTER(ctypes.c_int64),
        ctypes.c_size_t,
        ctypes.POINTER(_NativeInterval),
        ctypes.c_size_t,
        ctypes.c_int32,
        ctypes.POINTER(ctypes.c_int32),
    ]
    handle.nat_assign_intervals_to_timeline.restype = ctypes.c_int
    handle.nat_assign_points_to_timeline.argtypes = [
        ctypes.POINTER(ctypes.c_int64),
        ctypes.c_size_t,
        ctypes.POINTER(_NativePoint),
        ctypes.c_size_t,
        ctypes.c_int32,
        ctypes.POINTER(ctypes.c_int32),
    ]
    handle.nat_assign_points_to_timeline.restype = ctypes.c_int
    handle.nat_sort_timestamps.argtypes = [
        ctypes.POINTER(ctypes.c_int64),
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    handle.nat_sort_timestamps.restype = ctypes.c_int
    _LIB_HANDLE = handle
    return handle


def stitch_interval_values(
    timestamps_us: Sequence[int],
    intervals: Sequence[StitchInterval],
    *,
    fill_value: int = -1,
) -> list[int]:
    if not timestamps_us:
        return []
    if not intervals:
        return [int(fill_value)] * len(timestamps_us)

    handle = _load_library()

    timestamp_array = (ctypes.c_int64 * len(timestamps_us))(
        *(int(timestamp) for timestamp in timestamps_us)
    )
    interval_array = (_NativeInterval * len(intervals))(
        *[
            _NativeInterval(
                int(interval.start_time_us),
                int(interval.end_time_us),
                int(interval.value),
            )
            for interval in intervals
        ]
    )
    output_array = (ctypes.c_int32 * len(timestamps_us))()

    status = handle.nat_assign_intervals_to_timeline(
        timestamp_array,
        len(timestamps_us),
        interval_array,
        len(intervals),
        int(fill_value),
        output_array,
    )
    if status != 0:
        raise RuntimeError(f"libnatkit interval stitching failed with status {status}")
    return [int(output_array[index]) for index in range(len(timestamps_us))]


def stitch_point_values(
    timestamps_us: Sequence[int],
    points: Sequence[StitchPoint],
    *,
    fill_value: int = -1,
) -> list[int]:
    if not timestamps_us:
        return []
    if not points:
        return [int(fill_value)] * len(timestamps_us)

    handle = _load_library()

    timestamp_array = (ctypes.c_int64 * len(timestamps_us))(
        *(int(timestamp) for timestamp in timestamps_us)
    )
    point_array = (_NativePoint * len(points))(
        *[
            _NativePoint(
                int(point.time_us),
                int(point.value),
            )
            for point in points
        ]
    )
    output_array = (ctypes.c_int32 * len(timestamps_us))()

    status = handle.nat_assign_points_to_timeline(
        timestamp_array,
        len(timestamps_us),
        point_array,
        len(points),
        int(fill_value),
        output_array,
    )
    if status != 0:
        raise RuntimeError(f"libnatkit point stitching failed with status {status}")
    return [int(output_array[index]) for index in range(len(timestamps_us))]


def sort_timestamp_order(timestamps_us: Sequence[int]) -> list[int]:
    if not timestamps_us:
        return []

    handle = _load_library()
    timestamp_array = (ctypes.c_int64 * len(timestamps_us))(
        *(int(timestamp) for timestamp in timestamps_us)
    )
    output_array = (ctypes.c_uint32 * len(timestamps_us))()

    status = handle.nat_sort_timestamps(
        timestamp_array,
        len(timestamps_us),
        output_array,
    )
    if status != 0:
        raise RuntimeError(f"libnatkit timestamp sort failed with status {status}")
    return [int(output_array[index]) for index in range(len(timestamps_us))]
