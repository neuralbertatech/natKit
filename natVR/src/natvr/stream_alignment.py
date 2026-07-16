from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from natvr.libnatkit_stitch import StitchPoint, sort_timestamp_order, stitch_point_values


@dataclass(frozen=True, slots=True)
class TimestampedValue:
    timestamp_us: int
    value: int


def align_latest_points_python(
    timestamps_us: Sequence[int],
    points: Sequence[TimestampedValue],
    *,
    fill_value: int = -1,
) -> list[int]:
    assignments = [int(fill_value)] * len(timestamps_us)
    if not timestamps_us or not points:
        return assignments

    indexed_timestamps = sorted(
        enumerate(int(timestamp) for timestamp in timestamps_us),
        key=lambda item: item[1],
    )
    ordered_points = sorted(
        points,
        key=lambda point: (int(point.timestamp_us), int(point.value)),
    )

    point_index = 0
    active_value = int(fill_value)
    has_active_value = False

    for output_index, timestamp_us in indexed_timestamps:
        while (
            point_index < len(ordered_points)
            and int(ordered_points[point_index].timestamp_us) <= timestamp_us
        ):
            active_value = int(ordered_points[point_index].value)
            has_active_value = True
            point_index += 1
        if has_active_value:
            assignments[output_index] = active_value

    return assignments


def assign_latest_points(
    timestamps_us: Sequence[int],
    points: Sequence[TimestampedValue],
    *,
    fill_value: int = -1,
) -> list[int]:
    native_points = [
        StitchPoint(time_us=int(point.timestamp_us), value=int(point.value))
        for point in points
    ]
    try:
        return stitch_point_values(
            timestamps_us,
            native_points,
            fill_value=fill_value,
        )
    except (FileNotFoundError, OSError, RuntimeError):
        return align_latest_points_python(
            timestamps_us,
            points,
            fill_value=fill_value,
        )


def annotate_rows_with_latest_value(
    rows: Sequence[Mapping[str, Any]],
    points: Sequence[TimestampedValue],
    *,
    time_key: str = "device_ts_us",
    output_field: str = "aligned_value",
    fill_value: int | None = None,
) -> list[dict[str, Any]]:
    if not rows:
        return []

    ordered_rows = sorted(
        (dict(row) for row in rows),
        key=lambda row: int(row.get(time_key) or row["device_ts_us"]),
    )
    row_timestamps_us = [
        int(row.get(time_key) or row["device_ts_us"]) for row in ordered_rows
    ]
    fallback_value = -1 if fill_value is None else int(fill_value)
    assignments = assign_latest_points(
        row_timestamps_us,
        points,
        fill_value=fallback_value,
    )

    annotated: list[dict[str, Any]] = []
    for row, assignment in zip(ordered_rows, assignments):
        next_row = dict(row)
        if fill_value is None and assignment == -1:
            annotated.append(next_row)
            continue
        next_row[output_field] = assignment
        annotated.append(next_row)
    return annotated


def interleave_timestamped_streams(
    streams: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    time_key: str = "device_ts_us",
) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    timestamps_us: list[int] = []

    for stream_name, rows in streams.items():
        for stream_index, row in enumerate(rows):
            next_row = dict(row)
            next_row["stream_name"] = stream_name
            next_row["stream_index"] = stream_index
            flattened.append(next_row)
            timestamps_us.append(int(next_row.get(time_key) or next_row["device_ts_us"]))

    if not flattened:
        return []

    try:
        order = sort_timestamp_order(timestamps_us)
    except (FileNotFoundError, OSError, RuntimeError):
        order = sorted(range(len(flattened)), key=lambda index: (timestamps_us[index], index))

    return [flattened[index] for index in order]
