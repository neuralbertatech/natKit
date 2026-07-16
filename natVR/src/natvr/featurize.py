from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from natvr._optional import require_pyarrow
from natvr.dsp import preprocess_channel
from natvr.features import WindowedFeatureVector, extract_hudgins_features
from natvr.markers import (
    annotate_rows_with_cue_markers,
    annotate_rows_with_marker_stream,
    annotate_rows_with_marker_type,
    load_cue_file_markers,
    load_marker_jsonl,
)


def load_rows(
    parquet_path: Path,
    *,
    marker_path: Path | None = None,
    marker_type: str | None = None,
    field_prefix: str | None = None,
    time_key: str = "device_ts_us",
) -> list[dict[str, Any]]:
    _, pq = require_pyarrow()
    rows = pq.read_table(parquet_path).to_pylist()
    if marker_path is None:
        return rows

    if marker_path.name.endswith(".cues.json"):
        markers = load_cue_file_markers(marker_path)
    else:
        markers = load_marker_jsonl(marker_path)

    detected_marker_types = {marker.marker_type for marker in markers}
    if marker_type == "cue" and field_prefix in (None, "cue"):
        return annotate_rows_with_cue_markers(rows, markers, time_key=time_key)
    if marker_type:
        return annotate_rows_with_marker_type(
            rows,
            markers,
            marker_type=marker_type,
            time_key=time_key,
            field_prefix=field_prefix,
        )
    if detected_marker_types == {"cue"}:
        return annotate_rows_with_cue_markers(rows, markers, time_key=time_key)
    return annotate_rows_with_marker_stream(rows, markers, time_key=time_key)


def build_feature_output_path(parquet_path: Path) -> Path:
    return parquet_path.with_suffix("").with_suffix(".features.jsonl")


def infer_session_id(parquet_path: Path) -> str:
    stem = parquet_path.stem
    return stem.split("__", 1)[0]


def select_channel_indexes(
    channel_count: int,
    selected_channel_indexes: list[int] | tuple[int, ...] | None,
) -> list[int]:
    if selected_channel_indexes is None:
        return list(range(channel_count))
    indexes = sorted(set(int(index) for index in selected_channel_indexes))
    if any(index < 0 or index >= channel_count for index in indexes):
        raise ValueError(
            f"selected channel indexes {indexes} exceed available channel count {channel_count}"
        )
    return indexes


def rows_to_sample_stream(
    rows: list[dict[str, Any]],
    *,
    selected_channel_indexes: list[int] | tuple[int, ...] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    if not rows:
        return [], 0
    sample_rate_hz = int(rows[0]["sample_rate_hz"])
    stream: list[dict[str, Any]] = []
    for row in rows:
        channel_count = int(row["n_channels"])
        sample_count = int(row["samples_per_channel"])
        channel_indexes = select_channel_indexes(channel_count, selected_channel_indexes)
        channels = {
            idx: [int(sample) for sample in row[f"channel_{idx}"]]
            for idx in channel_indexes
        }
        gesture = row.get("cue_gesture")
        phase = row.get("cue_phase")
        frame_start_ts = int(row["device_ts_us"])
        for sample_idx in range(sample_count):
            stream.append(
                {
                    "ts_us": frame_start_ts + int(sample_idx * 1_000_000 / sample_rate_hz),
                    "gesture": gesture,
                    "phase": phase,
                    "values": tuple(channels[idx][sample_idx] for idx in channel_indexes),
                }
            )
    return stream, sample_rate_hz


def majority_label(samples: list[dict[str, Any]], key: str) -> str | None:
    counts = Counter(sample.get(key) for sample in samples if sample.get(key))
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def window_feature_vectors(
    stream: list[dict[str, Any]],
    *,
    sample_rate_hz: int,
    session_id: str | None = None,
    window_ms: int = 200,
    hop_ms: int = 50,
    notch_base_hz: float = 60.0,
    notch_harmonics: int = 3,
    highpass_hz: float | None = 20.0,
    rectify_signal: bool = False,
) -> list[WindowedFeatureVector]:
    if not stream:
        return []
    window_samples = max(1, int(round(sample_rate_hz * window_ms / 1000.0)))
    hop_samples = max(1, int(round(sample_rate_hz * hop_ms / 1000.0)))
    channel_count = len(stream[0]["values"])
    output: list[WindowedFeatureVector] = []
    for start in range(0, len(stream) - window_samples + 1, hop_samples):
        chunk = stream[start : start + window_samples]
        processed_channels = []
        for channel_idx in range(channel_count):
            raw_channel = [float(point["values"][channel_idx]) for point in chunk]
            processed = preprocess_channel(
                raw_channel,
                sample_rate_hz=sample_rate_hz,
                notch_base_hz=notch_base_hz,
                notch_harmonics=notch_harmonics,
                highpass_hz=highpass_hz,
                rectify_signal=rectify_signal,
                envelope_window_samples=None,
            )
            processed_channels.append(extract_hudgins_features(processed))
        output.append(
            WindowedFeatureVector(
                session_id=session_id,
                gesture=majority_label(chunk, "gesture"),
                phase=majority_label(chunk, "phase"),
                start_ts_us=int(chunk[0]["ts_us"]),
                end_ts_us=int(chunk[-1]["ts_us"]),
                channel_features=tuple(processed_channels),
            )
        )
    return output


def write_feature_vectors(path: Path, vectors: list[WindowedFeatureVector]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for vector in vectors:
            handle.write(json.dumps(vector.to_dict()) + "\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a recorded EMG Parquet session into windowed Hudgins features."
    )
    parser.add_argument("parquet_path")
    parser.add_argument("--marker-path")
    parser.add_argument("--marker-type")
    parser.add_argument("--field-prefix")
    parser.add_argument("--window-ms", type=int, default=200)
    parser.add_argument("--hop-ms", type=int, default=50)
    parser.add_argument("--notch-base-hz", type=float, default=60.0)
    parser.add_argument("--notch-harmonics", type=int, default=3)
    parser.add_argument("--highpass-hz", type=float, default=20.0)
    parser.add_argument("--no-highpass", action="store_true")
    parser.add_argument("--rectify", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    parquet_path = Path(args.parquet_path)
    rows = load_rows(
        parquet_path,
        marker_path=Path(args.marker_path) if args.marker_path else None,
        marker_type=args.marker_type,
        field_prefix=args.field_prefix,
    )
    stream, sample_rate_hz = rows_to_sample_stream(rows)
    vectors = window_feature_vectors(
        stream,
        sample_rate_hz=sample_rate_hz,
        session_id=infer_session_id(parquet_path),
        window_ms=args.window_ms,
        hop_ms=args.hop_ms,
        notch_base_hz=args.notch_base_hz,
        notch_harmonics=args.notch_harmonics,
        highpass_hz=None if args.no_highpass else args.highpass_hz,
        rectify_signal=args.rectify,
    )
    output_path = build_feature_output_path(parquet_path)
    write_feature_vectors(output_path, vectors)
    print(f"Wrote {len(vectors)} feature windows to {output_path}")
