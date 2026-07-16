from __future__ import annotations

import argparse

import pytest

from natvr.kafka_train_validate import (
    PipelineCancelledError,
    parse_selected_channel_indexes,
    parse_run_selector,
    resolve_train_eval_runs,
    run_pipeline,
)
from natvr.reconstruct_session import DiscoveredRun


def build_run(session_id: str, run_index: int) -> DiscoveredRun:
    start_us = run_index * 1_000
    end_us = start_us + 500
    return DiscoveredRun(
        session_id=session_id,
        run_index=run_index,
        start_us=start_us,
        end_us=end_us,
        device_ids=("emg01",),
        purpose="training",
        participant_id=f"p{run_index}",
        protocol_id="proto",
        tags=(),
        notes="",
        marker_count=10,
        last_activity_us=end_us,
    )


def test_parse_run_selector() -> None:
    assert parse_run_selector("demo:2") == ("demo", 2)


def test_parse_run_selector_rejects_invalid_shape() -> None:
    with pytest.raises(ValueError):
        parse_run_selector("demo")


def test_parse_selected_channel_indexes_from_descriptor_fields() -> None:
    assert parse_selected_channel_indexes(["channels.2.samples", "channels.0.samples"]) == [0, 2]


def test_parse_selected_channel_indexes_rejects_unsupported_fields() -> None:
    with pytest.raises(ValueError):
        parse_selected_channel_indexes(["device_ts_us"])


def test_resolve_train_eval_runs_from_cli_selectors() -> None:
    runs = [build_run("demo", 1), build_run("demo", 2), build_run("other", 1)]
    args = argparse.Namespace(
        train_runs=["demo:1", "other:1"],
        eval_runs=["demo:2"],
    )

    train_runs, eval_runs = resolve_train_eval_runs(args, runs)

    assert [(run.session_id, run.run_index) for run in train_runs] == [
        ("demo", 1),
        ("other", 1),
    ]
    assert [(run.session_id, run.run_index) for run in eval_runs] == [("demo", 2)]


def test_resolve_train_eval_runs_rejects_overlap() -> None:
    runs = [build_run("demo", 1), build_run("demo", 2)]
    args = argparse.Namespace(
        train_runs=["demo:1"],
        eval_runs=["demo:1"],
    )

    with pytest.raises(RuntimeError):
        resolve_train_eval_runs(args, runs)


def test_resolve_train_eval_runs_prompts_when_tty(monkeypatch) -> None:
    runs = [build_run("demo", 1), build_run("demo", 2), build_run("demo", 3)]
    args = argparse.Namespace(
        train_runs=None,
        eval_runs=None,
    )

    answers = iter(["1,3", "2"])
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    train_runs, eval_runs = resolve_train_eval_runs(args, runs)

    assert [(run.session_id, run.run_index) for run in train_runs] == [
        ("demo", 1),
        ("demo", 3),
    ]
    assert [(run.session_id, run.run_index) for run in eval_runs] == [("demo", 2)]


