from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from natvr._optional import require_pyarrow
from natvr.recording import build_cue_path, build_output_paths
from natvr.topics import emg_raw


GESTURE_LEVELS = {
    "rest": (1, 1),
    "fist": (6, 6),
    "open": (3, 3),
    "pinch": (5, 2),
    "point": (2, 5),
    "thumbs_up": (2, 4),
}


def synth_channel(level: int, *, sample_count: int, phase_shift: int = 0) -> list[int]:
    return [
        int(level + ((idx + phase_shift) % 3) - 1)
        for idx in range(sample_count)
    ]


def build_synthetic_rows(
    *,
    session_id: str,
    device_id: str,
    gestures: list[str],
    sample_rate_hz: int = 1000,
    frame_samples: int = 50,
    hold_frames: int = 4,
    rest_frames: int = 2,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    device_ts_us = 1_000_000
    seq_no = 0

    def append_rows(gesture: str, phase: str, frames: int) -> None:
        nonlocal device_ts_us, seq_no
        base0, base1 = GESTURE_LEVELS[gesture]
        for frame_idx in range(frames):
            rows.append(
                {
                    "schema_version": "exg.pill.emg.data.v1",
                    "device_id": device_id,
                    "topic": emg_raw(device_id),
                    "partition": 0,
                    "offset": seq_no,
                    "broker_received_at_us": device_ts_us,
                    "seq_no": seq_no,
                    "device_ts_us": device_ts_us,
                    "sample_rate_hz": sample_rate_hz,
                    "n_channels": 2,
                    "samples_per_channel": frame_samples,
                    "sequence_gap": 0,
                    "channel_labels": ["flexor_a", "extensor_a"],
                    "channel_0": synth_channel(base0, sample_count=frame_samples, phase_shift=frame_idx),
                    "channel_1": synth_channel(base1, sample_count=frame_samples, phase_shift=frame_idx + 1),
                    "cue_id": seq_no,
                    "cue_phase": phase,
                    "cue_gesture": gesture,
                    "cue_prompt": gesture,
                    "session_id": session_id,
                }
            )
            seq_no += 1
            device_ts_us += int(frame_samples * 1_000_000 / sample_rate_hz)

    for gesture in gestures:
        append_rows(gesture, "hold", hold_frames)
        if gesture != "rest":
            append_rows("rest", "rest", rest_frames)
    return rows


def write_synthetic_session(
    *,
    output_dir: Path,
    session_id: str,
    device_id: str,
    gestures: list[str],
) -> tuple[Path, Path]:
    pa, pq = require_pyarrow()
    rows = build_synthetic_rows(
        session_id=session_id,
        device_id=device_id,
        gestures=gestures,
    )
    parquet_path, _ = build_output_paths(output_dir, session_id, device_id)
    cue_path = build_cue_path(output_dir, session_id, device_id)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), parquet_path)
    cue_path.write_text("[]\n", encoding="utf-8")
    return parquet_path, cue_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a deterministic synthetic EMG Parquet session for pipeline testing."
    )
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--device-id", default="sim01")
    parser.add_argument("--output-dir", default="captures")
    parser.add_argument("--gestures", default="rest,fist,point,pinch,open")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    gestures = [gesture.strip() for gesture in args.gestures.split(",") if gesture.strip()]
    parquet_path, cue_path = write_synthetic_session(
        output_dir=Path(args.output_dir),
        session_id=args.session_id,
        device_id=args.device_id,
        gestures=gestures,
    )
    print(f"Wrote synthetic session to {parquet_path} and {cue_path}")
