from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import signal
import sys
import time
from typing import Any

from natvr.baseline import build_dataset
from natvr.calibration import build_calibration_output_path, build_calibration_profile
from natvr.cues import (
    CueEvent,
    active_cue_at_offset,
    cue_annotations,
    parse_gesture_list,
    schedule_duration_s,
    write_cue_file,
)
from natvr.emg_consumer import EmgKafkaConsumer
from natvr.featurize import (
    build_feature_output_path,
    load_rows,
    rows_to_sample_stream,
    window_feature_vectors,
    write_feature_vectors,
)
from natvr.model import train_lda, vector_to_flat_features
from natvr.recording import (
    ParquetSessionRecorder,
    add_metadata_args,
    add_recording_args,
    build_cue_path,
    build_output_paths,
    build_session_metadata,
)


def build_guided_calibration_schedule(
    gestures: list[str],
    *,
    active_gesture: str = "fist",
    lead_in_s: float = 5.0,
    rest_baseline_s: float = 20.0,
    max_squeeze_s: float = 15.0,
    gesture_hold_s: float = 5.0,
    gesture_rest_s: float = 4.0,
    tail_rest_s: float = 5.0,
) -> list[CueEvent]:
    if not gestures:
        raise ValueError("gestures must not be empty")
    if active_gesture not in gestures:
        raise ValueError(f"active_gesture {active_gesture!r} must be present in gestures")
    if min(
        lead_in_s,
        rest_baseline_s,
        max_squeeze_s,
        gesture_hold_s,
        gesture_rest_s,
        tail_rest_s,
    ) < 0:
        raise ValueError("cue timings must be non-negative")

    cue_id = 0
    current_s = 0.0
    events: list[CueEvent] = []

    def append_event(
        *,
        phase: str,
        gesture: str,
        prompt: str,
        duration_s: float,
        rep_index: int,
    ) -> None:
        nonlocal cue_id, current_s
        if duration_s <= 0:
            return
        events.append(
            CueEvent(
                cue_id=cue_id,
                rep_index=rep_index,
                phase=phase,
                gesture=gesture,
                prompt=prompt,
                start_offset_s=current_s,
                end_offset_s=current_s + duration_s,
            )
        )
        cue_id += 1
        current_s += duration_s

    append_event(
        phase="lead_in",
        gesture="rest",
        prompt="Prepare",
        duration_s=lead_in_s,
        rep_index=-1,
    )
    append_event(
        phase="rest_baseline",
        gesture="rest",
        prompt="Relax completely",
        duration_s=rest_baseline_s,
        rep_index=0,
    )
    append_event(
        phase="max_squeeze",
        gesture=active_gesture,
        prompt=f"Max {active_gesture}",
        duration_s=max_squeeze_s,
        rep_index=0,
    )

    for rep_index, gesture in enumerate(gestures):
        append_event(
            phase="gesture_hold",
            gesture=gesture,
            prompt=gesture,
            duration_s=gesture_hold_s,
            rep_index=rep_index,
        )
        append_event(
            phase="gesture_rest",
            gesture="rest",
            prompt="Rest",
            duration_s=gesture_rest_s,
            rep_index=rep_index,
        )

    append_event(
        phase="tail_rest",
        gesture="rest",
        prompt="Done",
        duration_s=tail_rest_s,
        rep_index=len(gestures),
    )
    return events


def build_guided_manifest_output_path(parquet_path: Path) -> Path:
    return parquet_path.with_suffix("").with_suffix(".guided-calibration.json")


def build_guided_model_output_path(parquet_path: Path) -> Path:
    return parquet_path.with_suffix("").with_suffix(".session-lda-model.json")


