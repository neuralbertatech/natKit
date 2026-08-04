from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from natvr.kafka_train_validate import (
    featurize_instances,
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


def test_resolve_train_eval_runs_allows_missing_eval(monkeypatch) -> None:
    # Validation is optional: with training runs but no eval runs, resolution
    # succeeds (train on the given runs, no held-out set).
    runs = [build_run("demo", 1)]
    args = argparse.Namespace(train_runs=["demo:1"], eval_runs=[])
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    train_runs, eval_runs = resolve_train_eval_runs(args, runs)

    assert [(run.session_id, run.run_index) for run in train_runs] == [("demo", 1)]
    assert eval_runs == []


def test_resolve_train_eval_runs_requires_train_non_tty(monkeypatch) -> None:
    runs = [build_run("demo", 1)]
    args = argparse.Namespace(train_runs=[], eval_runs=[])
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    with pytest.raises(RuntimeError):
        resolve_train_eval_runs(args, runs)


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


def _write_instance_artifacts(directory: Path, *, session_id: str, label: str):
    """Write artifacts in the shape natKit's Parquet exporter produces.

    Deliberately the EXPORTER's schema, not natVR's reconstruction schema: the label
    column is `label`/`label_phase` (not `cue_gesture`/`cue_phase`) and the samples
    are float32. Instance-backed training reads these files directly, so this is the
    contract that matters.
    """
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")

    directory.mkdir(parents=True, exist_ok=True)
    sample_rate = 500
    frames = 40
    samples_per_channel = 25
    start_us = 1_700_000_000_000_000

    rows = {
        "device_id": [],
        "seq_no": [],
        "device_ts_us": [],
        "sample_rate_hz": [],
        "n_channels": [],
        "samples_per_channel": [],
        "channel_0": [],
        "channel_1": [],
        "label": [],
        "label_cue_id": [],
        "label_phase": [],
    }
    for frame in range(frames):
        ts = start_us + frame * samples_per_channel * 1_000_000 // sample_rate
        rows["device_id"].append("emg01")
        rows["seq_no"].append(frame)
        rows["device_ts_us"].append(ts)
        rows["sample_rate_hz"].append(sample_rate)
        rows["n_channels"].append(2)
        rows["samples_per_channel"].append(samples_per_channel)
        # Two separable classes so a model can actually be fit.
        amplitude = 40.5 if frame % 2 == 0 else 5.25
        rows["channel_0"].append([amplitude + (index % 3) for index in range(samples_per_channel)])
        rows["channel_1"].append([amplitude / 2 for _ in range(samples_per_channel)])
        rows["label"].append(label if frame % 2 == 0 else "rest")
        rows["label_cue_id"].append(frame // 2)
        rows["label_phase"].append("hold")

    table = pa.table(rows)
    parquet_path = directory / f"{session_id}.parquet"
    pq.write_table(table, parquet_path)

    markers_path = directory / "markers.jsonl"
    with markers_path.open("w", encoding="utf-8") as handle:
        for frame in range(0, frames, 2):
            ts = start_us + frame * samples_per_channel * 1_000_000 // sample_rate
            cue = label if frame % 4 == 0 else "rest"
            for event, offset in (("start", 0), ("end", 20_000)):
                handle.write(
                    json.dumps(
                        {
                            "session_id": session_id,
                            "marker_type": "cue",
                            "marker_id": f"cue:{frame}",
                            "event": event,
                            "label": cue,
                            "emitted_at_us": ts + offset,
                            "attributes": {"gesture": cue, "phase": "hold", "cue_id": frame},
                        }
                    )
                    + "\n"
                )
    return parquet_path, markers_path


def test_featurize_instances_reads_exporter_artifacts_without_kafka(tmp_path) -> None:
    """Phase 6: an instance's materialized files ARE the dataset.

    No broker is touched — which is the point: reconstruction only works while the
    records are inside retention, so a model could not otherwise be retrained from
    an older session.
    """
    parquet_path, markers_path = _write_instance_artifacts(
        tmp_path / "inst", session_id="finger-counting", label="alpha"
    )
    args = argparse.Namespace(window_ms=100, hop_ms=50)

    artifacts = featurize_instances(
        args,
        [
            {
                "session_id": "finger-counting",
                "run_index": 1,
                "instance_id": "run-0001",
                "parquet": str(parquet_path),
                "markers": str(markers_path),
                "window_start_us": 1,
                "window_end_us": 2,
            }
        ],
        selected_channel_indexes=[0, 1],
    )

    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.run.session_id == "finger-counting"
    assert artifact.run.run_index == 1
    assert artifact.sample_rate_hz == 500
    assert artifact.feature_path.is_file()

    vectors = [json.loads(line) for line in artifact.feature_path.read_text().splitlines() if line]
    assert vectors, "featurization produced no windows"
    # The exporter writes `label`, not `cue_gesture` — if the compatibility fallback
    # regressed, every window would come back unlabelled and a model trained on this
    # would predict one class.
    labels = {vector.get("gesture") for vector in vectors}
    assert labels - {None}, f"no labels survived featurization: {labels}"
    assert "alpha" in labels or "rest" in labels, labels


def test_featurize_instances_fails_loudly_on_a_missing_artifact(tmp_path) -> None:
    args = argparse.Namespace(window_ms=100, hop_ms=50)
    with pytest.raises(RuntimeError, match="missing"):
        featurize_instances(
            args,
            [{"session_id": "x", "run_index": 1, "parquet": str(tmp_path / "nope.parquet")}],
            selected_channel_indexes=None,
        )


def test_rows_to_sample_stream_accepts_both_label_spellings() -> None:
    from natvr.featurize import rows_to_sample_stream

    base = {
        "sample_rate_hz": 100,
        "n_channels": 1,
        "samples_per_channel": 2,
        "channel_0": [1.5, 2.5],
        "device_ts_us": 1000,
    }
    natvr_style, _ = rows_to_sample_stream([{**base, "cue_gesture": "fist", "cue_phase": "hold"}])
    natkit_style, _ = rows_to_sample_stream([{**base, "label": "fist", "label_phase": "hold"}])
    assert [s["gesture"] for s in natvr_style] == ["fist", "fist"]
    assert [s["gesture"] for s in natkit_style] == ["fist", "fist"]
    assert [s["phase"] for s in natkit_style] == ["hold", "hold"]
    # Fractional samples must survive: an IMU's accel/gyro are not integers.
    assert natkit_style[0]["values"] == (1.5,)
