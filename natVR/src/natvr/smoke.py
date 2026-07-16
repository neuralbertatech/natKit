from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from natvr.baseline import build_report_output_path
from natvr.calibration import build_calibration_output_path
from natvr.channel_ablation import parse_channel_counts, run_channel_ablation
from natvr.featurize import build_feature_output_path, main as featurize_main
from natvr.guided_calibration import write_guided_calibration_outputs
from natvr.predictor import build_model_output_path
from natvr.replay_eval import evaluate_replay_session
from natvr.select_model import evaluate_model_families
from natvr.synthetic import write_synthetic_session
from natvr.train_model import main as train_main
from natvr.baseline import main as baseline_main


def build_smoke_summary_output_path(output_dir: Path) -> Path:
    return output_dir / "smoke-summary.json"


def run_smoke_pipeline(
    *,
    output_dir: Path,
    device_id: str = "sim01",
    gestures: list[str] | None = None,
    channel_counts: list[int] | None = None,
) -> dict[str, Any]:
    gestures = gestures or ["rest", "fist", "point", "pinch", "open"]
    channel_counts = channel_counts or [1, 2]

    session_ids = ["sim-a", "sim-b"]
    parquet_paths: list[Path] = []
    for session_id in session_ids:
        parquet_path, _ = write_synthetic_session(
            output_dir=output_dir,
            session_id=session_id,
            device_id=device_id,
            gestures=gestures,
        )
        parquet_paths.append(parquet_path)
        featurize_main([str(parquet_path)])

    feature_paths = [build_feature_output_path(path) for path in parquet_paths]
    train_main([str(path) for path in feature_paths])
    baseline_main([str(path) for path in feature_paths])
    replay_selection = evaluate_model_families(
        feature_paths,
        [parquet_paths[0]],
        vote_windows=1,
        min_hold_windows=1,
        confidence_threshold=0.0,
    )

    global_model_path = build_model_output_path(feature_paths[0], "lda")
    calibration_path = build_calibration_output_path(feature_paths[0])
    # Rebuild the explicit calibration profile for the replay session.
    from natvr.calibration import main as calibration_main

    calibration_main([str(feature_paths[0])])

    global_replay_report = evaluate_replay_session(
        parquet_paths[0],
        session_id="smoke-global",
        model_path=global_model_path,
        calibration_path=calibration_path,
        vote_windows=1,
        min_hold_windows=1,
        confidence_threshold=0.0,
    )

    guided_manifest = write_guided_calibration_outputs(
        parquet_paths[0],
        active_gesture="fist",
        train_feature_paths=[feature_paths[1]],
    )
    guided_replay_report = evaluate_replay_session(
        parquet_paths[0],
        session_id="smoke-guided",
        model_path=Path(str(guided_manifest["model_path"])),
        calibration_path=Path(str(guided_manifest["calibration_path"])),
        vote_windows=1,
        min_hold_windows=1,
        confidence_threshold=0.0,
    )

    ablation_report = run_channel_ablation(
        feature_paths,
        channel_counts=channel_counts,
    )
    baseline_report = json.loads(build_report_output_path(feature_paths[0]).read_text(encoding="utf-8"))
    summary = {
        "output_dir": str(output_dir),
        "device_id": device_id,
        "gestures": gestures,
        "parquet_paths": [str(path) for path in parquet_paths],
        "feature_paths": [str(path) for path in feature_paths],
        "replay_selection": replay_selection,
        "selected_model_family": replay_selection["selected_family"],
        "selected_model_path": replay_selection["selected_model_path"],
        "global_model_path": str(global_model_path),
        "global_replay_eval": global_replay_report,
        "guided_manifest": guided_manifest,
        "guided_replay_eval": guided_replay_report,
        "baseline_report": baseline_report,
        "channel_ablation": ablation_report,
    }
    summary_path = build_smoke_summary_output_path(output_dir)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the deterministic synthetic EMG smoke pipeline and write a summary report."
    )
    parser.add_argument("--output-dir", default="captures/smoke")
    parser.add_argument("--device-id", default="sim01")
    parser.add_argument("--gestures", default="rest,fist,point,pinch,open")
    parser.add_argument("--channel-counts", default="1,2")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    summary = run_smoke_pipeline(
        output_dir=Path(args.output_dir),
        device_id=args.device_id,
        gestures=[gesture.strip() for gesture in args.gestures.split(",") if gesture.strip()],
        channel_counts=parse_channel_counts(args.channel_counts),
    )
    print(
        "Wrote smoke summary to "
        f"{build_smoke_summary_output_path(Path(args.output_dir))} "
        f"(selected={summary['selected_model_family']} "
        f"acc={summary['replay_selection']['selected_mean_accuracy']:.3f}, "
        f"global lda replay acc={summary['global_replay_eval']['accuracy']:.3f}, "
        f"guided replay acc={summary['guided_replay_eval']['accuracy']:.3f})"
    )