def write_guided_calibration_outputs(
    parquet_path: Path,
    *,
    rest_gesture: str = "rest",
    active_gesture: str = "fist",
    train_feature_paths: list[Path] | None = None,
    window_ms: int = 200,
    hop_ms: int = 50,
    notch_base_hz: float = 60.0,
    notch_harmonics: int = 3,
    highpass_hz: float | None = 20.0,
    rectify_signal: bool = False,
) -> dict[str, Any]:
    rows = load_rows(parquet_path)
    stream, sample_rate_hz = rows_to_sample_stream(rows)
    session_id = parquet_path.stem.split("__", 1)[0]
    vectors = window_feature_vectors(
        stream,
        sample_rate_hz=sample_rate_hz,
        session_id=session_id,
        window_ms=window_ms,
        hop_ms=hop_ms,
        notch_base_hz=notch_base_hz,
        notch_harmonics=notch_harmonics,
        highpass_hz=highpass_hz,
        rectify_signal=rectify_signal,
    )

    feature_path = build_feature_output_path(parquet_path)
    write_feature_vectors(feature_path, vectors)

    calibration_vectors = [
        vector
        for vector in vectors
        if vector.gesture and vector.phase in {"hold", "gesture_hold", "rest_baseline", "max_squeeze"}
    ]
    profile = build_calibration_profile(
        calibration_vectors,
        rest_gesture=rest_gesture,
        active_gesture=active_gesture,
    )
    calibration_path = build_calibration_output_path(feature_path)
    calibration_path.write_text(
        json.dumps(profile.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )

    model_path: Path | None = None
    train_paths = list(train_feature_paths or [])
    if train_paths:
        dataset = build_dataset(
            train_paths + [feature_path],
            normalize=True,
            rest_gesture=rest_gesture,
            active_gesture=active_gesture,
        )
        samples = [
            (vector_to_flat_features(vector), str(vector.gesture))
            for vector in dataset
            if vector.gesture
        ]
        model = train_lda(samples)
        model_path = build_guided_model_output_path(parquet_path)
        model.save_json(model_path)

    hold_vectors = [vector for vector in calibration_vectors if vector.phase in {"hold", "gesture_hold"}]
    gesture_counts = Counter(vector.gesture for vector in hold_vectors if vector.gesture)
    manifest = {
        "session_id": session_id,
        "parquet_path": str(parquet_path),
        "feature_path": str(feature_path),
        "calibration_path": str(calibration_path),
        "model_path": str(model_path) if model_path else None,
        "window_ms": window_ms,
        "hop_ms": hop_ms,
        "sample_rate_hz": sample_rate_hz,
        "feature_windows": len(vectors),
        "hold_windows": len(hold_vectors),
        "hold_gesture_counts": dict(sorted(gesture_counts.items())),
    }
    manifest_path = build_guided_manifest_output_path(parquet_path)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the guided 2-minute EMG calibration session and fit session artifacts."
    )
    add_recording_args(parser)
    add_metadata_args(parser)
    parser.add_argument(
        "--gestures",
        default="fist,open,pinch,point,thumbs_up",
        help="Comma-separated gesture list for single-rep calibration prompts.",
    )
    parser.add_argument("--active-gesture", default="fist")
    parser.add_argument("--lead-in-s", type=float, default=5.0)
    parser.add_argument("--rest-baseline-s", type=float, default=20.0)
    parser.add_argument("--max-squeeze-s", type=float, default=15.0)
    parser.add_argument("--gesture-hold-s", type=float, default=5.0)
    parser.add_argument("--gesture-rest-s", type=float, default=4.0)
    parser.add_argument("--tail-rest-s", type=float, default=5.0)
    parser.add_argument("--window-ms", type=int, default=200)
    parser.add_argument("--hop-ms", type=int, default=50)
    parser.add_argument("--notch-base-hz", type=float, default=60.0)
    parser.add_argument("--notch-harmonics", type=int, default=3)
    parser.add_argument("--highpass-hz", type=float, default=20.0)
    parser.add_argument("--no-highpass", action="store_true")
    parser.add_argument("--rectify", action="store_true")
    parser.add_argument(
        "--train-feature-path",
        action="append",
        dest="train_feature_paths",
        help="Optional existing feature JSONL to combine with this session and re-fit an LDA model.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    gestures = parse_gesture_list(args.gestures)
    schedule = build_guided_calibration_schedule(
        gestures,
        active_gesture=args.active_gesture,
        lead_in_s=args.lead_in_s,
        rest_baseline_s=args.rest_baseline_s,
        max_squeeze_s=args.max_squeeze_s,
        gesture_hold_s=args.gesture_hold_s,
        gesture_rest_s=args.gesture_rest_s,
        tail_rest_s=args.tail_rest_s,
    )
    consumer = EmgKafkaConsumer(
        bootstrap_servers=args.broker,
        device_id=args.device_id,
        group_id=args.group_id,
        topic=args.input_topic,
        direct_assign=args.direct_assign,
        partition=args.partition,
    )
    output_dir = Path(args.output_dir)
    output_path, metadata_path = build_output_paths(output_dir, args.session_id, args.device_id)
    cue_path = build_cue_path(output_dir, args.session_id, args.device_id)
    metadata = build_session_metadata(args, topic=consumer.topic)
    metadata.extra["guided_calibration"] = {
        "gestures": gestures,
        "active_gesture": args.active_gesture,
        "schedule_duration_s": schedule_duration_s(schedule),
    }
    recorder = ParquetSessionRecorder(output_path, metadata_path, metadata)
    started_at = datetime.now(tz=timezone.utc)
    started_monotonic = time.monotonic()
    duration_s = schedule_duration_s(schedule)
    stopping = False
    current_cue_id: int | None = None

    def handle_stop(_sig: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    previous_int = signal.signal(signal.SIGINT, handle_stop)
    previous_term = signal.signal(signal.SIGTERM, handle_stop)
    try:
        print(
            f"Starting guided calibration for session={args.session_id} device={args.device_id} "
            f"duration={duration_s:.1f}s active={args.active_gesture} gestures={','.join(gestures)}",
            file=sys.stderr,
        )
        while not stopping:
            elapsed_s = time.monotonic() - started_monotonic
            if elapsed_s >= duration_s:
                break
            cue = active_cue_at_offset(schedule, elapsed_s)
            if cue and cue.cue_id != current_cue_id:
                current_cue_id = cue.cue_id
                print(f"[{elapsed_s:6.2f}s] {cue.phase.upper():13s} {cue.prompt}", file=sys.stderr)

            envelope = consumer.poll(timeout=0.2)
            if envelope is not None:
                recorder.append(envelope, annotations=cue_annotations(cue))
                if args.max_frames and recorder.frame_count >= args.max_frames:
                    break

        recorder.finalize()
        write_cue_file(
            cue_path,
            session_id=args.session_id,
            device_id=args.device_id,
            started_at_utc=started_at,
            events=schedule,
        )
        manifest = write_guided_calibration_outputs(
            output_path,
            rest_gesture="rest",
            active_gesture=args.active_gesture,
            train_feature_paths=[Path(path) for path in (args.train_feature_paths or [])],
            window_ms=args.window_ms,
            hop_ms=args.hop_ms,
            notch_base_hz=args.notch_base_hz,
            notch_harmonics=args.notch_harmonics,
            highpass_hz=None if args.no_highpass else args.highpass_hz,
            rectify_signal=args.rectify,
        )
        print(
            "Recorded guided calibration session to "
            f"{output_path} and wrote artifacts "
            f"{manifest['feature_path']}, {manifest['calibration_path']}"
            + (f", {manifest['model_path']}" if manifest["model_path"] else "")
            + f", {build_guided_manifest_output_path(output_path)}",
            file=sys.stderr,
        )
    finally:
        signal.signal(signal.SIGINT, previous_int)
        signal.signal(signal.SIGTERM, previous_term)
        consumer.close()
