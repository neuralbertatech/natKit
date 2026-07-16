from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any

from natvr.featurize import load_rows


@dataclass(frozen=True, slots=True)
class FrameFeatures:
    cue_gesture: str
    cue_phase: str | None
    device_ts_us: int
    channel_rms: tuple[float, ...]
    channel_mav: tuple[float, ...]


def rms(samples: list[int] | tuple[int, ...]) -> float:
    if not samples:
        return 0.0
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


def mav(samples: list[int] | tuple[int, ...]) -> float:
    if not samples:
        return 0.0
    return sum(abs(sample) for sample in samples) / len(samples)


def row_to_features(row: dict[str, Any]) -> FrameFeatures | None:
    gesture = row.get("cue_gesture")
    if not gesture or gesture == "rest" and row.get("cue_phase") not in {"hold", "rest"}:
        return None
    channel_count = int(row["n_channels"])
    rms_values = []
    mav_values = []
    for idx in range(channel_count):
        channel = tuple(int(sample) for sample in row[f"channel_{idx}"])
        rms_values.append(rms(channel))
        mav_values.append(mav(channel))
    return FrameFeatures(
        cue_gesture=str(gesture),
        cue_phase=(str(row["cue_phase"]) if row.get("cue_phase") is not None else None),
        device_ts_us=int(row["device_ts_us"]),
        channel_rms=tuple(rms_values),
        channel_mav=tuple(mav_values),
    )


def load_feature_rows(
    parquet_path: Path,
    *,
    marker_path: Path | None = None,
    marker_type: str | None = None,
    field_prefix: str | None = None,
) -> list[FrameFeatures]:
    features: list[FrameFeatures] = []
    for row in load_rows(
        parquet_path,
        marker_path=marker_path,
        marker_type=marker_type,
        field_prefix=field_prefix,
    ):
        feature = row_to_features(row)
        if feature is not None:
            features.append(feature)
    return features


def summarize_features(
    features: list[FrameFeatures],
    *,
    hold_only: bool = True,
) -> dict[str, Any]:
    filtered = [
        feature
        for feature in features
        if not hold_only or feature.cue_phase == "hold"
    ]
    by_gesture: dict[str, list[FrameFeatures]] = defaultdict(list)
    for feature in filtered:
        by_gesture[feature.cue_gesture].append(feature)

    channel_count = len(filtered[0].channel_rms) if filtered else 0
    gestures_summary: dict[str, Any] = {}
    for gesture, items in sorted(by_gesture.items()):
        gestures_summary[gesture] = {
            "frames": len(items),
            "mean_rms": [
                mean(feature.channel_rms[idx] for feature in items)
                for idx in range(channel_count)
            ],
            "mean_mav": [
                mean(feature.channel_mav[idx] for feature in items)
                for idx in range(channel_count)
            ],
        }

    separability = {}
    if "rest" in gestures_summary:
        rest_means = gestures_summary["rest"]["mean_rms"]
        for gesture, summary in gestures_summary.items():
            if gesture == "rest":
                continue
            separability[gesture] = [
                summary["mean_rms"][idx] - rest_means[idx]
                for idx in range(channel_count)
            ]

    return {
        "frames_considered": len(filtered),
        "channel_count": channel_count,
        "gestures": gestures_summary,
        "rest_delta_rms": separability,
    }


