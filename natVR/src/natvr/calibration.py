from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from statistics import mean
from typing import Any

from natvr.features import HudginsFeatures, WindowedFeatureVector


AMPLITUDE_FIELDS = ("mav", "rms", "waveform_length")
DEFAULT_CALIBRATION_PHASES = ("hold",)


def load_feature_vectors(path: Path) -> list[WindowedFeatureVector]:
    vectors: list[WindowedFeatureVector] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = json.loads(line)
            vectors.append(
                WindowedFeatureVector(
                    session_id=raw.get("session_id"),
                    gesture=raw.get("gesture"),
                    phase=raw.get("phase"),
                    start_ts_us=int(raw["start_ts_us"]),
                    end_ts_us=int(raw["end_ts_us"]),
                    channel_features=tuple(
                        HudginsFeatures(
                            mav=float(feature["mav"]),
                            rms=float(feature["rms"]),
                            zero_crossings=int(feature["zero_crossings"]),
                            slope_sign_changes=int(feature["slope_sign_changes"]),
                            waveform_length=float(feature["waveform_length"]),
                        )
                        for feature in raw["channel_features"]
                    ),
                )
            )
    return vectors


@dataclass(frozen=True, slots=True)
class CalibrationProfile:
    session_id: str | None
    rest_mean_rms: tuple[float, ...]
    active_mean_rms: tuple[float, ...]
    scale_rms: tuple[float, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "rest_mean_rms": list(self.rest_mean_rms),
            "active_mean_rms": list(self.active_mean_rms),
            "scale_rms": list(self.scale_rms),
        }


def build_calibration_profile(
    vectors: list[WindowedFeatureVector],
    *,
    rest_gesture: str = "rest",
    active_gesture: str = "fist",
) -> CalibrationProfile:
    rest_vectors = [vector for vector in vectors if vector.gesture == rest_gesture]
    active_vectors = [vector for vector in vectors if vector.gesture == active_gesture]
    if not rest_vectors:
        raise ValueError(f"no vectors found for rest gesture {rest_gesture!r}")
    if not active_vectors:
        raise ValueError(f"no vectors found for active gesture {active_gesture!r}")
    channel_count = len(rest_vectors[0].channel_features)
    rest_mean_rms = tuple(
        mean(vector.channel_features[idx].rms for vector in rest_vectors)
        for idx in range(channel_count)
    )
    active_mean_rms = tuple(
        mean(vector.channel_features[idx].rms for vector in active_vectors)
        for idx in range(channel_count)
    )
    scale_rms = tuple(
        max(1e-6, active_mean_rms[idx] - rest_mean_rms[idx])
        for idx in range(channel_count)
    )
    return CalibrationProfile(
        session_id=rest_vectors[0].session_id,
        rest_mean_rms=rest_mean_rms,
        active_mean_rms=active_mean_rms,
        scale_rms=scale_rms,
    )


def select_calibration_vectors(
    vectors: list[WindowedFeatureVector],
    *,
    phases: tuple[str, ...] | None = DEFAULT_CALIBRATION_PHASES,
) -> list[WindowedFeatureVector]:
    labeled_vectors = [vector for vector in vectors if vector.gesture]
    if phases is None:
        return labeled_vectors
    allowed_phases = {phase for phase in phases if phase}
    selected = [vector for vector in labeled_vectors if vector.phase in allowed_phases]
    if not selected:
        wanted = ", ".join(sorted(allowed_phases)) or "<none>"
        raise ValueError(f"no labeled vectors found for calibration phases: {wanted}")
    return selected


def normalize_feature_vector(
    vector: WindowedFeatureVector,
    profile: CalibrationProfile,
) -> WindowedFeatureVector:
    normalized_channels = []
    for idx, channel in enumerate(vector.channel_features):
        scale = profile.scale_rms[idx]
        rest = profile.rest_mean_rms[idx]
        normalized_channels.append(
            HudginsFeatures(
                mav=channel.mav / scale,
                rms=(channel.rms - rest) / scale,
                zero_crossings=channel.zero_crossings,
                slope_sign_changes=channel.slope_sign_changes,
                waveform_length=channel.waveform_length / scale,
            )
        )
    return WindowedFeatureVector(
        session_id=vector.session_id,
        gesture=vector.gesture,
        phase=vector.phase,
        start_ts_us=vector.start_ts_us,
        end_ts_us=vector.end_ts_us,
        channel_features=tuple(normalized_channels),
    )


def build_calibration_output_path(feature_path: Path) -> Path:
    return feature_path.with_suffix("").with_suffix(".calibration.json")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a per-session normalization profile from feature windows."
    )
    parser.add_argument("feature_path")
    parser.add_argument("--rest-gesture", default="rest")
    parser.add_argument("--active-gesture", default="fist")
    parser.add_argument(
        "--phase",
        action="append",
        dest="phases",
        help=(
            "Repeat to restrict calibration to specific cue phases. "
            "Defaults to hold-only to match model training."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    feature_path = Path(args.feature_path)
    vectors = select_calibration_vectors(
        load_feature_vectors(feature_path),
        phases=tuple(args.phases) if args.phases else DEFAULT_CALIBRATION_PHASES,
    )
    profile = build_calibration_profile(
        vectors,
        rest_gesture=args.rest_gesture,
        active_gesture=args.active_gesture,
    )
    output_path = build_calibration_output_path(feature_path)
    output_path.write_text(json.dumps(profile.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote calibration profile to {output_path}")
