from __future__ import annotations

import argparse
import json
from pathlib import Path

from natvr.baseline import build_dataset, evaluate_leave_one_session_out
from natvr.features import WindowedFeatureVector


def parse_channel_counts(raw: str) -> list[int]:
    counts = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not counts:
        raise ValueError("channel counts must not be empty")
    if any(count <= 0 for count in counts):
        raise ValueError("channel counts must be positive integers")
    return counts


def limit_channels(
    vector: WindowedFeatureVector,
    *,
    channel_count: int,
) -> WindowedFeatureVector:
    if channel_count > len(vector.channel_features):
        raise ValueError("channel_count exceeds available channels")
    return WindowedFeatureVector(
        session_id=vector.session_id,
        gesture=vector.gesture,
        phase=vector.phase,
        start_ts_us=vector.start_ts_us,
        end_ts_us=vector.end_ts_us,
        channel_features=vector.channel_features[:channel_count],
    )


def run_channel_ablation(
    paths: list[Path],
    *,
    channel_counts: list[int],
    normalize: bool = True,
    rest_gesture: str = "rest",
    active_gesture: str = "fist",
) -> dict[str, object]:
    dataset = build_dataset(
        paths,
        normalize=normalize,
        rest_gesture=rest_gesture,
        active_gesture=active_gesture,
    )
    if not dataset:
        raise ValueError("no feature vectors loaded")
    available_channels = len(dataset[0].channel_features)
    report: dict[str, object] = {
        "available_channels": available_channels,
        "evaluated_channel_counts": [],
        "results": {},
    }
    evaluated: list[int] = []
    for channel_count in channel_counts:
        if channel_count > available_channels:
            continue
        trimmed = [limit_channels(vector, channel_count=channel_count) for vector in dataset]
        report["results"][str(channel_count)] = evaluate_leave_one_session_out(trimmed)  # type: ignore[index]
        evaluated.append(channel_count)
    report["evaluated_channel_counts"] = evaluated
    return report


def build_ablation_output_path(first_path: Path) -> Path:
    return first_path.parent / "channel-ablation.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a session-split channel-count ablation over feature JSONL files."
    )
    parser.add_argument("feature_paths", nargs="+")
    parser.add_argument("--channel-counts", default="2,4,6")
    parser.add_argument("--no-normalize", action="store_true")
    parser.add_argument("--rest-gesture", default="rest")
    parser.add_argument("--active-gesture", default="fist")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    paths = [Path(path) for path in args.feature_paths]
    report = run_channel_ablation(
        paths,
        channel_counts=parse_channel_counts(args.channel_counts),
        normalize=not args.no_normalize,
        rest_gesture=args.rest_gesture,
        active_gesture=args.active_gesture,
    )
    output_path = build_ablation_output_path(paths[0])
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote channel ablation report to {output_path}")
