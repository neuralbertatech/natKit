from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from natvr.baseline import build_dataset
from natvr.calibration import (
    build_calibration_output_path,
    build_calibration_profile,
    load_feature_vectors,
    select_calibration_vectors,
)
from natvr.featurize import build_feature_output_path
from natvr.model import train_lda, vector_to_flat_features
from natvr.predictor import build_model_output_path, train_linear_svm, train_random_forest
from natvr.replay_eval import evaluate_replay_session


MODEL_FAMILIES = ("lda", "linear_svm", "random_forest")
FAMILY_PREFERENCE = {
    "linear_svm": 3,
    "lda": 2,
    "random_forest": 1,
}


def build_selection_output_path(first_path: Path) -> Path:
    return first_path.parent / "model-selection-report.json"


def infer_calibration_path(parquet_path: Path) -> Path:
    return build_calibration_output_path(build_feature_output_path(parquet_path))


def ensure_calibration_path(
    parquet_path: Path,
    *,
    rest_gesture: str = "rest",
    active_gesture: str = "fist",
) -> Path:
    calibration_path = infer_calibration_path(parquet_path)
    if calibration_path.exists():
        return calibration_path
    feature_path = build_feature_output_path(parquet_path)
    all_vectors = load_feature_vectors(feature_path)
    try:
        vectors = select_calibration_vectors(all_vectors)
        profile = build_calibration_profile(
            vectors,
            rest_gesture=rest_gesture,
            active_gesture=active_gesture,
        )
    except ValueError:
        fallback_vectors = select_calibration_vectors(all_vectors, phases=None)
        profile = build_calibration_profile(
            fallback_vectors,
            rest_gesture=rest_gesture,
            active_gesture=active_gesture,
        )
    calibration_path.write_text(json.dumps(profile.to_dict(), indent=2) + "\n", encoding="utf-8")
    return calibration_path


def train_model_family(
    feature_paths: list[Path],
    *,
    family: str,
    rest_gesture: str = "rest",
    active_gesture: str = "fist",
) -> Path:
    dataset = build_dataset(
        feature_paths,
        normalize=True,
        rest_gesture=rest_gesture,
        active_gesture=active_gesture,
    )
    samples = [
        (vector_to_flat_features(vector), str(vector.gesture))
        for vector in dataset
        if vector.gesture
    ]
    output_path = build_model_output_path(feature_paths[0], family)
    if family == "lda":
        model = train_lda(samples)
        model.save_json(output_path)
    elif family == "linear_svm":
        model = train_linear_svm(samples)
        model.save_joblib(output_path)
    elif family == "random_forest":
        model = train_random_forest(samples)
        model.save_joblib(output_path)
    else:
        raise ValueError(f"unsupported family {family!r}")
    return output_path


def evaluate_model_family(
    feature_paths: list[Path],
    eval_parquet_paths: list[Path],
    *,
    family: str,
    rest_gesture: str = "rest",
    active_gesture: str = "fist",
    window_ms: int = 200,
    hop_ms: int = 50,
    vote_windows: int = 1,
    confidence_threshold: float = 0.0,
    min_hold_windows: int = 1,
) -> dict[str, Any]:
    model_path = train_model_family(
        feature_paths,
        family=family,
        rest_gesture=rest_gesture,
        active_gesture=active_gesture,
    )
    replay_reports = []
    accuracies: list[float] = []
    coverages: list[float] = []
    for parquet_path in eval_parquet_paths:
        calibration_path = ensure_calibration_path(
            parquet_path,
            rest_gesture=rest_gesture,
            active_gesture=active_gesture,
        )
        report = evaluate_replay_session(
            parquet_path,
            session_id=f"{family}-{parquet_path.stem}",
            model_path=model_path,
            calibration_path=calibration_path,
            window_ms=window_ms,
            hop_ms=hop_ms,
            vote_windows=vote_windows,
            confidence_threshold=confidence_threshold,
            min_hold_windows=min_hold_windows,
        )
        replay_reports.append(report)
        accuracies.append(float(report["accuracy"]))
        coverages.append(float(report["coverage"]))
    return {
        "family": family,
        "model_path": str(model_path),
        "replay_reports": replay_reports,
        "mean_accuracy": (sum(accuracies) / len(accuracies)) if accuracies else 0.0,
        "min_accuracy": min(accuracies) if accuracies else 0.0,
        "mean_coverage": (sum(coverages) / len(coverages)) if coverages else 0.0,
    }


