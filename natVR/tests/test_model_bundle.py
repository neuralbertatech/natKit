"""Tests for the self-describing live-inference bundle (train/serve parity).

Confirms the bundle captures exactly the parameters the live C++ classifier needs
to reproduce training: window sample counts, the canonical feature order, the DSP
chain, the per-session rest-calibration profile, and the LDA params -- and that
the embedded calibration is the *same* one training normalized with (parity by
construction for the single-session convention flow).
"""

from __future__ import annotations

from pathlib import Path

from natvr.baseline import build_dataset
from natvr.calibration import build_calibration_profile
from natvr.features import HudginsFeatures, WindowedFeatureVector
from natvr.featurize import write_feature_vectors
from natvr.model import LdaModel, train_lda, vector_to_flat_features
from natvr.model_bundle import (
    BUNDLE_VERSION,
    FEATURE_ORDER,
    build_bundle_output_path,
    build_model_bundle,
    build_training_calibration_profile,
    write_model_bundle,
)


def _vector(gesture: str, rms0: float, rms1: float) -> WindowedFeatureVector:
    def _feat(rms: float) -> HudginsFeatures:
        return HudginsFeatures(
            mav=rms * 0.8,
            rms=rms,
            zero_crossings=3,
            slope_sign_changes=2,
            waveform_length=rms * 5.0,
        )

    return WindowedFeatureVector(
        session_id="s1",
        gesture=gesture,
        phase="hold",
        start_ts_us=0,
        end_ts_us=200_000,
        channel_features=(_feat(rms0), _feat(rms1)),
    )


def _write_session(path: Path) -> None:
    vectors = [
        _vector("rest", 1.0, 2.0),
        _vector("rest", 1.2, 1.8),
        _vector("fist", 6.0, 9.0),
        _vector("fist", 6.4, 8.6),
        _vector("open", 3.0, 4.0),
        _vector("open", 3.2, 4.2),
    ]
    write_feature_vectors(path, vectors)


def test_bundle_output_path_is_sibling() -> None:
    model_path = Path("/models/job42/lda-model.json")
    assert build_bundle_output_path(model_path) == Path(
        "/models/job42/emg-gesture-bundle.json"
    )


def test_bundle_shape_and_window_samples() -> None:
    profile = build_calibration_profile(
        [_vector("rest", 1.0, 2.0), _vector("fist", 6.0, 9.0)]
    )
    lda = train_lda(
        [
            (vector_to_flat_features(_vector("rest", 1.0, 2.0)), "rest"),
            (vector_to_flat_features(_vector("fist", 6.0, 9.0)), "fist"),
        ]
    )
    bundle = build_model_bundle(
        lda_model=lda,
        calibration=profile,
        sample_rate_hz=1000,
        window_ms=200,
        hop_ms=50,
        selected_channel_indexes=[0, 1],
    )
    assert bundle["bundle_version"] == BUNDLE_VERSION
    assert bundle["model_family"] == "lda"
    assert bundle["window_samples"] == 200  # round(1000 * 200 / 1000)
    assert bundle["hop_samples"] == 50
    assert bundle["channel_count"] == 2
    assert tuple(bundle["feature_order"]) == FEATURE_ORDER
    assert bundle["dsp"] == {
        "notch_base_hz": 60.0,
        "notch_harmonics": 3,
        "highpass_hz": 20.0,
        "rectify": False,
    }
    assert bundle["selected_channel_indexes"] == [0, 1]
    assert bundle["lda"]["model_type"] == "lda"
    assert len(bundle["calibration"]["rest_mean_rms"]) == 2
    assert len(bundle["calibration"]["scale_rms"]) == 2


def test_training_calibration_matches_build_dataset(tmp_path: Path) -> None:
    """For a single session, the bundle's calibration equals the profile
    build_dataset normalized the LDA with -- parity is exact."""
    feature_path = tmp_path / "session.features.jsonl"
    _write_session(feature_path)

    # The profile the bundle embeds.
    bundle_profile = build_training_calibration_profile([feature_path])

    # The profile build_dataset builds internally over the same filtered vectors.
    from natvr.calibration import load_feature_vectors

    filtered = [
        v
        for v in load_feature_vectors(feature_path)
        if v.gesture and (v.phase == "hold" or str(v.gesture) == "rest")
    ]
    dataset_profile = build_calibration_profile(filtered)

    assert bundle_profile.rest_mean_rms == dataset_profile.rest_mean_rms
    assert bundle_profile.scale_rms == dataset_profile.scale_rms
    # sanity: build_dataset consumes the same vectors without error
    assert build_dataset([feature_path], normalize=True)


def test_write_and_reload_bundle(tmp_path: Path) -> None:
    feature_path = tmp_path / "session.features.jsonl"
    _write_session(feature_path)
    profile = build_training_calibration_profile([feature_path])
    lda = train_lda(
        [
            (vector_to_flat_features(_vector("rest", 1.0, 2.0)), "rest"),
            (vector_to_flat_features(_vector("fist", 6.0, 9.0)), "fist"),
        ]
    )
    model_path = tmp_path / "lda-model.json"
    lda.save_json(model_path)
    bundle = build_model_bundle(
        lda_model=lda,
        calibration=profile,
        sample_rate_hz=1000,
        window_ms=200,
        hop_ms=50,
    )
    written = write_model_bundle(model_path, bundle)
    assert written == tmp_path / "emg-gesture-bundle.json"
    import json

    reloaded = json.loads(written.read_text())
    # The embedded LDA round-trips back into a usable model.
    embedded = LdaModel.from_dict(reloaded["lda"])
    assert set(embedded.labels) == {"rest", "fist"}