def test_run_pipeline_reports_progress(monkeypatch, tmp_path) -> None:
    runs = [build_run("demo", 1), build_run("demo", 2)]
    progress_messages: list[str] = []

    args = argparse.Namespace(
        broker="127.0.0.1:29092",
        output_dir=str(tmp_path),
        train_runs=["demo:1"],
        eval_runs=["demo:2"],
        families=["lda", "linear_svm"],
        no_direct_assign=False,
        rest_gesture="rest",
        active_gesture="fist",
        window_ms=200,
        hop_ms=50,
        vote_windows=5,
        confidence_threshold=0.6,
        min_hold_windows=2,
        emit_only_during_cue_hold=False,
        selected_fields=["channels.0.samples", "channels.1.samples"],
    )

    monkeypatch.setattr("natvr.kafka_train_validate.discover_runs", lambda _args: runs)

    def fake_reconstruct(
        args,
        selected_runs,
        *,
        runs_per_session,
        selected_channel_indexes=None,
        progress=None,
        should_stop=None,
        phase_label="run",
    ):
        assert selected_channel_indexes == [0, 1]
        if progress is not None:
            progress(f"stub {phase_label} prepared")
        return [
            argparse.Namespace(
                run=run,
                device_id="emg01",
                parquet_path=tmp_path / f"{run.session_id}-{run.run_index}.parquet",
                marker_path=tmp_path / f"{run.session_id}-{run.run_index}.markers.jsonl",
                metadata_path=tmp_path / f"{run.session_id}-{run.run_index}.meta.json",
                feature_path=tmp_path / f"{run.session_id}-{run.run_index}.features.jsonl",
                sample_rate_hz=0,
            )
            for run in selected_runs
        ]

    monkeypatch.setattr(
        "natvr.kafka_train_validate.reconstruct_and_featurize_runs",
        fake_reconstruct,
    )

    def fake_evaluate_family(
        args,
        *,
        family,
        train_artifacts,
        eval_artifacts,
        selected_channel_indexes=None,
        progress=None,
        should_stop=None,
    ):
        assert selected_channel_indexes == [0, 1]
        if progress is not None:
            progress(f"stub evaluating {family}")
        return {
            "family": family,
            "model_path": str(tmp_path / f"{family}.joblib"),
            "train_feature_paths": [str(artifact.feature_path) for artifact in train_artifacts],
            "replay_reports": [],
            "mean_accuracy": 0.9 if family == "linear_svm" else 0.8,
            "min_accuracy": 0.9 if family == "linear_svm" else 0.8,
            "mean_coverage": 0.95,
        }

    monkeypatch.setattr("natvr.kafka_train_validate.evaluate_family", fake_evaluate_family)
    monkeypatch.setattr("natvr.kafka_train_validate.select_best_model", lambda results: results[1])

    report = run_pipeline(args, progress_messages.append)

    assert report["selected_family"] == "linear_svm"
    assert progress_messages[0] == "Discovering recorded runs from Kafka"
    assert "Selected 1 training runs and 1 validation runs" in progress_messages
    assert "stub training run prepared" in progress_messages
    assert "stub validation run prepared" in progress_messages
    assert "stub evaluating lda" in progress_messages
    assert "stub evaluating linear_svm" in progress_messages
    assert progress_messages[-1] == "Selected linear_svm as the best model"
    assert report["selected_fields"] == ["channels.0.samples", "channels.1.samples"]
    assert report["selected_channel_indexes"] == [0, 1]


def test_run_pipeline_honors_cancellation_checkpoint(monkeypatch, tmp_path) -> None:
    runs = [build_run("demo", 1), build_run("demo", 2)]
    progress_messages: list[str] = []

    args = argparse.Namespace(
        broker="127.0.0.1:29092",
        output_dir=str(tmp_path),
        train_runs=["demo:1"],
        eval_runs=["demo:2"],
        families=["lda"],
        no_direct_assign=False,
        rest_gesture="rest",
        active_gesture="fist",
        window_ms=200,
        hop_ms=50,
        vote_windows=5,
        confidence_threshold=0.6,
        min_hold_windows=2,
        emit_only_during_cue_hold=False,
        selected_fields=[],
    )

    monkeypatch.setattr("natvr.kafka_train_validate.discover_runs", lambda _args: runs)

    def fake_reconstruct(
        args,
        selected_runs,
        *,
        runs_per_session,
        selected_channel_indexes=None,
        progress=None,
        should_stop=None,
        phase_label="run",
    ):
        assert runs_per_session is not None
        assert selected_channel_indexes is None
        if progress is not None:
            progress(f"stub {phase_label} prepared")
        return [
            argparse.Namespace(
                run=run,
                device_id="emg01",
                parquet_path=tmp_path / f"{run.session_id}-{run.run_index}.parquet",
                marker_path=tmp_path / f"{run.session_id}-{run.run_index}.markers.jsonl",
                metadata_path=tmp_path / f"{run.session_id}-{run.run_index}.meta.json",
                feature_path=tmp_path / f"{run.session_id}-{run.run_index}.features.jsonl",
                sample_rate_hz=0,
            )
            for run in selected_runs
        ]

    monkeypatch.setattr(
        "natvr.kafka_train_validate.reconstruct_and_featurize_runs",
        fake_reconstruct,
    )
    monkeypatch.setattr(
        "natvr.kafka_train_validate.evaluate_family",
        lambda *args, **kwargs: {
            "family": "lda",
            "model_path": str(tmp_path / "lda.joblib"),
            "train_feature_paths": [],
            "replay_reports": [],
            "mean_accuracy": 0.8,
            "min_accuracy": 0.8,
            "mean_coverage": 0.9,
        },
    )

    stop_checks = {"count": 0}

    def should_stop() -> bool:
        stop_checks["count"] += 1
        return stop_checks["count"] >= 6

    with pytest.raises(PipelineCancelledError):
        run_pipeline(args, progress_messages.append, should_stop)

    assert "stub training run prepared" in progress_messages
    assert "stub validation run prepared" in progress_messages
