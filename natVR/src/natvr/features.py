from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def mean_absolute_value(samples: list[float] | tuple[float, ...]) -> float:
    if not samples:
        return 0.0
    return sum(abs(sample) for sample in samples) / len(samples)


def rms_value(samples: list[float] | tuple[float, ...]) -> float:
    if not samples:
        return 0.0
    return (sum(sample * sample for sample in samples) / len(samples)) ** 0.5


def zero_crossings(samples: list[float] | tuple[float, ...], threshold: float = 0.0) -> int:
    count = 0
    for prev, curr in zip(samples, samples[1:]):
        if (prev >= 0 > curr or prev < 0 <= curr) and abs(prev - curr) >= threshold:
            count += 1
    return count


def slope_sign_changes(samples: list[float] | tuple[float, ...], threshold: float = 0.0) -> int:
    count = 0
    for a, b, c in zip(samples, samples[1:], samples[2:]):
        diff1 = b - a
        diff2 = b - c
        if diff1 * diff2 > 0 and max(abs(diff1), abs(diff2)) >= threshold:
            count += 1
    return count


def waveform_length(samples: list[float] | tuple[float, ...]) -> float:
    return sum(abs(curr - prev) for prev, curr in zip(samples, samples[1:]))


@dataclass(frozen=True, slots=True)
class HudginsFeatures:
    mav: float
    rms: float
    zero_crossings: int
    slope_sign_changes: int
    waveform_length: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "mav": self.mav,
            "rms": self.rms,
            "zero_crossings": self.zero_crossings,
            "slope_sign_changes": self.slope_sign_changes,
            "waveform_length": self.waveform_length,
        }


def extract_hudgins_features(
    samples: list[float] | tuple[float, ...],
    *,
    zc_threshold: float = 0.0,
    ssc_threshold: float = 0.0,
) -> HudginsFeatures:
    return HudginsFeatures(
        mav=mean_absolute_value(samples),
        rms=rms_value(samples),
        zero_crossings=zero_crossings(samples, threshold=zc_threshold),
        slope_sign_changes=slope_sign_changes(samples, threshold=ssc_threshold),
        waveform_length=waveform_length(samples),
    )


@dataclass(frozen=True, slots=True)
class WindowedFeatureVector:
    session_id: str | None
    gesture: str | None
    phase: str | None
    start_ts_us: int
    end_ts_us: int
    channel_features: tuple[HudginsFeatures, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "gesture": self.gesture,
            "phase": self.phase,
            "start_ts_us": self.start_ts_us,
            "end_ts_us": self.end_ts_us,
            "channel_features": [
                feature.to_dict() for feature in self.channel_features
            ],
        }
