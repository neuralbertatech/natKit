from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

from natvr.features import WindowedFeatureVector


@dataclass(slots=True)
class LdaModel:
    labels: list[str]
    priors: dict[str, float]
    means: dict[str, list[float]]
    variances: list[float]

    def score_samples(self, features: list[float]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for label in self.labels:
            mean_vec = self.means[label]
            score = math.log(max(self.priors[label], 1e-12))
            for idx, value in enumerate(features):
                variance = self.variances[idx]
                diff = value - mean_vec[idx]
                score -= 0.5 * diff * diff / variance
            scores[label] = score
        return scores

    def predict_one(self, features: list[float]) -> str:
        scores = self.score_samples(features)
        return max(scores, key=scores.get)

    def predict_confidence(self, features: list[float]) -> tuple[str, float]:
        scores = self.score_samples(features)
        predicted = max(scores, key=scores.get)
        max_score = max(scores.values())
        exps = {label: math.exp(score - max_score) for label, score in scores.items()}
        denom = sum(exps.values()) or 1.0
        return predicted, exps[predicted] / denom

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_type": "lda",
            "labels": self.labels,
            "priors": self.priors,
            "means": self.means,
            "variances": self.variances,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LdaModel":
        if payload.get("model_type") != "lda":
            raise ValueError("unsupported model_type")
        return cls(
            labels=[str(label) for label in payload["labels"]],
            priors={str(k): float(v) for k, v in payload["priors"].items()},
            means={
                str(label): [float(value) for value in values]
                for label, values in payload["means"].items()
            },
            variances=[float(value) for value in payload["variances"]],
        )

    @classmethod
    def load_json(cls, path: Path) -> "LdaModel":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save_json(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")


def vector_to_flat_features(vector: WindowedFeatureVector) -> list[float]:
    values: list[float] = []
    for channel in vector.channel_features:
        values.extend(
            [
                channel.mav,
                channel.rms,
                float(channel.zero_crossings),
                float(channel.slope_sign_changes),
                channel.waveform_length,
            ]
        )
    return values


def train_lda(samples: list[tuple[list[float], str]]) -> LdaModel:
    if not samples:
        raise ValueError("no training samples")
    labels = sorted({label for _, label in samples})
    dim = len(samples[0][0])
    grouped: dict[str, list[list[float]]] = {}
    for label in labels:
        grouped[label] = []
    for features, label in samples:
        grouped[label].append(features)
    means = {
        label: [
            sum(features[idx] for features in grouped[label]) / len(grouped[label])
            for idx in range(dim)
        ]
        for label in labels
    }
    variances = []
    total_count = sum(len(grouped[label]) for label in labels)
    for idx in range(dim):
        acc = 0.0
        for label in labels:
            label_mean = means[label][idx]
            for features in grouped[label]:
                diff = features[idx] - label_mean
                acc += diff * diff
        variances.append(max(1e-6, acc / max(1, total_count - len(labels))))
    priors = {label: len(grouped[label]) / total_count for label in labels}
    return LdaModel(labels=labels, priors=priors, means=means, variances=variances)
