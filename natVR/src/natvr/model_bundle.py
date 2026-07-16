"""Self-describing EMG gesture classification bundle (train/serve parity).

The training pipeline extracts features in a very specific way -- a sliding
window (``window_ms``/``hop_ms``), a fixed DSP chain applied fresh per window
(60 Hz notch chain + 20 Hz high-pass, no rectify), Hudgins features in a fixed
per-channel order, and per-session rest-calibration normalization. The live C++
classifier must reproduce *all* of that exactly or live accuracy diverges from
the reported validation accuracy.

Rather than hoping a hand-wired live pipeline matches, the trainer emits one
self-describing bundle that captures every parameter. A single C++ transform
(``emg_gesture_classify``) reads the bundle and drives its windowing, feature
order, normalization, and LDA scoring from it -- so parity holds by construction.

The bundle is written next to ``lda-model.json`` and carries the LDA parameters
inline, so it is the only artifact the live path needs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from natvr.calibration import (
    CalibrationProfile,
    build_calibration_profile,
    load_feature_vectors,
)
from natvr.model import LdaModel


BUNDLE_VERSION = "emg-gesture-bundle-v1"
BUNDLE_FILENAME = "emg-gesture-bundle.json"

# The canonical per-channel Hudgins feature order (matches model.vector_to_flat_features).
FEATURE_ORDER = (
    "mav",
    "rms",
    "zero_crossings",
    "slope_sign_changes",
    "waveform_length",
)

# DSP parameters the pipeline applies at featurization. These mirror the defaults
# used by featurize.window_feature_vectors (kafka_train_validate does not override
# them). rectify is False on the training path -- do not change without re-deriving.
DEFAULT_DSP = {
    "notch_base_hz": 60.0,
    "notch_harmonics": 3,
    "highpass_hz": 20.0,
    "rectify": False,
}


def build_bundle_output_path(model_path: Path) -> Path:
    """The bundle sits next to the LDA model artifact in the same directory."""
    return model_path.parent / BUNDLE_FILENAME


def _window_samples(sample_rate_hz: int, window_ms: int) -> int:
    return max(1, int(round(sample_rate_hz * window_ms / 1000.0)))


def build_training_calibration_profile(
    feature_paths: list[Path],
    *,
    rest_gesture: str = "rest",
    active_gesture: str = "fist",
) -> CalibrationProfile:
    """Rebuild the calibration profile that build_dataset applied at fit time.

    Mirrors baseline.build_dataset's per-path filter (hold-phase windows plus all
    rest windows), then builds one profile over the combined set. For the walk-up
    convention flow there is exactly one training session, so this is the *same*
    profile the LDA was normalized with -- parity is exact. With multiple training
    sessions it is a single-profile approximation of build_dataset's per-session
    normalization (documented; the convention flow is single-session).
    """
    filtered = []
    for path in feature_paths:
        for vector in load_feature_vectors(path):
            if vector.gesture and (
                vector.phase == "hold" or str(vector.gesture) == rest_gesture
            ):
                filtered.append(vector)
    return build_calibration_profile(
        filtered,
        rest_gesture=rest_gesture,
        active_gesture=active_gesture,
    )


def build_model_bundle(
    *,
    lda_model: LdaModel,
    calibration: CalibrationProfile,
    sample_rate_hz: int,
    window_ms: int,
    hop_ms: int,
    selected_channel_indexes: list[int] | tuple[int, ...] | None = None,
    channel_labels: list[str] | tuple[str, ...] | None = None,
    zc_threshold: float = 0.0,
    ssc_threshold: float = 0.0,
    dsp: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the self-describing bundle dict for the selected LDA model."""
    channel_count = len(calibration.scale_rms)
    bundle: dict[str, Any] = {
        "bundle_version": BUNDLE_VERSION,
        "model_family": "lda",
        "sample_rate_hz": int(sample_rate_hz),
        "window_ms": int(window_ms),
        "hop_ms": int(hop_ms),
        # Sample counts are computed here (authoritative) so the live path never
        # re-derives them and risks a rounding divergence from training.
        "window_samples": _window_samples(sample_rate_hz, window_ms),
        "hop_samples": _window_samples(sample_rate_hz, hop_ms),
        "channel_count": channel_count,
        "feature_order": list(FEATURE_ORDER),
        "zc_threshold": float(zc_threshold),
        "ssc_threshold": float(ssc_threshold),
        "dsp": dict(dsp) if dsp is not None else dict(DEFAULT_DSP),
        "calibration": {
            "rest_mean_rms": list(calibration.rest_mean_rms),
            "scale_rms": list(calibration.scale_rms),
        },
        "lda": lda_model.to_dict(),
    }
    if selected_channel_indexes:
        bundle["selected_channel_indexes"] = [int(i) for i in selected_channel_indexes]
    if channel_labels:
        bundle["channel_labels"] = [str(label) for label in channel_labels]
    return bundle


def write_model_bundle(model_path: Path, bundle: dict[str, Any]) -> Path:
    """Write the bundle next to the LDA model artifact; return the bundle path."""
    bundle_path = build_bundle_output_path(model_path)
    bundle_path.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    return bundle_path
