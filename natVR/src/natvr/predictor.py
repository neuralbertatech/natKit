from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Protocol

from natvr._optional import require_sklearn
from natvr.model import LdaModel


class PredictiveModel(Protocol):
    def predict_one(self, features: list[float]) -> str: ...
    def predict_confidence(self, features: list[float]) -> tuple[str, float]: ...


class SklearnPredictorArtifact:
    def __init__(self, *, family: str, model: Any) -> None:
        self.family = family
        self.model = model

    def predict_one(self, features: list[float]) -> str:
        return str(self.model.predict([features])[0])

    def predict_confidence(self, features: list[float]) -> tuple[str, float]:
        predicted = self.predict_one(features)
        if hasattr(self.model, "predict_proba"):
            probabilities = self.model.predict_proba([features])[0]
            labels = getattr(self.model, "classes_", None)
            if labels is not None:
                mapping = {str(label): float(prob) for label, prob in zip(labels, probabilities, strict=True)}
                return predicted, mapping.get(predicted, max(mapping.values(), default=1.0))
        if hasattr(self.model, "decision_function"):
            raw_scores = self.model.decision_function([features])[0]
            labels = getattr(self.model, "classes_", None)
            if labels is not None:
                if hasattr(raw_scores, "tolist"):
                    raw_scores = raw_scores.tolist()
                if not isinstance(raw_scores, (list, tuple)):
                    raw_scores = [float(raw_scores)]
                scores = [float(score) for score in raw_scores]
                max_score = max(scores) if scores else 0.0
                exps = [math.exp(score - max_score) for score in scores]
                denom = sum(exps) or 1.0
                mapping = {
                    str(label): exp / denom
                    for label, exp in zip(labels, exps, strict=True)
                }
                return predicted, mapping.get(predicted, max(mapping.values(), default=1.0))
        return predicted, 1.0

    def save_joblib(self, path: Path) -> None:
        import joblib

        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model_type": "sklearn",
                "family": self.family,
                "model": self.model,
            },
            path,
        )

    @classmethod
    def load_joblib(cls, path: Path) -> "SklearnPredictorArtifact":
        import joblib

        payload = joblib.load(path)
        if payload.get("model_type") != "sklearn":
            raise ValueError("unsupported sklearn model artifact")
        return cls(
            family=str(payload["family"]),
            model=payload["model"],
        )


def train_linear_svm(samples: list[tuple[list[float], str]]) -> SklearnPredictorArtifact:
    RandomForestClassifier, make_pipeline, StandardScaler, LinearSVC = require_sklearn()
    del RandomForestClassifier
    xs = [features for features, _ in samples]
    ys = [label for _, label in samples]
    model = make_pipeline(
        StandardScaler(),
        LinearSVC(
            C=1.0,
            dual="auto",
            random_state=0,
            max_iter=10000,
        ),
    )
    model.fit(xs, ys)
    return SklearnPredictorArtifact(family="linear_svm", model=model)


def train_random_forest(samples: list[tuple[list[float], str]]) -> SklearnPredictorArtifact:
    RandomForestClassifier, make_pipeline, StandardScaler, LinearSVC = require_sklearn()
    del make_pipeline, StandardScaler, LinearSVC
    xs = [features for features, _ in samples]
    ys = [label for _, label in samples]
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=None,
        min_samples_leaf=1,
        random_state=0,
    )
    model.fit(xs, ys)
    return SklearnPredictorArtifact(family="random_forest", model=model)


def build_model_output_path(first_path: Path, family: str) -> Path:
    if family == "lda":
        return first_path.parent / "lda-model.json"
    if family == "linear_svm":
        return first_path.parent / "linear-svm-model.joblib"
    if family == "random_forest":
        return first_path.parent / "random-forest-model.joblib"
    raise ValueError(f"unsupported family {family!r}")


def load_prediction_model(path: Path) -> PredictiveModel:
    if path.suffix == ".json":
        return LdaModel.load_json(path)
    if path.suffix == ".joblib":
        return SklearnPredictorArtifact.load_joblib(path)
    raise ValueError(f"unsupported model artifact suffix for {path}")
