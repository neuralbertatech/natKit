from __future__ import annotations

import argparse
from pathlib import Path

from natvr._optional import require_pyarrow
from natvr.markers import (
    annotate_rows_with_cue_markers,
    annotate_rows_with_marker_stream,
    annotate_rows_with_marker_type,
    load_cue_file_markers,
    load_marker_jsonl,
)


def build_stitched_output_path(parquet_path: Path) -> Path:
    return parquet_path.with_suffix("").with_suffix(".annotated.parquet")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stitch a cue-marker side stream onto raw EMG Parquet rows."
    )
    parser.add_argument("parquet_path")
    parser.add_argument(
        "--marker-path",
        required=True,
        help="Marker JSONL file captured from the cue.marker topic, or a legacy .cues.json file.",
    )
    parser.add_argument("--output-path")
    parser.add_argument(
        "--time-key",
        default="device_ts_us",
        help="Frame timestamp column used for alignment; defaults to device_ts_us.",
    )
    parser.add_argument(
        "--marker-type",
        help="Optional marker_type to stitch. Defaults to cue-specific fields for cue-only streams, otherwise stitches all marker types.",
    )
    parser.add_argument(
        "--field-prefix",
        help="Optional field prefix used with --marker-type for generic marker annotations.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    parquet_path = Path(args.parquet_path)
    marker_path = Path(args.marker_path)
    pa, pq = require_pyarrow()
    rows = pq.read_table(parquet_path).to_pylist()
    if marker_path.name.endswith(".cues.json"):
        markers = load_cue_file_markers(marker_path)
    else:
        markers = load_marker_jsonl(marker_path)
    detected_marker_types = {marker.marker_type for marker in markers}
    if args.marker_type == "cue" and args.field_prefix in (None, "cue"):
        annotated = annotate_rows_with_cue_markers(
            rows,
            markers,
            time_key=args.time_key,
        )
    elif args.marker_type:
        annotated = annotate_rows_with_marker_type(
            rows,
            markers,
            marker_type=args.marker_type,
            time_key=args.time_key,
            field_prefix=args.field_prefix,
        )
    elif detected_marker_types == {"cue"}:
        annotated = annotate_rows_with_cue_markers(
            rows,
            markers,
            time_key=args.time_key,
        )
    else:
        annotated = annotate_rows_with_marker_stream(
            rows,
            markers,
            time_key=args.time_key,
        )
    output_path = (
        Path(args.output_path)
        if args.output_path
        else build_stitched_output_path(parquet_path)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(annotated), output_path)
    print(
        f"Wrote {len(annotated)} annotated rows to {output_path} using {len(markers)} markers across {len(detected_marker_types)} marker types"
    )
