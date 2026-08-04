from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from natvr.libnatkit_stitch import StitchInterval, stitch_interval_values
from natvr.models import MarkerEventV1


_FIELD_NAME_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class MarkerInterval:
    marker: MarkerEventV1
    start_time_us: int
    end_time_us: int


def normalize_marker_field_name(value: str) -> str:
    normalized = _FIELD_NAME_RE.sub("_", value.strip().lower()).strip("_")
    return normalized or "value"


def load_marker_jsonl(path: Path) -> list[MarkerEventV1]:
    markers: list[MarkerEventV1] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        markers.append(MarkerEventV1.from_dict(json.loads(line)))
    return sorted(markers, key=lambda marker: marker.emitted_at_us)


def load_cue_file_markers(path: Path) -> list[MarkerEventV1]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    session_id = str(payload["session_id"])
    markers: list[MarkerEventV1] = []
    for event in payload.get("events", []):
        cue_id = int(event["cue_id"])
        phase = str(event["phase"])
        gesture = str(event["gesture"])
        prompt = str(event["prompt"])
        markers.append(
            MarkerEventV1(
                session_id=session_id,
                marker_type="cue",
                marker_id=f"cue:{cue_id}",
                event="start",
                label=prompt,
                emitted_at_us=int(event["start_ts_us"]),
                attributes={
                    "cue_id": cue_id,
                    "phase": phase,
                    "gesture": gesture,
                    "prompt": prompt,
                    "rep_index": int(event.get("rep_index", -1)),
                },
            )
        )
        markers.append(
            MarkerEventV1(
                session_id=session_id,
                marker_type="cue",
                marker_id=f"cue:{cue_id}",
                event="end",
                label=prompt,
                emitted_at_us=int(event["end_ts_us"]),
                attributes={
                    "cue_id": cue_id,
                    "phase": phase,
                    "gesture": gesture,
                    "prompt": prompt,
                    "rep_index": int(event.get("rep_index", -1)),
                },
            )
        )
    return sorted(markers, key=lambda marker: marker.emitted_at_us)