def select_best_model(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        raise ValueError("results must not be empty")
    return max(
        results,
        key=lambda result: (
            float(result["mean_accuracy"]),
            float(result["min_accuracy"]),
            float(result["mean_coverage"]),
            FAMILY_PREFERENCE.get(str(result["family"]), 0),
        ),
    )


def evaluate_model_families(
    feature_paths: list[Path],
    eval_parquet_paths: list[Path],
    *,
    families: list[str] | None = None,
    rest_gesture: str = "rest",
    active_gesture: str = "fist",
    window_ms: int = 200,
    hop_ms: int = 50,
    vote_windows: int = 1,
    confidence_threshold: float = 0.0,
    min_hold_windows: int = 1,
) -> dict[str, Any]:
    families = families or list(MODEL_FAMILIES)
    results = [
        evaluate_model_family(
            feature_paths,
            eval_parquet_paths,
            family=family,
            rest_gesture=rest_gesture,
            active_gesture=active_gesture,
            window_ms=window_ms,
            hop_ms=hop_ms,
            vote_windows=vote_windows,
            confidence_threshold=confidence_threshold,
            min_hold_windows=min_hold_windows,
        )
        for family in families
    ]
    selected = select_best_model(results)
    return {
        "feature_paths": [str(path) for path in feature_paths],
        "eval_parquet_paths": [str(path) for path in eval_parquet_paths],
        "results": results,
        "selected_family": selected["family"],
        "selected_model_path": selected["model_path"],
        "selected_mean_accuracy": selected["mean_accuracy"],
        "selected_min_accuracy": selected["min_accuracy"],
        "selected_mean_coverage": selected["mean_coverage"],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train candidate classifier families and select the best replay-evaluated deployment artifact."
    )
    parser.add_argument("feature_paths", nargs="+")
    parser.add_argument(
        "--eval-parquet",
        action="append",
        dest="eval_parquet_paths",
        required=True,
        help="Repeat for each replay session to score against the candidate artifacts.",
    )
    parser.add_argument(
        "--family",
        action="append",
        choices=MODEL_FAMILIES,
        dest="families",
        help="Optional subset of families to evaluate. Defaults to lda, linear_svm, random_forest.",
    )
    parser.add_argument("--rest-gesture", default="rest")
    parser.add_argument("--active-gesture", default="fist")
    parser.add_argument("--window-ms", type=int, default=200)
    parser.add_argument("--hop-ms", type=int, default=50)
    parser.add_argument("--vote-windows", type=int, default=1)
    parser.add_argument("--confidence-threshold", type=float, default=0.0)
    parser.add_argument("--min-hold-windows", type=int, default=1)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    feature_paths = [Path(path) for path in args.feature_paths]
    report = evaluate_model_families(
        feature_paths,
        [Path(path) for path in args.eval_parquet_paths],
        families=args.families,
        rest_gesture=args.rest_gesture,
        active_gesture=args.active_gesture,
        window_ms=args.window_ms,
        hop_ms=args.hop_ms,
        vote_windows=args.vote_windows,
        confidence_threshold=args.confidence_threshold,
        min_hold_windows=args.min_hold_windows,
    )
    output_path = build_selection_output_path(feature_paths[0])
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote model selection report to {output_path} "
        f"(selected={report['selected_family']} acc={report['selected_mean_accuracy']:.3f})"
    )
