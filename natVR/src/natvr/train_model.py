from __future__ import annotations

import argparse
from pathlib import Path

from natvr.baseline import build_dataset
from natvr.model import train_lda, vector_to_flat_features
from natvr.predictor import build_model_output_path, train_linear_svm, train_random_forest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train a classifier model artifact from one or more feature JSONL files."
    )
    parser.add_argument("feature_paths", nargs="+")
    parser.add_argument(
        "--family",
        choices=("lda", "linear_svm", "random_forest"),
        default="lda",
    )
    parser.add_argument("--no-normalize", action="store_true")
    parser.add_argument("--rest-gesture", default="rest")
    parser.add_argument("--active-gesture", default="fist")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    paths = [Path(path) for path in args.feature_paths]
    dataset = build_dataset(
        paths,
        normalize=not args.no_normalize,
        rest_gesture=args.rest_gesture,
        active_gesture=args.active_gesture,
    )
    samples = [
        (vector_to_flat_features(vector), str(vector.gesture))
        for vector in dataset
        if vector.gesture
    ]
    output_path = build_model_output_path(paths[0], args.family)
    if args.family == "lda":
        model = train_lda(samples)
        model.save_json(output_path)
    elif args.family == "linear_svm":
        model = train_linear_svm(samples)
        model.save_joblib(output_path)
    else:
        model = train_random_forest(samples)
        model.save_joblib(output_path)
    print(f"Wrote model artifact to {output_path}")