def render_rms_scatter_svg(
    features: list[FrameFeatures],
    *,
    channel_x: int = 0,
    channel_y: int = 1,
    hold_only: bool = True,
    width: int = 800,
    height: int = 520,
) -> str:
    filtered = [
        feature
        for feature in features
        if (not hold_only or feature.cue_phase == "hold")
        and len(feature.channel_rms) > max(channel_x, channel_y)
    ]
    if not filtered:
        raise ValueError("no features available for scatter plot")

    palette = {
        "rest": "#64748b",
        "fist": "#0f766e",
        "open": "#b45309",
        "pinch": "#2563eb",
        "point": "#7c3aed",
        "thumbs_up": "#c2410c",
    }
    pad_left = 72
    pad_right = 28
    pad_top = 28
    pad_bottom = 56
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom
    xs = [feature.channel_rms[channel_x] for feature in filtered]
    ys = [feature.channel_rms[channel_y] for feature in filtered]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if min_x == max_x:
        max_x += 1.0
    if min_y == max_y:
        max_y += 1.0

    def sx(value: float) -> float:
        return pad_left + (value - min_x) / (max_x - min_x) * plot_w

    def sy(value: float) -> float:
        return height - pad_bottom - (value - min_y) / (max_y - min_y) * plot_h

    circles = []
    for feature in filtered:
        circles.append(
            f'<circle cx="{sx(feature.channel_rms[channel_x]):.2f}" '
            f'cy="{sy(feature.channel_rms[channel_y]):.2f}" r="4" '
            f'fill="{palette.get(feature.cue_gesture, "#334155")}" fill-opacity="0.72" />'
        )

    legend_rows = []
    for idx, gesture in enumerate(sorted({feature.cue_gesture for feature in filtered})):
        y = pad_top + idx * 20
        legend_rows.append(
            f'<circle cx="{width - 140}" cy="{y}" r="5" fill="{palette.get(gesture, "#334155")}" />'
            f'<text x="{width - 126}" y="{y + 4}" font-size="12" fill="#16211C">{gesture}</text>'
        )

    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="#F4F7F5" />',
            f'<rect x="{pad_left}" y="{pad_top}" width="{plot_w}" height="{plot_h}" fill="#FFFFFF" stroke="#D9E1DC" />',
            f'<line x1="{pad_left}" y1="{height - pad_bottom}" x2="{width - pad_right}" y2="{height - pad_bottom}" stroke="#94A3B8" />',
            f'<line x1="{pad_left}" y1="{pad_top}" x2="{pad_left}" y2="{height - pad_bottom}" stroke="#94A3B8" />',
            f'<text x="{width / 2:.0f}" y="20" text-anchor="middle" font-size="16" fill="#16211C">RMS separability scatter</text>',
            f'<text x="{width / 2:.0f}" y="{height - 16}" text-anchor="middle" font-size="13" fill="#334155">channel {channel_x} RMS</text>',
            f'<text x="20" y="{height / 2:.0f}" transform="rotate(-90 20 {height / 2:.0f})" text-anchor="middle" font-size="13" fill="#334155">channel {channel_y} RMS</text>',
            f'<text x="{pad_left}" y="{height - pad_bottom + 22}" font-size="11" fill="#475569">{min_x:.2f}</text>',
            f'<text x="{width - pad_right}" y="{height - pad_bottom + 22}" text-anchor="end" font-size="11" fill="#475569">{max_x:.2f}</text>',
            f'<text x="{pad_left - 10}" y="{height - pad_bottom}" text-anchor="end" font-size="11" fill="#475569">{min_y:.2f}</text>',
            f'<text x="{pad_left - 10}" y="{pad_top + 4}" text-anchor="end" font-size="11" fill="#475569">{max_y:.2f}</text>',
            *circles,
            *legend_rows,
            "</svg>",
        ]
    )


def build_analysis_output_paths(parquet_path: Path) -> tuple[Path, Path]:
    stem = parquet_path.with_suffix("")
    return Path(f"{stem}.summary.json"), Path(f"{stem}.scatter.svg")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize EMG capture separability from a recorded Parquet session."
    )
    parser.add_argument("parquet_path")
    parser.add_argument("--marker-path")
    parser.add_argument("--marker-type")
    parser.add_argument("--field-prefix")
    parser.add_argument("--channel-x", type=int, default=0)
    parser.add_argument("--channel-y", type=int, default=1)
    parser.add_argument("--include-rest-phases", action="store_true")
    parser.add_argument("--skip-scatter", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    parquet_path = Path(args.parquet_path)
    features = load_feature_rows(
        parquet_path,
        marker_path=Path(args.marker_path) if args.marker_path else None,
        marker_type=args.marker_type,
        field_prefix=args.field_prefix,
    )
    summary = summarize_features(
        features,
        hold_only=not args.include_rest_phases,
    )
    summary_path, scatter_path = build_analysis_output_paths(parquet_path)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if not args.skip_scatter:
        scatter_svg = render_rms_scatter_svg(
            features,
            channel_x=args.channel_x,
            channel_y=args.channel_y,
            hold_only=not args.include_rest_phases,
        )
        scatter_path.write_text(scatter_svg + "\n", encoding="utf-8")
    print(f"Wrote analysis summary to {summary_path}")
    if not args.skip_scatter:
        print(f"Wrote scatter plot to {scatter_path}")