def write_marker_jsonl(path: Path, markers: list[MarkerEventV1]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for marker in markers:
            handle.write(json.dumps(marker.to_dict()) + "\n")


def build_marker_intervals(
    markers: list[MarkerEventV1],
    *,
    marker_type: str | None = None,
) -> list[MarkerInterval]:
    ordered_markers = sorted(markers, key=lambda marker: marker.emitted_at_us)
    open_markers: dict[str, list[MarkerEventV1]] = {}
    intervals: list[MarkerInterval] = []

    for marker in ordered_markers:
        if marker_type is not None and marker.marker_type != marker_type:
            continue
        if marker.event == "end":
            stack = open_markers.get(marker.marker_id)
            if not stack:
                continue
            start_marker = stack.pop()
            if marker.emitted_at_us < start_marker.emitted_at_us:
                continue
            intervals.append(
                MarkerInterval(
                    marker=start_marker,
                    start_time_us=start_marker.emitted_at_us,
                    end_time_us=marker.emitted_at_us,
                )
            )
            continue
        open_markers.setdefault(marker.marker_id, []).append(marker)

    return intervals


def align_marker_intervals_python(
    timestamps_us: list[int],
    intervals: list[StitchInterval],
    *,
    fill_value: int = -1,
) -> list[int]:
    assignments = [fill_value] * len(timestamps_us)
    if not timestamps_us or not intervals:
        return assignments

    indexed_timestamps = sorted(enumerate(timestamps_us), key=lambda item: item[1])
    ordered_intervals = sorted(
        intervals,
        key=lambda interval: (interval.start_time_us, interval.end_time_us, interval.value),
    )
    active: list[StitchInterval] = []
    interval_index = 0

    for output_index, timestamp_us in indexed_timestamps:
        active = [
            interval for interval in active if interval.end_time_us > timestamp_us
        ]
        while (
            interval_index < len(ordered_intervals)
            and ordered_intervals[interval_index].start_time_us <= timestamp_us
        ):
            interval = ordered_intervals[interval_index]
            if interval.end_time_us > timestamp_us:
                active.append(interval)
            interval_index += 1
        if active:
            assignments[output_index] = int(active[-1].value)

    return assignments


def assign_marker_intervals(
    timestamps_us: list[int],
    intervals: list[MarkerInterval],
) -> list[int]:
    native_intervals = [
        StitchInterval(
            start_time_us=interval.start_time_us,
            end_time_us=interval.end_time_us,
            value=index,
        )
        for index, interval in enumerate(intervals)
    ]
    try:
        return stitch_interval_values(timestamps_us, native_intervals)
    except (FileNotFoundError, OSError, RuntimeError):
        return align_marker_intervals_python(timestamps_us, native_intervals)


def annotate_rows_with_marker_type(
    rows: list[dict[str, Any]],
    markers: list[MarkerEventV1],
    *,
    marker_type: str,
    time_key: str = "device_ts_us",
    field_prefix: str | None = None,
) -> list[dict[str, Any]]:
    if not rows or not markers:
        return [dict(row) for row in rows]

    ordered_rows = sorted(
        rows, key=lambda row: int(row.get(time_key) or row["device_ts_us"])
    )
    marker_intervals = build_marker_intervals(markers, marker_type=marker_type)
    if not marker_intervals:
        return [dict(row) for row in ordered_rows]

    prefix = normalize_marker_field_name(field_prefix or marker_type)
    row_timestamps_us = [
        int(row.get(time_key) or row["device_ts_us"]) for row in ordered_rows
    ]
    assignments = assign_marker_intervals(row_timestamps_us, marker_intervals)

    annotated: list[dict[str, Any]] = []
    for row, assignment in zip(ordered_rows, assignments):
        next_row = dict(row)
        if assignment >= 0:
            interval = marker_intervals[assignment]
            marker = interval.marker
            next_row[f"{prefix}_marker_type"] = marker.marker_type
            next_row[f"{prefix}_marker_id"] = marker.marker_id
            next_row[f"{prefix}_label"] = marker.label
            next_row[f"{prefix}_session_id"] = marker.session_id
            for attr_key, attr_value in marker.attributes.items():
                normalized_key = normalize_marker_field_name(str(attr_key))
                next_row[f"{prefix}_{normalized_key}"] = attr_value
        annotated.append(next_row)

    return annotated


def annotate_rows_with_marker_stream(
    rows: list[dict[str, Any]],
    markers: list[MarkerEventV1],
    *,
    marker_types: list[str] | None = None,
    time_key: str = "device_ts_us",
) -> list[dict[str, Any]]:
    if not rows or not markers:
        return [dict(row) for row in rows]

    selected_marker_types = marker_types or sorted(
        {marker.marker_type for marker in markers}
    )
    annotated = [dict(row) for row in rows]
    for marker_type in selected_marker_types:
        annotated = annotate_rows_with_marker_type(
            annotated,
            markers,
            marker_type=marker_type,
            time_key=time_key,
        )
    return annotated


def annotate_rows_with_cue_markers(
    rows: list[dict[str, Any]],
    markers: list[MarkerEventV1],
    *,
    time_key: str = "device_ts_us",
) -> list[dict[str, Any]]:
    if not rows or not markers:
        return [dict(row) for row in rows]

    ordered_rows = sorted(
        rows, key=lambda row: int(row.get(time_key) or row["device_ts_us"])
    )
    cue_intervals = build_marker_intervals(markers, marker_type="cue")
    if not cue_intervals:
        return [dict(row) for row in ordered_rows]

    row_timestamps_us = [
        int(row.get(time_key) or row["device_ts_us"]) for row in ordered_rows
    ]
    assignments = assign_marker_intervals(row_timestamps_us, cue_intervals)

    annotated: list[dict[str, Any]] = []
    for row, assignment in zip(ordered_rows, assignments):
        next_row = dict(row)
        if assignment >= 0:
            marker = cue_intervals[assignment].marker
            attributes = marker.attributes
            # Tolerate markers that omit the optional display/bookkeeping fields.
            # These used to be direct subscripts, so a timeline missing `prompt` --
            # which nothing in training reads, it is the participant-facing string --
            # killed featurization with a bare KeyError deep in the pipeline. Instance
            # sidecars can come from any producer, so the label fields are the only
            # ones worth being strict about.
            next_row["cue_id"] = int(attributes.get("cue_id") or 0)
            next_row["cue_phase"] = str(attributes.get("phase") or "")
            next_row["cue_gesture"] = str(
                attributes.get("gesture")
                or attributes.get("label")
                or attributes.get("class")
                or ""
            )
            next_row["cue_prompt"] = str(attributes.get("prompt") or "")
            next_row["marker_session_id"] = marker.session_id
        annotated.append(next_row)

    return annotated
