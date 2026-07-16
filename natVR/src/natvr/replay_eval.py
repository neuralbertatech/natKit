from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from natvr.baseline import confusion_matrix
from natvr.classifier import ClassifierEngine, load_calibration_profile
from natvr.featurize import (
    load_rows,
    rows_to_sample_stream,
    select_channel_indexes,
    window_feature_vectors,
)
from natvr.predictor import load_prediction_model
from natvr.replay import load_replay_timeline


def build_replay_eval_output_path(parquet_path: Path) -> Path:
    return parquet_path.with_suffix("").with_suffix(".replay-eval.json")


def expected_window_labels(
    parquet_path: Path,
    *,
    marker_path: Path | None = None,
    marker_type: str | None = None,
    field_prefix: str | None = None,
    selected_channel_indexes: list[int] | tuple[int, ...] | None = None,
    window_ms: int,
    hop_ms: int,
) -> dict[tuple[int, int], dict[str, Any]]:
    rows = load_rows(
        parquet_path,
        marker_path=marker_path,
        marker_type=marker_type,
        field_prefix=field_prefix,
    )
    stream, sample_rate_hz = rows_to_sample_stream(
        rows,
        selected_channel_indexes=selected_channel_indexes,
    )
    session_id = parquet_path.stem.split("__", 1)[0]
    vectors = window_feature_vectors(
        stream,
        sample_rate_hz=sample_rate_hz,
        session_id=session_id,
        window_ms=window_ms,
        hop_ms=hop_ms,
    )
    return {
        (vector.start_ts_us, vector.end_ts_us): {
            "gesture": vector.gesture,
            "phase": vector.phase,
        }
        for vector in vectors
        if vector.gesture
    }


def evaluate_replay_session(
    parquet_path: Path,
    *,
    session_id: str,
    model_path: Path,
    calibration_path: Path,
    marker_path: Path | None = None,
    marker_type: str | None = None,
    field_prefix: str | None = None,
    device_id: str | None = None,
    selected_channel_indexes: list[int] | tuple[int, ...] | None = None,
    window_ms: int = 200,
    hop_ms: int = 50,
    vote_windows: int = 5,
    confidence_threshold: float = 0.6,
    min_hold_windows: int = 2,
    emit_only_during_cue_hold: bool = False,
) -> dict[str, Any]:
    timeline = load_replay_timeline(
        parquet_path,
        marker_path=marker_path,
        session_id=session_id,
    )
    replay_frames = [event.frame for event in timeline if event.kind == "emg" and event.frame is not None]
    if not replay_frames:
        raise RuntimeError("no replay frames found")
    model = load_prediction_model(model_path)
    calibration = load_calibration_profile(calibration_path)
    engine = ClassifierEngine(
        device_id=device_id or replay_frames[0].frame.device_id,
        session_id=session_id,
        sample_rate_hz=replay_frames[0].frame.sample_rate_hz,
        model=model,
        calibration=calibration,
        window_ms=window_ms,
        hop_ms=hop_ms,
        vote_windows=vote_windows,
        confidence_threshold=confidence_threshold,
        min_hold_windows=min_hold_windows,
        emit_only_during_cue_hold=emit_only_during_cue_hold,
    )
    expected = expected_window_labels(
        parquet_path,
        marker_path=marker_path,
        marker_type=marker_type,
        field_prefix=field_prefix,
        selected_channel_indexes=selected_channel_indexes,
        window_ms=window_ms,
        hop_ms=hop_ms,
    )
    matched_truth: list[str] = []
    matched_predicted: list[str] = []
    matched_windows: list[tuple[int, int]] = []
    unmatched_predictions = 0
    for event in timeline:
        if event.kind == "marker":
            if event.marker is not None:
                engine.observe_marker_event(event.marker)
            continue
        if event.frame is None:
            continue
        replay_frame = event.frame
        channel_indexes = select_channel_indexes(
            len(replay_frame.frame.channels),
            selected_channel_indexes,
        )
        selected_channels = tuple(
            replay_frame.frame.channels[index] for index in channel_indexes
        )
        for result in engine.process_frame_detailed(
            device_ts_us=replay_frame.frame.device_ts_us,
            channels=selected_channels,
        ):
            if result.emitted_state is None:
                continue
            state = result.emitted_state
            key = (state.source_window_start_us, state.source_window_end_us)
            exp = expected.get(key)
            if not exp or not exp.get("gesture"):
                unmatched_predictions += 1
                continue
            matched_windows.append(key)
            matched_truth.append(str(exp["gesture"]))
            matched_predicted.append(state.gesture_id)
    matched_window_set = set(matched_windows)
    missing_windows = sum(1 for key in expected if key not in matched_window_set)
    correct = sum(
        1
        for truth, predicted in zip(matched_truth, matched_predicted, strict=True)
        if truth == predicted
    )
    return {
        "session_id": session_id,
        "parquet_path": str(parquet_path),
        "model_path": str(model_path),
        "calibration_path": str(calibration_path),
        "expected_windows": len(expected),
        "predicted_windows": len(matched_predicted) + unmatched_predictions,
        "matched_windows": len(matched_predicted),
        "missing_windows": missing_windows,
        "unmatched_predictions": unmatched_predictions,
        "coverage": (len(matched_predicted) / len(expected)) if expected else 0.0,
        "accuracy": (correct / len(matched_truth)) if matched_truth else 0.0,
        "confusion_matrix": (
            confusion_matrix(matched_truth, matched_predicted)
            if matched_truth
            else {}
        ),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate replay-session classifier output against the recorded cue timeline."
    )
    parser.add_argument("parquet_path")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--device-id")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--calibration-path", required=True)
    parser.add_argument("--marker-path")
    parser.add_argument("--marker-type")
    parser.add_argument("--field-prefix")
    parser.add_argument("--window-ms", type=int, default=200)
    parser.add_argument("--hop-ms", type=int, default=50)
    parser.add_argument("--vote-windows", type=int, default=5)
    parser.add_argument("--confidence-threshold", type=float, default=0.6)
    parser.add_argument("--min-hold-windows", type=int, default=2)
    parser.add_argument("--emit-only-during-cue-hold", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    parquet_path = Path(args.parquet_path)
    report = evaluate_replay_session(
        parquet_path,
        session_id=args.session_id,
        device_id=args.device_id,
        model_path=Path(args.model_path),
        calibration_path=Path(args.calibration_path),
        marker_path=Path(args.marker_path) if args.marker_path else None,
        marker_type=args.marker_type,
        field_prefix=args.field_prefix,
        window_ms=args.window_ms,
        hop_ms=args.hop_ms,
        vote_windows=args.vote_windows,
        confidence_threshold=args.confidence_threshold,
        min_hold_windows=args.min_hold_windows,
        emit_only_during_cue_hold=args.emit_only_during_cue_hold,
    )
    output_path = build_replay_eval_output_path(parquet_path)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote replay evaluation report to {output_path}")
