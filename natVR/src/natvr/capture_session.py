from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import signal
import sys
import time

from natvr.cues import (
    active_cue_at_offset,
    build_cue_schedule,
    cue_annotations,
    parse_gesture_list,
    schedule_duration_s,
    write_cue_file,
)
from natvr.emg_consumer import EmgKafkaConsumer
from natvr.recording import (
    ParquetSessionRecorder,
    add_metadata_args,
    add_recording_args,
    build_cue_path,
    build_output_paths,
    build_session_metadata,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a cue-driven EMG capture session and record labeled Parquet output."
    )
    add_recording_args(parser)
    add_metadata_args(parser)
    parser.add_argument(
        "--gestures",
        default="rest,fist,open,pinch,point,thumbs_up",
        help="Comma-separated gesture list for hold prompts.",
    )
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--hold-s", type=float, default=3.0)
    parser.add_argument("--rest-s", type=float, default=2.0)
    parser.add_argument("--lead-in-s", type=float, default=3.0)
    parser.add_argument("--tail-rest-s", type=float, default=2.0)
    parser.add_argument("--seed", type=int)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    gestures = parse_gesture_list(args.gestures)
    schedule = build_cue_schedule(
        gestures,
        repetitions=args.repetitions,
        hold_s=args.hold_s,
        rest_s=args.rest_s,
        lead_in_s=args.lead_in_s,
        tail_rest_s=args.tail_rest_s,
        seed=args.seed,
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
            f"Starting cue capture for session={args.session_id} device={args.device_id} "
            f"duration={duration_s:.1f}s gestures={','.join(gestures)}",
            file=sys.stderr,
        )
        while not stopping:
            elapsed_s = time.monotonic() - started_monotonic
            if elapsed_s >= duration_s:
                break
            cue = active_cue_at_offset(schedule, elapsed_s)
            if cue and cue.cue_id != current_cue_id:
                current_cue_id = cue.cue_id
                print(
                    f"[{elapsed_s:6.2f}s] {cue.phase.upper():7s} {cue.prompt}",
                    file=sys.stderr,
                )

            envelope = consumer.poll(timeout=0.2)
            if envelope is not None:
                recorder.append(
                    envelope,
                    annotations=cue_annotations(cue),
                )
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
        print(
            f"Recorded {recorder.frame_count} labeled frames to {output_path} "
            f"with metadata {metadata_path} and cues {cue_path}",
            file=sys.stderr,
        )
    finally:
        signal.signal(signal.SIGINT, previous_int)
        signal.signal(signal.SIGTERM, previous_term)
        consumer.close()
