from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import random
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CueEvent:
    cue_id: int
    rep_index: int
    phase: str
    gesture: str
    prompt: str
    start_offset_s: float
    end_offset_s: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_gesture_list(raw: str) -> list[str]:
    gestures = [gesture.strip() for gesture in raw.split(",")]
    return [gesture for gesture in gestures if gesture]


def build_cue_schedule(
    gestures: list[str],
    *,
    repetitions: int = 1,
    hold_s: float = 3.0,
    rest_s: float = 2.0,
    lead_in_s: float = 3.0,
    tail_rest_s: float = 2.0,
    seed: int | None = None,
) -> list[CueEvent]:
    if not gestures:
        raise ValueError("gestures must not be empty")
    if repetitions <= 0:
        raise ValueError("repetitions must be > 0")
    if min(hold_s, rest_s, lead_in_s, tail_rest_s) < 0:
        raise ValueError("cue timings must be non-negative")

    rng = random.Random(seed)
    events: list[CueEvent] = []
    current_s = 0.0
    cue_id = 0

    if lead_in_s > 0:
        events.append(
            CueEvent(
                cue_id=cue_id,
                rep_index=-1,
                phase="lead_in",
                gesture="rest",
                prompt="Prepare",
                start_offset_s=current_s,
                end_offset_s=current_s + lead_in_s,
            )
        )
        cue_id += 1
        current_s += lead_in_s

    for rep_index in range(repetitions):
        order = list(gestures)
        rng.shuffle(order)
        for gesture in order:
            events.append(
                CueEvent(
                    cue_id=cue_id,
                    rep_index=rep_index,
                    phase="hold",
                    gesture=gesture,
                    prompt=gesture,
                    start_offset_s=current_s,
                    end_offset_s=current_s + hold_s,
                )
            )
            cue_id += 1
            current_s += hold_s
            if rest_s > 0:
                events.append(
                    CueEvent(
                        cue_id=cue_id,
                        rep_index=rep_index,
                        phase="rest",
                        gesture="rest",
                        prompt="Rest",
                        start_offset_s=current_s,
                        end_offset_s=current_s + rest_s,
                    )
                )
                cue_id += 1
                current_s += rest_s

    if tail_rest_s > 0:
        events.append(
            CueEvent(
                cue_id=cue_id,
                rep_index=repetitions,
                phase="tail_rest",
                gesture="rest",
                prompt="Done",
                start_offset_s=current_s,
                end_offset_s=current_s + tail_rest_s,
            )
        )

    return events


def active_cue_at_offset(events: list[CueEvent], elapsed_s: float) -> CueEvent | None:
    for event in events:
        if event.start_offset_s <= elapsed_s < event.end_offset_s:
            return event
    return None


def cue_annotations(event: CueEvent | None) -> dict[str, Any]:
    if event is None:
        return {
            "cue_id": None,
            "cue_phase": None,
            "cue_gesture": None,
            "cue_prompt": None,
        }
    return {
        "cue_id": event.cue_id,
        "cue_phase": event.phase,
        "cue_gesture": event.gesture,
        "cue_prompt": event.prompt,
    }


def schedule_duration_s(events: list[CueEvent]) -> float:
    if not events:
        return 0.0
    return max(event.end_offset_s for event in events)


def write_cue_file(
    path: Path,
    *,
    session_id: str,
    device_id: str,
    started_at_utc: datetime,
    events: list[CueEvent],
) -> None:
    started_at_utc = started_at_utc.astimezone(timezone.utc)
    payload = {
        "session_id": session_id,
        "device_id": device_id,
        "started_at_utc": started_at_utc.isoformat(),
        "events": [
            {
                **event.to_dict(),
                "start_ts_us": int(started_at_utc.timestamp() * 1_000_000 + event.start_offset_s * 1_000_000),
                "end_ts_us": int(started_at_utc.timestamp() * 1_000_000 + event.end_offset_s * 1_000_000),
            }
            for event in events
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
