from __future__ import annotations

import argparse
import json
from pathlib import Path

from natvr.classifier import ClassifierEngine, hand_state_to_dict, load_calibration_profile
from natvr.predictor import load_prediction_model
from natvr.replay import load_replay_timeline


def build_output_path(parquet_path: Path) -> Path:
    return parquet_path.with_suffix("").with_suffix(".hand-state.jsonl")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the classifier engine against a recorded replay session offline."
    )
    parser.add_argument("parquet_path")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--device-id")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--calibration-path", required=True)
    parser.add_argument("--marker-path")
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
    timeline = load_replay_timeline(
        parquet_path,
        marker_path=Path(args.marker_path) if args.marker_path else None,
        session_id=args.session_id,
    )
    replay_frames = [event.frame for event in timeline if event.kind == "emg" and event.frame is not None]
    marker_events = [event.marker for event in timeline if event.kind == "marker" and event.marker is not None]
    if not replay_frames:
        raise RuntimeError("no replay frames found")
    model = load_prediction_model(Path(args.model_path))
    calibration = load_calibration_profile(Path(args.calibration_path))
    device_id = args.device_id or replay_frames[0].frame.device_id
    engine = ClassifierEngine(
        device_id=device_id,
        session_id=args.session_id,
        sample_rate_hz=replay_frames[0].frame.sample_rate_hz,
        model=model,
        calibration=calibration,
        window_ms=args.window_ms,
        hop_ms=args.hop_ms,
        vote_windows=args.vote_windows,
        confidence_threshold=args.confidence_threshold,
        min_hold_windows=args.min_hold_windows,
        emit_only_during_cue_hold=args.emit_only_during_cue_hold,
    )
    output_path = build_output_path(parquet_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for event in timeline:
            if event.kind == "marker":
                if event.marker is not None:
                    engine.observe_marker_event(event.marker)
                continue
            if event.frame is None:
                continue
            replay_frame = event.frame
            for result in engine.process_frame_detailed(
                device_ts_us=replay_frame.frame.device_ts_us,
                channels=replay_frame.frame.channels,
            ):
                if result.emitted_state is None:
                    continue
                payload = hand_state_to_dict(result.emitted_state)
                payload.update(result.active_marker_context)
                handle.write(json.dumps(payload) + "\n")
                count += 1
    print(
        f"Wrote {count} classified states to {output_path}"
        + (
            f" after merging {len(marker_events)} marker events"
            if marker_events
            else ""
        )
    )
