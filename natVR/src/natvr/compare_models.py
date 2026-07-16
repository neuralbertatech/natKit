from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from natvr.baseline import build_dataset, confusion_matrix, session_split
from natvr.features import WindowedFeatureVector
from natvr.model import train_lda, vector_to_flat_features
from natvr.predictor import train_linear_svm, train_random_forest


class LdaPredictor:
    def __init__(self, samples: list[tuple[list[float], str]]) -> None:
        self._model = train_lda(samples)

    def predict(self, features: list[float]) -> str:
        return self._model.predict_one(features)


def predict_label(model: Any, features: list[float]) -> str:
    if hasattr(model, "predict"):
        return str(model.predict(features))
    return str(model.predict_one(features))


def evaluate_model_leave_one_session_out(
    vectors: list[WindowedFeatureVector],
    *,
    trainer: Callable[[list[tuple[list[float], str]]], Any],
) -> dict[str, Any]:
    by_session = session_split(vectors)
    sessions = sorted(by_session)
    all_truth: list[str] = []
    all_predicted: list[str] = []
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
        predictor = trainer(
            [(vector_to_flat_features(vector), str(vector.gesture)) for vector in train_vectors]
        )
        truth = [str(vector.gesture) for vector in test_vectors]
        predicted = [predict_label(predictor, vector_to_flat_features(vector)) for vector in test_vectors]
        all_truth.extend(truth)
        all_predicted.extend(predicted)
        correct = sum(1 for t, p in zip(truth, predicted, strict=True) if t == p)
        per_session[held_out] = {
            "samples": len(truth),
            "accuracy": correct / len(truth),
            "confusion_matrix": confusion_matrix(truth, predicted),
        }
    overall_correct = sum(
        1 for truth, predicted in zip(all_truth, all_predicted, strict=True) if truth == predicted
    )
    return {
        "sessions": per_session,
        "overall_samples": len(all_truth),
        "overall_accuracy": (overall_correct / len(all_truth)) if all_truth else 0.0,
        "overall_confusion_matrix": confusion_matrix(all_truth, all_predicted) if all_truth else {},
    }


def compare_models(vectors: list[WindowedFeatureVector]) -> dict[str, Any]:
    models = {
        "lda": lambda samples: LdaPredictor(samples),
        "linear_svm": train_linear_svm,
        "random_forest": train_random_forest,
    }
    return {
        "models": {
            model_name: evaluate_model_leave_one_session_out(vectors, trainer=trainer)
            for model_name, trainer in models.items()
        }
    }


def build_compare_output_path(first_path: Path) -> Path:
    return first_path.parent / "model-compare-report.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare LDA, linear SVM, and random forest on session-split feature data."
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
    report = compare_models(vectors)
    output_path = build_compare_output_path(paths[0])
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote model comparison report to {output_path}")
