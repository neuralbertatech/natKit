from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from typing import Any

from natvr.calibration import build_calibration_profile, load_feature_vectors, normalize_feature_vector
from natvr.features import WindowedFeatureVector
from natvr.model import train_lda, vector_to_flat_features


def confusion_matrix(
    truth: list[str],
    predicted: list[str],
) -> dict[str, dict[str, int]]:
    labels = sorted(set(truth) | set(predicted))
    matrix = {label: {pred: 0 for pred in labels} for label in labels}
    for true_label, predicted_label in zip(truth, predicted, strict=True):
        matrix[true_label][predicted_label] += 1
    return matrix


def session_split(
    vectors: list[WindowedFeatureVector],
) -> dict[str, list[WindowedFeatureVector]]:
    grouped: dict[str, list[WindowedFeatureVector]] = defaultdict(list)
    for vector in vectors:
        if not vector.session_id:
            raise ValueError("all vectors must have a session_id for session split")
        grouped[vector.session_id].append(vector)
    return grouped


def build_dataset(
    paths: list[Path],
    *,
    normalize: bool = True,
    rest_gesture: str = "rest",
    active_gesture: str = "fist",
) -> list[WindowedFeatureVector]:
    vectors: list[WindowedFeatureVector] = []
    for path in paths:
        session_vectors = [
            vector for vector in load_feature_vectors(path)
            if vector.gesture
            and (
                vector.phase == "hold"
                or str(vector.gesture) == rest_gesture
            )
        ]
        if normalize and session_vectors:
            profile = build_calibration_profile(
                session_vectors,
                rest_gesture=rest_gesture,
                active_gesture=active_gesture,
            )
            session_vectors = [normalize_feature_vector(vector, profile) for vector in session_vectors]
        vectors.extend(session_vectors)
    return vectors


def evaluate_leave_one_session_out(
    vectors: list[WindowedFeatureVector],
) -> dict[str, Any]:
    by_session = session_split(vectors)
    sessions = sorted(by_session)
    all_truth: list[str] = []
    all_pred: list[str] = []
    per_session: dict[str, Any] = {}
    for held_out in sessions:
        train_vectors = [
            vector
            for session_id, items in by_session.items()
            if session_id != held_out
            for vector in items
            if vector.gesture
        ]
        test_vectors = [vector for vector in by_session[held_out] if vector.gesture]
        if not train_vectors or not test_vectors:
            continue
        model = train_lda([(vector_to_flat_features(vector), str(vector.gesture)) for vector in train_vectors])
        truth = [str(vector.gesture) for vector in test_vectors]
        predicted = [model.predict_one(vector_to_flat_features(vector)) for vector in test_vectors]
        all_truth.extend(truth)
        all_pred.extend(predicted)
        correct = sum(1 for t, p in zip(truth, predicted, strict=True) if t == p)
        per_session[held_out] = {
            "samples": len(truth),
            "accuracy": correct / len(truth),
            "confusion_matrix": confusion_matrix(truth, predicted),
        }
    overall_correct = sum(1 for t, p in zip(all_truth, all_pred, strict=True) if t == p)
    return {
        "sessions": per_session,
        "overall_samples": len(all_truth),
        "overall_accuracy": (overall_correct / len(all_truth)) if all_truth else 0.0,
        "overall_confusion_matrix": confusion_matrix(all_truth, all_pred) if all_truth else {},
    }


def build_report_output_path(first_path: Path) -> Path:
    return first_path.parent / "baseline-report.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a session-split baseline LDA evaluation over feature JSONL files."
    )
    parser.add_argument("feature_paths", nargs="+")
    parser.add_argument("--no-normalize", action="store_true")
    parser.add_argument("--rest-gesture", default="rest")
    parser.add_argument("--active-gesture", default="fist")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    paths = [Path(path) for path in args.feature_paths]
    vectors = build_dataset(
        paths,
        normalize=not args.no_normalize,
        rest_gesture=args.rest_gesture,
        active_gesture=args.active_gesture,
    )
    report = evaluate_leave_one_session_out(vectors)
    output_path = build_report_output_path(paths[0])
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote baseline report to {output_path}")
