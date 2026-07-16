import argparse
import json
from pathlib import Path

import pytest

from natvr.analysis import (
    build_analysis_output_paths,
    load_feature_rows,
    render_rms_scatter_svg,
    row_to_features,
    summarize_features,
)
from natvr._optional import require_pyarrow
from natvr.classify_replay import build_output_path
from natvr.classifier import (
    ClassifierEngine,
    ClassifierMetricsAccumulator,
    GestureStabilizer,
    SampleWindowBuffer,
    WindowInferenceResult,
    build_window_vector,
    hand_state_from_prediction,
    resolve_classifier_input_topics,
)
from natvr.calibration import CalibrationProfile
from natvr.channel_ablation import (
    build_ablation_output_path,
    parse_channel_counts,
    run_channel_ablation,
)
from natvr.compare_models import build_compare_output_path, compare_models
from natvr.dataset_manifest import (
    build_dataset_manifest,
    build_manifest_output_path,
    build_session_splits,
)
from natvr.baseline import build_dataset, evaluate_leave_one_session_out, train_lda, vector_to_flat_features
from natvr.calibration import (
    DEFAULT_CALIBRATION_PHASES,
    build_calibration_output_path,
    build_calibration_profile,
    normalize_feature_vector,
    select_calibration_vectors,
)
from natvr.dsp import moving_rms, preprocess_channel, rectify
from natvr.cues import (
    active_cue_at_offset,
    build_cue_schedule,
    cue_annotations,
    parse_gesture_list,
    schedule_duration_s,
)
from natvr.emg_consumer import (
    EmgFrameEnvelope,
    EmgGapTracker,
    MarkerEventEnvelope,
    decode_emg_message,
    decode_marker_message,
)
from natvr.features import WindowedFeatureVector, extract_hudgins_features
from natvr.featurize import (
    build_feature_output_path,
    load_rows,
    rows_to_sample_stream,
    window_feature_vectors,
    write_feature_vectors,
)
from natvr.guided_calibration import (
    build_guided_calibration_schedule,
    build_guided_manifest_output_path,
    build_guided_model_output_path,
    write_guided_calibration_outputs,
)
from natvr.libnatkit_stitch import (
    StitchInterval,
    find_libnatkit_core,
    sort_timestamp_order,
    stitch_interval_values,
)
from natvr.markers import (
    align_marker_intervals_python,
    annotate_rows_with_cue_markers,
    annotate_rows_with_marker_stream,
    annotate_rows_with_marker_type,
    build_marker_intervals,
    load_cue_file_markers,
)
from natvr.model import LdaModel
from natvr.predictor import build_model_output_path, load_prediction_model, train_linear_svm
from natvr.models import (
    DeviceStatusV1,
    ExgPillEmgDataSchemaV1,
    HandStateV1,
    MarkerEventV1,
    SessionMetadataRecord,
)
from natvr.recording import (
    SessionMetadata,
    build_cue_path,
    build_output_paths,
    frame_to_row,
    load_extra_metadata,
)
from natvr.reconstruct_session import (
    DiscoveredRun,
    build_reconstruction_stem,
    build_runs_for_session,
    choose_session_metadata_record,
    discover_runs,
    drain_emg_frames_for_window,
    filter_frames_to_window,
    filter_markers_to_window,
    infer_session_window_us,
    resolve_device_id,
    resolve_discovered_run,
    resolve_session_run,
)
from natvr.replay_eval import build_replay_eval_output_path, evaluate_replay_session
from natvr.replay_eval import expected_window_labels
from natvr.replay import (
    ReplayFrame,
    ReplayMarkerContextTracker,
    load_replay_markers,
    load_replay_timeline,
    replay_intervals,
)
from natvr.select_model import (
    build_selection_output_path,
    evaluate_model_families,
    ensure_calibration_path,
    select_best_model,
)
from natvr.session_publish import (
    build_session_lifecycle_marker,
    build_session_metadata_record,
)
from natvr.smoke import build_smoke_summary_output_path, run_smoke_pipeline
from natvr.synthetic import build_synthetic_rows, write_synthetic_session
from natvr.stream_alignment import (
    TimestampedValue,
    align_latest_points_python,
    annotate_rows_with_latest_value,
    assign_latest_points,
    interleave_timestamped_streams,
)
from natvr.topics import (
    cue_marker,
    device_firmware_status,
    device_status,
    emg_raw,
    hand_state,
    imu_quat,
    marker_stream,
    meta_session,
)


def test_topic_helpers() -> None:
    assert emg_raw("emg01") == "Data-1112596048936639351-Json-ExgPillEmgDataSchemaV1"
    assert imu_quat("forearm01") == "Data-8309436325383987184-Json-NatImuDataSchema"
    assert hand_state("sessionA") == "Data-6491625055895967802-Json-HandStateV1"
    assert marker_stream("sessionA") == "Marker-6491625055895967802-Json-MarkerEventV1"
    assert cue_marker("sessionA") == marker_stream("sessionA")
    assert meta_session("sessionA") == "Meta-6491625055895967802-Json-MetaRecord"
    assert device_status("emg01") == "Status-1112596048936639351-Json-DeviceStatusV1"
    assert (
        device_firmware_status("emg01-fw")
        == "Heartbeat-5307678792778866332-Json-DeviceFirmwareStatusV1"
    )


def test_session_split_manifest_is_deterministic(tmp_path) -> None:
    feature_paths = []
    for session_id in ("s1", "s2", "s3"):
        path = tmp_path / f"{session_id}__emg01.features.jsonl"
        path.write_text('{"session_id":"%s"}\n' % session_id, encoding="utf-8")
        feature_paths.append(path)

    splits = build_session_splits(["s1", "s2", "s3"], seed=3)
    manifest = build_dataset_manifest(feature_paths, dataset_name="demo", seed=3)

    assert sorted(manifest["session_ids"]) == ["s1", "s2", "s3"]
    assert manifest["splits"] == splits
    assert not (set(splits["train"]) & set(splits["val"]))
    assert not (set(splits["train"]) & set(splits["test"]))
    assert not (set(splits["val"]) & set(splits["test"]))
    assert build_manifest_output_path(feature_paths[0]).name == "dataset-manifest.json"


def test_emg_frame_round_trip() -> None:
    frame = ExgPillEmgDataSchemaV1(
        device_id="emg01",
        seq_no=42,
        device_ts_us=123456789,
        sample_rate_hz=1000,
        channel_labels=("flexor_a", "extensor_a"),
        channels=((100, 120, 90), (-50, -40, -60)),
    )

    restored = ExgPillEmgDataSchemaV1.from_json_bytes(frame.to_json_bytes())

    assert restored == frame
    assert restored.n_channels == 2
    assert restored.samples_per_channel == 3


def test_emg_frame_uses_canonical_type() -> None:
    frame = ExgPillEmgDataSchemaV1(
        device_id="emg01",
        seq_no=7,
        device_ts_us=55,
        sample_rate_hz=1000,
        channel_labels=("flexor_a",),
        channels=((1, 2, 3),),
    )

    assert isinstance(frame, ExgPillEmgDataSchemaV1)


def test_emg_frame_rejects_mismatched_channel_lengths() -> None:
    with pytest.raises(ValueError):
        ExgPillEmgDataSchemaV1(
            device_id="emg01",
            seq_no=1,
            device_ts_us=1,
            sample_rate_hz=1000,
            channel_labels=("a", "b"),
            channels=((1, 2, 3), (4, 5)),
        )


def test_hand_state_bridge_payload() -> None:
    state = HandStateV1(
        session_id="demo",
        gesture_id="fist",
        confidence=0.91,
        curls=(1.0, 1.0, 1.0, 1.0, 1.0),
        source_window_start_us=1000,
        source_window_end_us=1200,
        emitted_at_us=1300,
        source_device_id="emg01",
    )

    restored = HandStateV1.from_json_bytes(state.to_json_bytes())

    assert restored == state
    assert restored.to_bridge_dict() == {
        "type": "hand_state",
        "ts": 1300,
        "gesture": "fist",
        "conf": 0.91,
        "curls": [1.0, 1.0, 1.0, 1.0, 1.0],
        "window": {"start_us": 1000, "end_us": 1200},
        "device_id": "emg01",
    }


def test_reconstruct_session_uses_session_lifecycle_bounds() -> None:
    markers = [
        MarkerEventV1(
            session_id="demo",
            marker_type="cue",
            marker_id="cue:1",
            event="start",
            label="fist",
            emitted_at_us=2_000,
            attributes={"cue_id": 1},
        ),
        MarkerEventV1(
            session_id="demo",
            marker_type="session",
            marker_id="session:demo",
            event="start",
            label="Session Start",
            emitted_at_us=1_000,
            attributes={},
        ),
        MarkerEventV1(
            session_id="demo",
            marker_type="session",
            marker_id="session:demo",
            event="end",
            label="Session End",
            emitted_at_us=9_000,
            attributes={},
        ),
        MarkerEventV1(
            session_id="demo",
            marker_type="cue",
            marker_id="cue:1",
            event="end",
            label="fist",
            emitted_at_us=8_000,
            attributes={"cue_id": 1},
        ),
    ]

    assert infer_session_window_us(markers) == (1_000, 9_000)
    assert [marker.event for marker in filter_markers_to_window(markers, start_us=1_500, end_us=8_500)] == [
        "start",
        "end",
    ]


def test_reconstruct_session_filters_frames_by_device_and_window() -> None:
    frame_inside = EmgFrameEnvelope(
        frame=ExgPillEmgDataSchemaV1(
            device_id="emg01",
            seq_no=1,
            device_ts_us=5_000,
            sample_rate_hz=1000,
            channel_labels=("a",),
            channels=((1, 2, 3),),
        ),
        topic="demo",
    )
    frame_wrong_device = EmgFrameEnvelope(
        frame=ExgPillEmgDataSchemaV1(
            device_id="emg02",
            seq_no=2,
            device_ts_us=5_500,
            sample_rate_hz=1000,
            channel_labels=("a",),
            channels=((1, 2, 3),),
        ),
        topic="demo",
    )
    frame_outside = EmgFrameEnvelope(
        frame=ExgPillEmgDataSchemaV1(
            device_id="emg01",
            seq_no=3,
            device_ts_us=11_000,
            sample_rate_hz=1000,
            channel_labels=("a",),
            channels=((1, 2, 3),),
        ),
        topic="demo",
    )

    filtered = filter_frames_to_window(
        [frame_wrong_device, frame_inside, frame_outside],
        device_id="emg01",
        start_us=4_000,
        end_us=10_000,
    )

    assert filtered == [frame_inside]


def test_reconstruct_session_prefers_latest_metadata_record() -> None:
    early = SessionMetadataRecord(
        session_id="demo",
        participant_id="old",
        created_at_us=1,
        updated_at_us=2,
    )
    late = SessionMetadataRecord(
        session_id="demo",
        participant_id="new",
        created_at_us=1,
        updated_at_us=3,
    )

    selected = choose_session_metadata_record([early, late], session_id="demo")

    assert selected == late


def test_reconstruct_session_separates_multiple_runs_per_session_id() -> None:
    markers = [
        MarkerEventV1(
            session_id="demo",
            marker_type="session",
            marker_id="session:demo",
            event="start",
            label="training",
            emitted_at_us=1_000,
            attributes={"device_ids": ["emg01"], "participant_id": "p1"},
        ),
        MarkerEventV1(
            session_id="demo",
            marker_type="cue",
            marker_id="cue:1",
            event="start",
            label="fist",
            emitted_at_us=2_000,
            attributes={},
        ),
        MarkerEventV1(
            session_id="demo",
            marker_type="session",
            marker_id="session:demo",
            event="end",
            label="training",
            emitted_at_us=3_000,
            attributes={"device_ids": ["emg01"], "participant_id": "p1"},
        ),
        MarkerEventV1(
            session_id="demo",
            marker_type="session",
            marker_id="session:demo",
            event="start",
            label="training",
            emitted_at_us=10_000,
            attributes={"device_ids": ["emg01"], "participant_id": "p2"},
        ),
        MarkerEventV1(
            session_id="demo",
            marker_type="cue",
            marker_id="cue:2",
            event="start",
            label="open",
            emitted_at_us=11_000,
            attributes={},
        ),
        MarkerEventV1(
            session_id="demo",
            marker_type="session",
            marker_id="session:demo",
            event="end",
            label="training",
            emitted_at_us=12_000,
            attributes={"device_ids": ["emg01"], "participant_id": "p2"},
        ),
    ]
    records = [
        SessionMetadataRecord(
            session_id="demo",
            participant_id="p1",
            device_ids=("emg01",),
            created_at_us=1_000,
            updated_at_us=3_000,
        ),
        SessionMetadataRecord(
            session_id="demo",
            participant_id="p2",
            device_ids=("emg01",),
            created_at_us=10_000,
            updated_at_us=12_000,
        ),
    ]

    runs = build_runs_for_session("demo", markers, records)

    assert [(run.run_index, run.start_us, run.end_us) for run in runs] == [
        (1, 1_000, 3_000),
        (2, 10_000, 12_000),
    ]
    assert [run.participant_id for run in runs] == ["p1", "p2"]
    assert build_reconstruction_stem(
        "demo",
        "emg01",
        run_index=2,
        include_run_index=True,
    ) == "demo__emg01__run-02"


def test_reconstruct_session_builds_metadata_only_runs() -> None:
    records = [
        SessionMetadataRecord(
            session_id="demo",
            participant_id="p1",
            device_ids=("emg01",),
            created_at_us=1_000,
            updated_at_us=1_000,
        ),
        SessionMetadataRecord(
            session_id="demo",
            participant_id="p1",
            device_ids=("emg01",),
            created_at_us=1_000,
            updated_at_us=3_000,
        ),
        SessionMetadataRecord(
            session_id="demo",
            participant_id="p2",
            device_ids=("emg02",),
            created_at_us=10_000,
            updated_at_us=10_000,
        ),
        SessionMetadataRecord(
            session_id="demo",
            participant_id="p2",
            device_ids=("emg02",),
            created_at_us=10_000,
            updated_at_us=12_000,
        ),
    ]

    runs = build_runs_for_session("demo", [], records)

    assert [(run.run_index, run.start_us, run.end_us) for run in runs] == [
        (1, 1_000, 3_000),
        (2, 10_000, 12_000),
    ]
    assert [run.participant_id for run in runs] == ["p1", "p2"]
    assert [run.marker_count for run in runs] == [0, 0]


def test_reconstruct_session_supplements_marker_runs_with_metadata_only_runs() -> None:
    markers = [
        MarkerEventV1(
            session_id="demo",
            marker_type="session",
            marker_id="session:demo",
            event="start",
            label="training",
            emitted_at_us=10_000,
            attributes={"device_ids": ["emg02"], "participant_id": "p2"},
        ),
        MarkerEventV1(
            session_id="demo",
            marker_type="session",
            marker_id="session:demo",
            event="end",
            label="training",
            emitted_at_us=12_000,
            attributes={"device_ids": ["emg02"], "participant_id": "p2"},
        ),
    ]
    records = [
        SessionMetadataRecord(
            session_id="demo",
            participant_id="p1",
            device_ids=("emg01",),
            created_at_us=1_000,
            updated_at_us=3_000,
        ),
        SessionMetadataRecord(
            session_id="demo",
            participant_id="p2",
            device_ids=("emg02",),
            created_at_us=10_000,
            updated_at_us=12_000,
        ),
        SessionMetadataRecord(
            session_id="demo",
            participant_id="p3",
            device_ids=("emg03",),
            created_at_us=20_000,
            updated_at_us=23_000,
        ),
    ]

    runs = build_runs_for_session("demo", markers, records)

    assert [(run.run_index, run.start_us, run.end_us) for run in runs] == [
        (1, 1_000, 3_000),
        (2, 10_000, 12_000),
        (3, 20_000, 23_000),
    ]
    assert [run.participant_id for run in runs] == ["p1", "p2", "p3"]
    assert [run.marker_count for run in runs] == [0, 2, 0]


def test_discover_runs_includes_metadata_only_sessions(monkeypatch) -> None:
    args = argparse.Namespace(
        broker="127.0.0.1:29092",
        group_id="natvr-emg-reconstruct",
        idle_timeout_s=2.0,
        direct_assign=True,
        partition=0,
    )
    records = [
        SessionMetadataRecord(
            session_id="meta-only",
            participant_id="p1",
            device_ids=("emg01",),
            created_at_us=1_000,
            updated_at_us=2_000,
        )
    ]

    monkeypatch.setattr(
        "natvr.reconstruct_session.list_broker_topics",
        lambda **_kwargs: ["Nat_Data_Meta_session_id_meta-only_Json-MetaRecord"],
    )
    monkeypatch.setattr(
        "natvr.reconstruct_session.load_stream_history",
        lambda *_args, **_kwargs: ([], records),
    )

    runs = discover_runs(args)

    assert len(runs) == 1
    assert runs[0].session_id == "meta-only"
    assert runs[0].start_us == 1_000
    assert runs[0].end_us == 2_000


def test_reconstruct_session_prompts_for_missing_session_id(monkeypatch) -> None:
    args = argparse.Namespace(
        session_id=None,
        broker="127.0.0.1:29092",
        group_id="natvr-emg-reconstruct",
        idle_timeout_s=2.0,
        direct_assign=True,
        partition=0,
    )
    runs = [
        DiscoveredRun(
            session_id="older",
            run_index=1,
            start_us=10,
            end_us=20,
            device_ids=("emg01",),
            purpose="training",
            participant_id="",
            protocol_id="",
            tags=(),
            notes="",
            marker_count=3,
            last_activity_us=20,
        ),
        DiscoveredRun(
            session_id="newer",
            run_index=2,
            start_us=30,
            end_us=40,
            device_ids=("emg02",),
            purpose="training",
            participant_id="",
            protocol_id="",
            tags=(),
            notes="",
            marker_count=4,
            last_activity_us=40,
        ),
    ]

    monkeypatch.setattr("natvr.reconstruct_session.discover_runs", lambda _: runs)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "2")

    selected = resolve_discovered_run(args)

    assert selected is not None
    assert selected.session_id == "newer"
    assert selected.run_index == 2


def test_reconstruct_session_prompts_between_multiple_runs_for_session(monkeypatch) -> None:
    args = argparse.Namespace(session_id="demo", run_index=None)
    runs = [
        DiscoveredRun(
            session_id="demo",
            run_index=1,
            start_us=1_000,
            end_us=2_000,
            device_ids=("emg01",),
            purpose="training",
            participant_id="p1",
            protocol_id="",
            tags=(),
            notes="",
            marker_count=10,
            last_activity_us=2_000,
        ),
        DiscoveredRun(
            session_id="demo",
            run_index=2,
            start_us=3_000,
            end_us=4_000,
            device_ids=("emg01",),
            purpose="training",
            participant_id="p2",
            protocol_id="",
            tags=(),
            notes="",
            marker_count=12,
            last_activity_us=4_000,
        ),
    ]

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "2")

    selected = resolve_session_run(args, runs)

    assert selected.run_index == 2
    assert selected.participant_id == "p2"


def test_reconstruct_session_resolves_single_metadata_device_without_prompt() -> None:
    args = argparse.Namespace(device_id=None)
    run = DiscoveredRun(
        session_id="demo",
        run_index=1,
        start_us=1_000,
        end_us=2_000,
        device_ids=("emg01",),
        purpose="training",
        participant_id="",
        protocol_id="",
        tags=(),
        notes="",
        marker_count=2,
        last_activity_us=2_000,
    )

    selected = resolve_device_id(
        args,
        selected_run=run,
        start_us=1_000,
        end_us=2_000,
    )

    assert selected == "emg01"


def test_reconstruct_session_prompts_between_metadata_devices(monkeypatch) -> None:
    args = argparse.Namespace(device_id=None)
    run = DiscoveredRun(
        session_id="demo",
        run_index=1,
        start_us=1_000,
        end_us=2_000,
        device_ids=("emg01", "emg02"),
        purpose="training",
        participant_id="",
        protocol_id="",
        tags=(),
        notes="",
        marker_count=2,
        last_activity_us=2_000,
    )

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "2")

    selected = resolve_device_id(
        args,
        selected_run=run,
        start_us=1_000,
        end_us=2_000,
    )

    assert selected == "emg02"


def test_reconstruct_session_discovers_device_ids_from_window(monkeypatch) -> None:
    args = argparse.Namespace(device_id=None)
    run = DiscoveredRun(
        session_id="demo",
        run_index=1,
        start_us=1_000,
        end_us=2_000,
        device_ids=(),
        purpose="training",
        participant_id="",
        protocol_id="",
        tags=(),
        notes="",
        marker_count=2,
        last_activity_us=2_000,
    )

    monkeypatch.setattr("natvr.reconstruct_session.discover_device_ids_for_window", lambda *a, **k: ["emg03"])

    selected = resolve_device_id(
        args,
        selected_run=run,
        start_us=1_000,
        end_us=2_000,
    )

    assert selected == "emg03"


def test_reconstruct_session_stops_after_window_rollover() -> None:
    frames = iter(
        [
            EmgFrameEnvelope(
                frame=ExgPillEmgDataSchemaV1(
                    device_id="emg01",
                    seq_no=1,
                    device_ts_us=900,
                    sample_rate_hz=1000,
                    channel_labels=("a",),
                    channels=((1, 2),),
                ),
                topic="demo",
            ),
            EmgFrameEnvelope(
                frame=ExgPillEmgDataSchemaV1(
                    device_id="emg01",
                    seq_no=2,
                    device_ts_us=1_100,
                    sample_rate_hz=1000,
                    channel_labels=("a",),
                    channels=((1, 2),),
                ),
                topic="demo",
            ),
            EmgFrameEnvelope(
                frame=ExgPillEmgDataSchemaV1(
                    device_id="emg01",
                    seq_no=3,
                    device_ts_us=2_200,
                    sample_rate_hz=1000,
                    channel_labels=("a",),
                    channels=((1, 2),),
                ),
                topic="demo",
            ),
            EmgFrameEnvelope(
                frame=ExgPillEmgDataSchemaV1(
                    device_id="emg01",
                    seq_no=4,
                    device_ts_us=2_300,
                    sample_rate_hz=1000,
                    channel_labels=("a",),
                    channels=((1, 2),),
                ),
                topic="demo",
            ),
        ]
    )

    def fake_poll(timeout: float = 0.25):
        del timeout
        return next(frames, None)

    selected = drain_emg_frames_for_window(
        fake_poll,
        device_id="emg01",
        start_us=1_000,
        end_us=2_000,
        idle_timeout_s=0.5,
        post_roll_us=0,
        end_streak_required=2,
    )

    assert [frame.frame.seq_no for frame in selected] == [2, 3, 4]


def test_build_dataset_keeps_rest_windows_outside_hold_phase(tmp_path) -> None:
    feature_path = tmp_path / "demo__emg01.features.jsonl"
    feature_rows = [
        WindowedFeatureVector(
            session_id="demo",
            gesture="rest",
            phase="rest",
            start_ts_us=0,
            end_ts_us=1000,
            channel_features=(extract_hudgins_features([0.0, 0.0, 0.0]),),
        ),
        WindowedFeatureVector(
            session_id="demo",
            gesture="fist",
            phase="hold",
            start_ts_us=1000,
            end_ts_us=2000,
            channel_features=(extract_hudgins_features([1.0, 1.0, 1.0]),),
        ),
    ]
    write_feature_vectors(feature_path, feature_rows)

    dataset = build_dataset([feature_path], normalize=False)

    assert [vector.gesture for vector in dataset] == ["rest", "fist"]

    status = DeviceStatusV1(
        device_id="emg01",
        session_id="demo",
        sample_rate_hz=1000,
        windows_processed=12,
        states_emitted=5,
        mean_compute_ms=0.4,
        max_compute_ms=0.8,
        mean_end_to_end_ms=18.0,
        last_compute_ms=0.5,
        last_end_to_end_ms=20.0,
        last_gesture_id="fist",
        emitted_at_us=1400,
    )
    restored_status = DeviceStatusV1.from_json_bytes(status.to_json_bytes())
    assert restored_status == status


def test_gap_tracking_and_record_row_shape(tmp_path) -> None:
    topic = emg_raw("emg01")
    tracker = EmgGapTracker()
    first = ExgPillEmgDataSchemaV1(
        device_id="emg01",
        seq_no=10,
        device_ts_us=1000,
        sample_rate_hz=1000,
        channel_labels=("flexor_a", "extensor_a"),
        channels=((1, 2), (3, 4)),
    )
    second = ExgPillEmgDataSchemaV1(
        device_id="emg01",
        seq_no=13,
        device_ts_us=1300,
        sample_rate_hz=1000,
        channel_labels=("flexor_a", "extensor_a"),
        channels=((5, 6), (7, 8)),
    )

    env1 = decode_emg_message(first.to_json_bytes(), topic=topic, gap_tracker=tracker)
    env2 = decode_emg_message(second.to_json_bytes(), topic=topic, gap_tracker=tracker)

    assert env1.sequence_gap == 0
    assert env2.sequence_gap == 2

    row = frame_to_row(env2, annotations={"cue_gesture": "fist", "cue_phase": "hold"})
    assert row["channel_0"] == [5, 6]
    assert row["channel_1"] == [7, 8]
    assert row["sequence_gap"] == 2
    assert row["cue_gesture"] == "fist"

    metadata = SessionMetadata(
        session_id="demo",
        device_id="emg01",
        topic=topic,
        channel_map=["flexor_a", "extensor_a"],
    )
    _, metadata_path = build_output_paths(tmp_path, "demo", "emg01")
    cue_path = build_cue_path(tmp_path, "demo", "emg01")
    metadata.write_json(metadata_path)
    assert '"session_id": "demo"' in metadata_path.read_text(encoding="utf-8")
    assert cue_path.name == "demo__emg01.cues.json"


def test_decode_marker_message_round_trip() -> None:
    marker = MarkerEventV1(
        session_id="demo",
        marker_type="cue",
        marker_id="cue:1",
        event="start",
        label="fist",
        emitted_at_us=123456,
        attributes={"phase": "hold", "gesture": "fist"},
    )

    envelope = decode_marker_message(
        marker.to_json_bytes(),
        topic=marker_stream("demo"),
        partition=2,
        offset=11,
        broker_received_at_us=123999,
    )

    assert isinstance(envelope, MarkerEventEnvelope)
    assert envelope.marker == marker
    assert envelope.topic == marker_stream("demo")
    assert envelope.partition == 2
    assert envelope.offset == 11
    assert envelope.broker_received_at_us == 123999


def test_session_metadata_record_meta_record_round_trip() -> None:
    record = SessionMetadataRecord(
        session_id="demo",
        purpose="training",
        participant_id="p001",
        protocol_id="gesture-v1",
        device_ids=("emg01",),
        tags=("pilot", "right-arm"),
        notes="seated",
        created_at_us=100,
        updated_at_us=120,
    )

    encoded = record.to_meta_record_json_bytes()
    restored = SessionMetadataRecord.from_meta_record_json_bytes(encoded)

    assert restored == record


def test_session_publish_builders_create_metadata_and_session_markers() -> None:
    record = build_session_metadata_record(
        session_id="demo",
        purpose="training",
        participant_id="p001",
        protocol_id="gesture-v1",
        device_ids=["emg01"],
        tags=["pilot"],
        notes="seated",
        created_at_us=100,
        updated_at_us=120,
    )
    start_marker = build_session_lifecycle_marker(
        record,
        event="start",
        emitted_at_us=130,
    )
    end_marker = build_session_lifecycle_marker(
        record,
        event="end",
        emitted_at_us=200,
    )

    assert record.session_id == "demo"
    assert record.device_ids == ("emg01",)
    assert start_marker.marker_type == "session"
    assert start_marker.marker_id == "session:demo"
    assert start_marker.event == "start"
    assert start_marker.attributes["purpose"] == "training"
    assert end_marker.event == "end"


def test_classifier_input_topics_default_to_emg_and_marker_streams() -> None:
    assert resolve_classifier_input_topics(
        device_id="emg01",
        session_id="sessionA",
    ) == (
        emg_raw("emg01"),
        marker_stream("sessionA"),
    )
    assert resolve_classifier_input_topics(
        device_id="emg01",
        session_id="sessionA",
        disable_marker_stream=True,
    ) == (
        emg_raw("emg01"),
        None,
    )


def test_replay_intervals_and_metadata_json() -> None:
    topic = emg_raw("emg01")
    frames = [
        ReplayFrame(
            frame=ExgPillEmgDataSchemaV1(
                device_id="emg01",
                seq_no=1,
                device_ts_us=1_000_000,
                sample_rate_hz=1000,
                channel_labels=("a",),
                channels=((1, 2),),
            ),
            topic=topic,
        ),
        ReplayFrame(
            frame=ExgPillEmgDataSchemaV1(
                device_id="emg01",
                seq_no=2,
                device_ts_us=1_050_000,
                sample_rate_hz=1000,
                channel_labels=("a",),
                channels=((3, 4),),
            ),
            topic=topic,
        ),
        ReplayFrame(
            frame=ExgPillEmgDataSchemaV1(
                device_id="emg01",
                seq_no=3,
                device_ts_us=1_150_000,
                sample_rate_hz=1000,
                channel_labels=("a",),
                channels=((5, 6),),
            ),
            topic=topic,
        ),
    ]

    assert list(replay_intervals(frames, speed=2.0)) == [0.025, 0.05]
    assert load_extra_metadata('{"subject":"zach","day":2}') == {
        "subject": "zach",
        "day": 2,
    }


def test_cue_schedule_and_lookup_are_deterministic() -> None:
    schedule = build_cue_schedule(
        parse_gesture_list("fist,open,pinch"),
        repetitions=2,
        hold_s=3.0,
        rest_s=2.0,
        lead_in_s=1.0,
        tail_rest_s=1.0,
        seed=7,
    )

    assert schedule[0].phase == "lead_in"
    assert schedule[1].phase == "hold"
    assert schedule[1].gesture == "pinch"
    assert schedule_duration_s(schedule) == 32.0

    active = active_cue_at_offset(schedule, 1.5)
    assert active is not None
    assert cue_annotations(active) == {
        "cue_id": 1,
        "cue_phase": "hold",
        "cue_gesture": "pinch",
        "cue_prompt": "pinch",
    }


def test_cue_markers_round_trip_and_stitching(tmp_path) -> None:
    marker = MarkerEventV1(
        session_id="demo",
        marker_type="cue",
        marker_id="cue:3",
        event="start",
        label="fist",
        emitted_at_us=1_000_000,
        attributes={
            "cue_id": 3,
            "phase": "hold",
            "gesture": "fist",
            "prompt": "fist",
        },
    )
    assert MarkerEventV1.from_json_bytes(marker.to_json_bytes()) == marker

    cue_path = tmp_path / "demo__emg01.cues.json"
    cue_path.write_text(
        json.dumps(
            {
                "session_id": "demo",
                "device_id": "emg01",
                "started_at_utc": "2026-06-25T00:00:00+00:00",
                "events": [
                    {
                        "cue_id": 0,
                        "rep_index": -1,
                        "phase": "lead_in",
                        "gesture": "rest",
                        "prompt": "Prepare",
                        "start_offset_s": 0.0,
                        "end_offset_s": 1.0,
                        "start_ts_us": 1_000_000,
                        "end_ts_us": 2_000_000,
                    },
                    {
                        "cue_id": 1,
                        "rep_index": 0,
                        "phase": "hold",
                        "gesture": "fist",
                        "prompt": "fist",
                        "start_offset_s": 1.0,
                        "end_offset_s": 3.0,
                        "start_ts_us": 2_000_000,
                        "end_ts_us": 4_000_000,
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    markers = load_cue_file_markers(cue_path)
    replay_markers = load_replay_markers(cue_path)
    assert [(marker.event, marker.attributes["cue_id"]) for marker in markers] == [
        ("start", 0),
        ("end", 0),
        ("start", 1),
        ("end", 1),
    ]
    assert replay_markers[0].delay_s == 0.0
    assert replay_markers[1].delay_s == 1.0

    rows = [
        {
            "device_ts_us": 1_500_000,
            "broker_received_at_us": 9_500_000,
            "n_channels": 1,
            "channel_0": [1],
        },
        {
            "device_ts_us": 2_500_000,
            "broker_received_at_us": 9_600_000,
            "n_channels": 1,
            "channel_0": [2],
        },
        {
            "device_ts_us": 4_500_000,
            "broker_received_at_us": 9_700_000,
            "n_channels": 1,
            "channel_0": [3],
        },
    ]
    annotated = annotate_rows_with_cue_markers(rows, markers)
    assert annotated[0]["cue_gesture"] == "rest"
    assert annotated[1]["cue_gesture"] == "fist"
    assert "cue_gesture" not in annotated[2]

    cue_intervals = build_marker_intervals(markers, marker_type="cue")
    assert [
        (
            interval.marker.attributes["cue_id"],
            interval.start_time_us,
            interval.end_time_us,
        )
        for interval in cue_intervals
    ] == [(0, 1_000_000, 2_000_000), (1, 2_000_000, 4_000_000)]


def test_python_interval_alignment_prefers_latest_active_interval() -> None:
    assignments = align_marker_intervals_python(
        [50, 150, 250, 350, 450],
        [
            StitchInterval(start_time_us=100, end_time_us=400, value=7),
            StitchInterval(start_time_us=200, end_time_us=300, value=9),
        ],
    )
    assert assignments == [-1, 7, 9, 7, -1]


def test_native_interval_alignment_when_libnatkit_core_is_built() -> None:
    if find_libnatkit_core() is None:
        pytest.skip("libnatkit-core shared library not built")

    assignments = stitch_interval_values(
        [50, 150, 250, 350, 450],
        [
            StitchInterval(start_time_us=100, end_time_us=400, value=7),
            StitchInterval(start_time_us=200, end_time_us=300, value=9),
        ],
    )
    assert assignments == [-1, 7, 9, 7, -1]


def test_python_point_alignment_uses_latest_timestamped_value() -> None:
    assignments = align_latest_points_python(
        [50, 150, 250, 350],
        [
            TimestampedValue(timestamp_us=100, value=3),
            TimestampedValue(timestamp_us=200, value=5),
        ],
    )
    assert assignments == [-1, 3, 5, 5]


def test_native_point_alignment_when_libnatkit_core_is_built() -> None:
    if find_libnatkit_core() is None:
        pytest.skip("libnatkit-core shared library not built")

    assignments = assign_latest_points(
        [50, 150, 250, 350],
        [
            TimestampedValue(timestamp_us=100, value=3),
            TimestampedValue(timestamp_us=200, value=5),
        ],
    )
    assert assignments == [-1, 3, 5, 5]


def test_annotate_rows_with_latest_value_uses_device_timestamp() -> None:
    rows = [
        {"device_ts_us": 1_500_000, "broker_received_at_us": 8_000_000},
        {"device_ts_us": 2_500_000, "broker_received_at_us": 7_000_000},
    ]
    points = [
        TimestampedValue(timestamp_us=1_000_000, value=11),
        TimestampedValue(timestamp_us=2_000_000, value=12),
    ]

    annotated = annotate_rows_with_latest_value(
        rows,
        points,
        output_field="status_code",
    )

    assert annotated == [
        {
            "device_ts_us": 1_500_000,
            "broker_received_at_us": 8_000_000,
            "status_code": 11,
        },
        {
            "device_ts_us": 2_500_000,
            "broker_received_at_us": 7_000_000,
            "status_code": 12,
        },
    ]


def test_interleave_timestamped_streams_orders_by_timestamp() -> None:
    streams = {
        "emg": [
            {"device_ts_us": 300, "seq_no": 3},
            {"device_ts_us": 100, "seq_no": 1},
        ],
        "marker": [
            {"device_ts_us": 200, "marker_id": "m1"},
        ],
    }

    interleaved = interleave_timestamped_streams(streams)

    assert [(row["stream_name"], row["device_ts_us"]) for row in interleaved] == [
        ("emg", 100),
        ("marker", 200),
        ("emg", 300),
    ]


def test_native_timestamp_sort_when_libnatkit_core_is_built() -> None:
    if find_libnatkit_core() is None:
        pytest.skip("libnatkit-core shared library not built")

    assert sort_timestamp_order([300, 100, 200]) == [1, 2, 0]


def test_generic_marker_type_annotation_is_timestamp_based() -> None:
    markers = [
        MarkerEventV1(
            session_id="demo",
            marker_type="trial",
            marker_id="trial:7",
            event="start",
            label="block-a",
            emitted_at_us=1_000_000,
            attributes={"phase": "reach", "rep index": 2},
        ),
        MarkerEventV1(
            session_id="demo",
            marker_type="trial",
            marker_id="trial:7",
            event="end",
            label="block-a",
            emitted_at_us=2_000_000,
            attributes={"phase": "reach", "rep index": 2},
        ),
    ]
    rows = [
        {"device_ts_us": 1_500_000, "broker_received_at_us": 9_100_000},
        {"device_ts_us": 2_500_000, "broker_received_at_us": 1_100_000},
    ]

    annotated = annotate_rows_with_marker_type(
        rows,
        markers,
        marker_type="trial",
    )

    assert annotated[0]["trial_marker_type"] == "trial"
    assert annotated[0]["trial_marker_id"] == "trial:7"
    assert annotated[0]["trial_label"] == "block-a"
    assert annotated[0]["trial_phase"] == "reach"
    assert annotated[0]["trial_rep_index"] == 2
    assert "trial_marker_type" not in annotated[1]


def test_marker_stream_annotation_namespaces_multiple_types() -> None:
    markers = [
        MarkerEventV1(
            session_id="demo",
            marker_type="cue",
            marker_id="cue:1",
            event="start",
            label="fist",
            emitted_at_us=1_000_000,
            attributes={"cue_id": 1, "phase": "hold"},
        ),
        MarkerEventV1(
            session_id="demo",
            marker_type="cue",
            marker_id="cue:1",
            event="end",
            label="fist",
            emitted_at_us=3_000_000,
            attributes={"cue_id": 1, "phase": "hold"},
        ),
        MarkerEventV1(
            session_id="demo",
            marker_type="trial",
            marker_id="trial:9",
            event="start",
            label="block-b",
            emitted_at_us=1_500_000,
            attributes={"block": 9},
        ),
        MarkerEventV1(
            session_id="demo",
            marker_type="trial",
            marker_id="trial:9",
            event="end",
            label="block-b",
            emitted_at_us=2_500_000,
            attributes={"block": 9},
        ),
    ]
    rows = [{"device_ts_us": 2_000_000}]

    annotated = annotate_rows_with_marker_stream(rows, markers)

    assert annotated[0]["cue_marker_type"] == "cue"
    assert annotated[0]["cue_cue_id"] == 1
    assert annotated[0]["trial_marker_type"] == "trial"
    assert annotated[0]["trial_block"] == 9


def test_load_rows_and_expected_labels_can_stitch_marker_side_stream(tmp_path) -> None:
    try:
        pa, pq = require_pyarrow()
    except RuntimeError:
        pytest.skip("pyarrow not installed")

    parquet_path = tmp_path / "demo__emg01.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "schema_version": "exg.pill.emg.data.v1",
                    "topic": "Data-demo-Json-ExgPillEmgDataSchemaV1",
                    "device_id": "emg01",
                    "seq_no": 1,
                    "device_ts_us": 1_000_000,
                    "broker_received_at_us": 9_000_000,
                    "sample_rate_hz": 1000,
                    "n_channels": 1,
                    "samples_per_channel": 4,
                    "channel_labels": ["c0"],
                    "channel_0": [1, 2, 3, 4],
                },
                {
                    "schema_version": "exg.pill.emg.data.v1",
                    "topic": "Data-demo-Json-ExgPillEmgDataSchemaV1",
                    "device_id": "emg01",
                    "seq_no": 2,
                    "device_ts_us": 2_000_000,
                    "broker_received_at_us": 8_000_000,
                    "sample_rate_hz": 1000,
                    "n_channels": 1,
                    "samples_per_channel": 4,
                    "channel_labels": ["c0"],
                    "channel_0": [5, 6, 7, 8],
                },
            ]
        ),
        parquet_path,
    )

    cue_path = tmp_path / "demo__emg01.cues.json"
    cue_path.write_text(
        json.dumps(
            {
                "session_id": "demo",
                "device_id": "emg01",
                "started_at_utc": "2026-06-25T00:00:00+00:00",
                "events": [
                    {
                        "cue_id": 1,
                        "rep_index": 0,
                        "phase": "hold",
                        "gesture": "fist",
                        "prompt": "fist",
                        "start_offset_s": 0.0,
                        "end_offset_s": 3.0,
                        "start_ts_us": 900_000,
                        "end_ts_us": 3_000_000,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rows = load_rows(parquet_path, marker_path=cue_path)
    assert rows[0]["cue_gesture"] == "fist"
    assert rows[1]["cue_gesture"] == "fist"

    features = load_feature_rows(parquet_path, marker_path=cue_path)
    assert [feature.cue_gesture for feature in features] == ["fist", "fist"]

    expected = expected_window_labels(
        parquet_path,
        marker_path=cue_path,
        window_ms=2,
        hop_ms=2,
    )
    assert expected
    assert all(value["gesture"] == "fist" for value in expected.values())


def test_load_replay_timeline_interleaves_frames_and_markers(tmp_path) -> None:
    try:
        pa, pq = require_pyarrow()
    except RuntimeError:
        pytest.skip("pyarrow not installed")

    parquet_path = tmp_path / "demo__emg01.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "schema_version": "exg.pill.emg.data.v1",
                    "topic": "Data-demo-Json-ExgPillEmgDataSchemaV1",
                    "device_id": "emg01",
                    "seq_no": 1,
                    "device_ts_us": 1_000_000,
                    "broker_received_at_us": 1_100_000,
                    "sample_rate_hz": 1000,
                    "n_channels": 1,
                    "samples_per_channel": 2,
                    "channel_labels": ["c0"],
                    "channel_0": [1, 2],
                },
                {
                    "schema_version": "exg.pill.emg.data.v1",
                    "topic": "Data-demo-Json-ExgPillEmgDataSchemaV1",
                    "device_id": "emg01",
                    "seq_no": 2,
                    "device_ts_us": 3_000_000,
                    "broker_received_at_us": 3_100_000,
                    "sample_rate_hz": 1000,
                    "n_channels": 1,
                    "samples_per_channel": 2,
                    "channel_labels": ["c0"],
                    "channel_0": [3, 4],
                },
            ]
        ),
        parquet_path,
    )
    marker_path = tmp_path / "markers.jsonl"
    marker_path.write_text(
        "\n".join(
            [
                json.dumps(
                    MarkerEventV1(
                        session_id="demo",
                        marker_type="trial",
                        marker_id="trial:1",
                        event="start",
                        label="a",
                        emitted_at_us=2_000_000,
                        attributes={},
                    ).to_dict()
                ),
                json.dumps(
                    MarkerEventV1(
                        session_id="demo",
                        marker_type="trial",
                        marker_id="trial:1",
                        event="end",
                        label="a",
                        emitted_at_us=4_000_000,
                        attributes={},
                    ).to_dict()
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    timeline = load_replay_timeline(parquet_path, marker_path=marker_path)

    assert [(event.kind, event.timestamp_us) for event in timeline] == [
        ("emg", 1_000_000),
        ("marker", 2_000_000),
        ("emg", 3_000_000),
        ("marker", 4_000_000),
    ]


def test_replay_marker_context_tracker_emits_active_cue_context() -> None:
    tracker = ReplayMarkerContextTracker()
    cue_start = MarkerEventV1(
        session_id="demo",
        marker_type="cue",
        marker_id="cue:4",
        event="start",
        label="fist",
        emitted_at_us=1_000_000,
        attributes={
            "cue_id": 4,
            "phase": "hold",
            "gesture": "fist",
            "prompt": "fist",
        },
    )
    trial_start = MarkerEventV1(
        session_id="demo",
        marker_type="trial",
        marker_id="trial:2",
        event="start",
        label="block-a",
        emitted_at_us=1_500_000,
        attributes={"block": 2},
    )
    cue_end = MarkerEventV1(
        session_id="demo",
        marker_type="cue",
        marker_id="cue:4",
        event="end",
        label="fist",
        emitted_at_us=2_000_000,
        attributes={},
    )

    tracker.observe(cue_start)
    tracker.observe(trial_start)
    context = tracker.to_output_context()
    assert context["cue_id"] == 4
    assert context["cue_phase"] == "hold"
    assert context["cue_gesture"] == "fist"
    assert context["cue_prompt"] == "fist"
    assert context["active_markers"] == {
        "cue": {
            "marker_type": "cue",
            "marker_id": "cue:4",
            "label": "fist",
            "session_id": "demo",
            "emitted_at_us": 1_000_000,
            "attributes": {
                "cue_id": 4,
                "phase": "hold",
                "gesture": "fist",
                "prompt": "fist",
            },
        },
        "trial": {
            "marker_type": "trial",
            "marker_id": "trial:2",
            "label": "block-a",
            "session_id": "demo",
            "emitted_at_us": 1_500_000,
            "attributes": {"block": 2},
        },
    }

    tracker.observe(cue_end)
    context = tracker.to_output_context()
    assert "cue_id" not in context
    assert context["active_markers"] == {
        "trial": {
            "marker_type": "trial",
            "marker_id": "trial:2",
            "label": "block-a",
            "session_id": "demo",
            "emitted_at_us": 1_500_000,
            "attributes": {"block": 2},
        }
    }


def test_classifier_engine_can_gate_on_active_cue_hold_context() -> None:
    class AlwaysFistModel:
        def predict_one(self, features: list[float]) -> str:
            del features
            return "fist"

        def predict_confidence(self, features: list[float]) -> tuple[str, float]:
            del features
            return "fist", 0.95

    engine = ClassifierEngine(
        device_id="emg01",
        session_id="demo",
        sample_rate_hz=1000,
        model=AlwaysFistModel(),
        calibration=CalibrationProfile(
            session_id="demo",
            rest_mean_rms=(0.0,),
            active_mean_rms=(1.0,),
            scale_rms=(1.0,),
        ),
        window_ms=2,
        hop_ms=2,
        vote_windows=1,
        confidence_threshold=0.1,
        min_hold_windows=1,
        emit_only_during_cue_hold=True,
    )

    results = engine.process_frame_detailed(
        device_ts_us=1_000_000,
        channels=((100, 100),),
    )
    assert len(results) == 1
    assert results[0].emitted_state is None
    assert results[0].active_marker_context == {}

    engine.observe_marker_event(
        MarkerEventV1(
            session_id="demo",
            marker_type="cue",
            marker_id="cue:1",
            event="start",
            label="fist",
            emitted_at_us=1_100_000,
            attributes={
                "cue_id": 1,
                "phase": "hold",
                "gesture": "fist",
                "prompt": "fist",
            },
        )
    )

    results = engine.process_frame_detailed(
        device_ts_us=2_000_000,
        channels=((100, 100),),
    )
    assert len(results) == 1
    assert results[0].emitted_state is not None
    assert results[0].active_marker_context["cue_gesture"] == "fist"
    assert results[0].active_marker_context["cue_phase"] == "hold"


def test_analysis_summary_and_svg_output(tmp_path) -> None:
    rows = [
        {
            "n_channels": 2,
            "channel_0": [1, 1, 1, 1],
            "channel_1": [2, 2, 2, 2],
            "cue_gesture": "rest",
            "cue_phase": "hold",
            "device_ts_us": 1000,
        },
        {
            "n_channels": 2,
            "channel_0": [3, 3, 3, 3],
            "channel_1": [4, 4, 4, 4],
            "cue_gesture": "fist",
            "cue_phase": "hold",
            "device_ts_us": 2000,
        },
        {
            "n_channels": 2,
            "channel_0": [5, 5, 5, 5],
            "channel_1": [6, 6, 6, 6],
            "cue_gesture": "fist",
            "cue_phase": "hold",
            "device_ts_us": 3000,
        },
    ]
    features = [feature for feature in (row_to_features(row) for row in rows) if feature is not None]
    summary = summarize_features(features)

    assert summary["frames_considered"] == 3
    assert summary["gestures"]["rest"]["mean_rms"] == [1.0, 2.0]
    assert summary["gestures"]["fist"]["mean_rms"] == [4.0, 5.0]
    assert summary["rest_delta_rms"]["fist"] == [3.0, 3.0]

    svg = render_rms_scatter_svg(features, channel_x=0, channel_y=1)
    assert "<svg" in svg
    assert "RMS separability scatter" in svg
    assert "#0f766e" in svg

    summary_path, scatter_path = build_analysis_output_paths(tmp_path / "demo__emg01.parquet")
    assert summary_path.name == "demo__emg01.summary.json"
    assert scatter_path.name == "demo__emg01.scatter.svg"


def test_dsp_and_hudgins_features() -> None:
    samples = [1.0, -1.0, 1.0, -1.0]
    assert rectify(samples) == [1.0, 1.0, 1.0, 1.0]
    assert moving_rms([1.0, 1.0, 1.0, 1.0], window_size=2) == [1.0, 1.0, 1.0, 1.0]

    processed = preprocess_channel(
        [1, -1, 1, -1, 1, -1],
        sample_rate_hz=1000,
        notch_harmonics=1,
        highpass_hz=None,
        rectify_signal=False,
    )
    assert len(processed) == 6

    features = extract_hudgins_features([1.0, -1.0, 1.0, -1.0])
    assert features.mav == 1.0
    assert features.rms == 1.0
    assert features.zero_crossings == 3
    assert features.slope_sign_changes == 2
    assert features.waveform_length == 6.0


def test_featurize_window_builder() -> None:
    rows = [
        {
            "device_ts_us": 1_000_000,
            "sample_rate_hz": 1000,
            "n_channels": 2,
            "samples_per_channel": 4,
            "channel_0": [1, 2, 3, 4],
            "channel_1": [4, 3, 2, 1],
            "cue_gesture": "fist",
            "cue_phase": "hold",
        },
        {
            "device_ts_us": 1_004_000,
            "sample_rate_hz": 1000,
            "n_channels": 2,
            "samples_per_channel": 4,
            "channel_0": [5, 6, 7, 8],
            "channel_1": [8, 7, 6, 5],
            "cue_gesture": "fist",
            "cue_phase": "hold",
        },
    ]
    stream, sample_rate_hz = rows_to_sample_stream(rows)
    assert len(stream) == 8
    assert sample_rate_hz == 1000
    assert stream[0]["values"] == (1, 4)

    selected_stream, selected_rate = rows_to_sample_stream(
        rows,
        selected_channel_indexes=[1],
    )
    assert len(selected_stream) == 8
    assert selected_rate == 1000
    assert selected_stream[0]["values"] == (4,)

    windows = window_feature_vectors(
        stream,
        sample_rate_hz=sample_rate_hz,
        session_id="demo",
        window_ms=4,
        hop_ms=2,
        highpass_hz=None,
        rectify_signal=False,
    )
    assert len(windows) == 3
    assert windows[0].session_id == "demo"
    assert windows[0].gesture == "fist"
    assert len(windows[0].channel_features) == 2
    assert build_feature_output_path(Path("demo__emg01.parquet")).name == "demo__emg01.features.jsonl"


def test_calibration_and_baseline_pipeline() -> None:
    session_a = [
        WindowedFeatureVector(
            session_id="session-a",
            gesture="rest",
            phase="hold",
            start_ts_us=0,
            end_ts_us=1,
            channel_features=(
                extract_hudgins_features([1.0, 1.0, 1.0, 1.0]),
                extract_hudgins_features([1.0, 1.0, 1.0, 1.0]),
            ),
        ),
        WindowedFeatureVector(
            session_id="session-a",
            gesture="fist",
            phase="hold",
            start_ts_us=2,
            end_ts_us=3,
            channel_features=(
                extract_hudgins_features([4.0, 4.0, 4.0, 4.0]),
                extract_hudgins_features([4.0, 4.0, 4.0, 4.0]),
            ),
        ),
    ]
    session_b = [
        WindowedFeatureVector(
            session_id="session-b",
            gesture="rest",
            phase="hold",
            start_ts_us=4,
            end_ts_us=5,
            channel_features=(
                extract_hudgins_features([1.1, 1.1, 1.1, 1.1]),
                extract_hudgins_features([1.1, 1.1, 1.1, 1.1]),
            ),
        ),
        WindowedFeatureVector(
            session_id="session-b",
            gesture="fist",
            phase="hold",
            start_ts_us=6,
            end_ts_us=7,
            channel_features=(
                extract_hudgins_features([4.2, 4.2, 4.2, 4.2]),
                extract_hudgins_features([4.2, 4.2, 4.2, 4.2]),
            ),
        ),
    ]

    profile = build_calibration_profile(session_a, rest_gesture="rest", active_gesture="fist")
    assert profile.rest_mean_rms == (1.0, 1.0)
    assert profile.active_mean_rms == (4.0, 4.0)
    assert profile.scale_rms == (3.0, 3.0)
    assert build_calibration_output_path(Path("demo.features.jsonl")).name == "demo.calibration.json"

    normalized = normalize_feature_vector(session_a[1], profile)
    assert round(normalized.channel_features[0].rms, 6) == 1.0

    model = train_lda(
        [
            (vector_to_flat_features(normalize_feature_vector(vector, profile)), str(vector.gesture))
            for vector in session_a
        ]
    )
    assert model.predict_one(vector_to_flat_features(normalize_feature_vector(session_a[0], profile))) == "rest"

    report = evaluate_leave_one_session_out(
        [
            normalize_feature_vector(vector, build_calibration_profile(session_a))
            for vector in session_a
        ]
        + [
            normalize_feature_vector(vector, build_calibration_profile(session_b))
            for vector in session_b
        ]
    )
    assert report["overall_samples"] == 4
    assert report["overall_accuracy"] == 1.0


def test_calibration_phase_selection_defaults_to_hold() -> None:
    vectors = [
        WindowedFeatureVector(
            session_id="session-a",
            gesture="rest",
            phase="hold",
            start_ts_us=0,
            end_ts_us=1,
            channel_features=(extract_hudgins_features([1.0, 1.0, 1.0, 1.0]),),
        ),
        WindowedFeatureVector(
            session_id="session-a",
            gesture="rest",
            phase="rest",
            start_ts_us=2,
            end_ts_us=3,
            channel_features=(extract_hudgins_features([2.0, 2.0, 2.0, 2.0]),),
        ),
        WindowedFeatureVector(
            session_id="session-a",
            gesture="fist",
            phase="hold",
            start_ts_us=4,
            end_ts_us=5,
            channel_features=(extract_hudgins_features([4.0, 4.0, 4.0, 4.0]),),
        ),
        WindowedFeatureVector(
            session_id="session-a",
            gesture="fist",
            phase="max_squeeze",
            start_ts_us=6,
            end_ts_us=7,
            channel_features=(extract_hudgins_features([5.0, 5.0, 5.0, 5.0]),),
        ),
    ]

    selected = select_calibration_vectors(vectors)
    assert DEFAULT_CALIBRATION_PHASES == ("hold",)
    assert [vector.phase for vector in selected] == ["hold", "hold"]

    expanded = select_calibration_vectors(vectors, phases=("hold", "max_squeeze"))
    assert [vector.phase for vector in expanded] == ["hold", "hold", "max_squeeze"]


def test_model_artifact_and_classifier_helpers(tmp_path) -> None:
    model = train_lda(
        [
            ([0.0, 0.0], "rest"),
            ([1.0, 1.0], "fist"),
        ]
    )
    predicted, confidence = model.predict_confidence([0.9, 1.0])
    assert predicted == "fist"
    assert 0.5 <= confidence <= 1.0

    model_path = build_model_output_path(tmp_path / "demo.features.jsonl", "lda")
    model.save_json(model_path)
    restored = LdaModel.load_json(model_path)
    assert restored.predict_one([0.0, 0.0]) == "rest"

    svm_artifact = train_linear_svm(
        [
            ([0.0, 0.0], "rest"),
            ([1.0, 1.0], "fist"),
        ]
    )
    svm_path = build_model_output_path(tmp_path / "demo.features.jsonl", "linear_svm")
    svm_artifact.save_joblib(svm_path)
    restored_svm = load_prediction_model(svm_path)
    assert restored_svm.predict_one([0.9, 1.0]) == "fist"

    buffer = SampleWindowBuffer(sample_rate_hz=1000, window_ms=4, hop_ms=2)
    buffer.add_frame(1_000_000, ((1, 2, 3, 4), (4, 3, 2, 1)))
    assert buffer.pop_next_window() is not None

    vector = build_window_vector(
        [(1, 4), (2, 3), (3, 2), (4, 1)],
        sample_rate_hz=1000,
        start_ts_us=1_000_000,
        end_ts_us=1_003_000,
    )
    assert len(vector.channel_features) == 2

    stabilizer = GestureStabilizer(vote_windows=3, confidence_threshold=0.5, min_hold_windows=1)
    assert stabilizer.update("fist", 0.9)[0] is None
    assert stabilizer.update("fist", 0.9)[0] is None
    gesture, stable_conf = stabilizer.update("fist", 0.9)
    assert gesture == "fist"
    assert stable_conf == 1.0

    state = hand_state_from_prediction(
        session_id="demo",
        device_id="emg01",
        gesture="point",
        confidence=0.8,
        start_ts_us=10,
        end_ts_us=20,
    )
    assert state.gesture_id == "point"
    assert state.curls == (0.7, 0.0, 1.0, 1.0, 1.0)
    assert build_output_path(Path("demo__emg01.parquet")).name == "demo__emg01.hand-state.jsonl"

    metrics = ClassifierMetricsAccumulator()
    metrics.observe(
        WindowInferenceResult(
            start_ts_us=10,
            end_ts_us=20,
            predicted_gesture="point",
            prediction_confidence=0.8,
            stable_gesture="point",
            stable_confidence=0.8,
            compute_ms=0.7,
            emitted_state=state,
        )
    )
    status = metrics.build_status(
        session_id="demo",
        device_id="emg01",
        sample_rate_hz=1000,
    )
    assert status.windows_processed == 1
    assert status.states_emitted == 1
    assert status.last_gesture_id == "point"
    assert status.max_compute_ms == 0.7


def test_ensure_calibration_path_falls_back_beyond_hold_only(tmp_path) -> None:
    parquet_path = tmp_path / "demo__emg01.parquet"
    feature_path = build_feature_output_path(parquet_path)
    write_feature_vectors(
        feature_path,
        [
            WindowedFeatureVector(
                session_id="demo",
                gesture="rest",
                phase="rest",
                start_ts_us=0,
                end_ts_us=1,
                channel_features=(extract_hudgins_features([1.0, 1.0, 1.0, 1.0]),),
            ),
            WindowedFeatureVector(
                session_id="demo",
                gesture="fist",
                phase="hold",
                start_ts_us=2,
                end_ts_us=3,
                channel_features=(extract_hudgins_features([4.0, 4.0, 4.0, 4.0]),),
            ),
        ],
    )

    calibration_path = ensure_calibration_path(
        parquet_path,
        rest_gesture="rest",
        active_gesture="fist",
    )

    payload = json.loads(calibration_path.read_text(encoding="utf-8"))
    assert payload["session_id"] == "demo"
    assert len(payload["scale_rms"]) == 1


def test_synthetic_session_rows() -> None:
    rows = build_synthetic_rows(
        session_id="demo",
        device_id="sim01",
        gestures=["rest", "fist"],
        hold_frames=2,
        rest_frames=1,
    )
    assert len(rows) == 5
    assert rows[0]["cue_gesture"] == "rest"
    assert rows[2]["cue_gesture"] == "fist"
    assert rows[3]["cue_gesture"] == "fist"
    assert rows[4]["cue_gesture"] == "rest"


def test_guided_calibration_schedule_and_outputs(tmp_path) -> None:
    schedule = build_guided_calibration_schedule(
        ["fist", "open"],
        active_gesture="fist",
        lead_in_s=2.0,
        rest_baseline_s=10.0,
        max_squeeze_s=5.0,
        gesture_hold_s=3.0,
        gesture_rest_s=1.0,
        tail_rest_s=2.0,
    )
    assert schedule[0].phase == "lead_in"
    assert schedule[1].phase == "rest_baseline"
    assert schedule[2].phase == "max_squeeze"
    assert schedule_duration_s(schedule) == 27.0

    historical_parquet, _ = write_synthetic_session(
        output_dir=tmp_path,
        session_id="hist",
        device_id="sim01",
        gestures=["rest", "fist", "open"],
    )
    history_stream, history_rate = rows_to_sample_stream(load_rows(historical_parquet))
    history_vectors = window_feature_vectors(
        history_stream,
        sample_rate_hz=history_rate,
        session_id="hist",
        window_ms=200,
        hop_ms=50,
        highpass_hz=None,
        rectify_signal=False,
    )
    history_feature_path = build_feature_output_path(historical_parquet)
    write_feature_vectors(history_feature_path, history_vectors)

    calibration_parquet, _ = write_synthetic_session(
        output_dir=tmp_path,
        session_id="cal",
        device_id="sim01",
        gestures=["rest", "fist", "open"],
    )
    manifest = write_guided_calibration_outputs(
        calibration_parquet,
        active_gesture="fist",
        train_feature_paths=[history_feature_path],
        highpass_hz=None,
    )

    assert Path(manifest["feature_path"]).exists()
    assert Path(manifest["calibration_path"]).exists()
    assert Path(manifest["model_path"]).exists()
    assert manifest["feature_windows"] > 0
    assert manifest["hold_windows"] > 0
    assert manifest["hold_gesture_counts"]["fist"] > 0
    assert build_guided_manifest_output_path(calibration_parquet).exists()
    assert build_guided_model_output_path(calibration_parquet).name == "cal__sim01.session-lda-model.json"


def test_replay_evaluation_report(tmp_path) -> None:
    historical_parquet, _ = write_synthetic_session(
        output_dir=tmp_path,
        session_id="hist",
        device_id="sim01",
        gestures=["rest", "fist", "open"],
    )
    history_stream, history_rate = rows_to_sample_stream(load_rows(historical_parquet))
    history_vectors = window_feature_vectors(
        history_stream,
        sample_rate_hz=history_rate,
        session_id="hist",
        window_ms=200,
        hop_ms=50,
        highpass_hz=None,
        rectify_signal=False,
    )
    history_feature_path = build_feature_output_path(historical_parquet)
    write_feature_vectors(history_feature_path, history_vectors)

    evaluation_parquet, _ = write_synthetic_session(
        output_dir=tmp_path,
        session_id="eval",
        device_id="sim01",
        gestures=["rest", "fist", "open"],
    )
    manifest = write_guided_calibration_outputs(
        evaluation_parquet,
        active_gesture="fist",
        train_feature_paths=[history_feature_path],
        highpass_hz=None,
    )
    report = evaluate_replay_session(
        evaluation_parquet,
        session_id="eval-replay",
        model_path=Path(manifest["model_path"]),
        calibration_path=Path(manifest["calibration_path"]),
        vote_windows=1,
        min_hold_windows=1,
        confidence_threshold=0.0,
    )

    assert report["expected_windows"] > 0
    assert report["matched_windows"] > 0
    assert 0.0 <= report["accuracy"] <= 1.0
    assert build_replay_eval_output_path(evaluation_parquet).name == "eval__sim01.replay-eval.json"


def test_channel_ablation_report(tmp_path) -> None:
    hist_parquet, _ = write_synthetic_session(
        output_dir=tmp_path,
        session_id="hist",
        device_id="sim01",
        gestures=["rest", "fist", "open"],
    )
    eval_parquet, _ = write_synthetic_session(
        output_dir=tmp_path,
        session_id="eval",
        device_id="sim01",
        gestures=["rest", "fist", "open"],
    )
    feature_paths = []
    for session_id, parquet_path in (("hist", hist_parquet), ("eval", eval_parquet)):
        stream, sample_rate_hz = rows_to_sample_stream(load_rows(parquet_path))
        vectors = window_feature_vectors(
            stream,
            sample_rate_hz=sample_rate_hz,
            session_id=session_id,
            window_ms=200,
            hop_ms=50,
            highpass_hz=None,
            rectify_signal=False,
        )
        feature_path = build_feature_output_path(parquet_path)
        write_feature_vectors(feature_path, vectors)
        feature_paths.append(feature_path)

    report = run_channel_ablation(
        feature_paths,
        channel_counts=parse_channel_counts("1,2,4"),
    )
    assert report["available_channels"] == 2
    assert report["evaluated_channel_counts"] == [1, 2]
    assert "1" in report["results"]
    assert "2" in report["results"]
    assert build_ablation_output_path(feature_paths[0]).name == "channel-ablation.json"


def test_smoke_pipeline_summary(tmp_path) -> None:
    summary = run_smoke_pipeline(
        output_dir=tmp_path,
        device_id="sim01",
        gestures=["rest", "fist", "point", "pinch", "open"],
        channel_counts=[1, 2],
    )
    assert summary["selected_model_family"] in {"linear_svm", "random_forest", "lda"}
    assert Path(summary["selected_model_path"]).exists()
    assert summary["global_replay_eval"]["coverage"] == 1.0
    assert summary["global_replay_eval"]["accuracy"] >= 0.6
    assert summary["guided_replay_eval"]["coverage"] == 1.0
    assert summary["replay_selection"]["selected_mean_accuracy"] >= summary["global_replay_eval"]["accuracy"]
    assert build_smoke_summary_output_path(tmp_path).exists()


def test_model_selection_report_prefers_best_replay_family(tmp_path) -> None:
    hist_parquet, _ = write_synthetic_session(
        output_dir=tmp_path,
        session_id="hist",
        device_id="sim01",
        gestures=["rest", "fist", "point", "pinch", "open"],
    )
    eval_parquet, _ = write_synthetic_session(
        output_dir=tmp_path,
        session_id="eval",
        device_id="sim01",
        gestures=["rest", "fist", "point", "pinch", "open"],
    )
    feature_paths = []
    for session_id, parquet_path in (("hist", hist_parquet), ("eval", eval_parquet)):
        stream, sample_rate_hz = rows_to_sample_stream(load_rows(parquet_path))
        vectors = window_feature_vectors(
            stream,
            sample_rate_hz=sample_rate_hz,
            session_id=session_id,
            window_ms=200,
            hop_ms=50,
            highpass_hz=None,
            rectify_signal=False,
        )
        feature_path = build_feature_output_path(parquet_path)
        write_feature_vectors(feature_path, vectors)
        feature_paths.append(feature_path)

    report = evaluate_model_families(
        feature_paths,
        [eval_parquet],
        vote_windows=1,
        min_hold_windows=1,
        confidence_threshold=0.0,
    )
    best = select_best_model(report["results"])

    assert report["selected_family"] == best["family"]
    assert Path(report["selected_model_path"]).exists()
    assert report["selected_mean_accuracy"] == best["mean_accuracy"]
    assert build_selection_output_path(feature_paths[0]).name == "model-selection-report.json"


def test_model_comparison_report(tmp_path) -> None:
    hist_parquet, _ = write_synthetic_session(
        output_dir=tmp_path,
        session_id="hist",
        device_id="sim01",
        gestures=["rest", "fist", "open"],
    )
    eval_parquet, _ = write_synthetic_session(
        output_dir=tmp_path,
        session_id="eval",
        device_id="sim01",
        gestures=["rest", "fist", "open"],
    )
    feature_paths = []
    for session_id, parquet_path in (("hist", hist_parquet), ("eval", eval_parquet)):
        stream, sample_rate_hz = rows_to_sample_stream(load_rows(parquet_path))
        vectors = window_feature_vectors(
            stream,
            sample_rate_hz=sample_rate_hz,
            session_id=session_id,
            window_ms=200,
            hop_ms=50,
            highpass_hz=None,
            rectify_signal=False,
        )
        feature_path = build_feature_output_path(parquet_path)
        write_feature_vectors(feature_path, vectors)
        feature_paths.append(feature_path)

    report = compare_models(build_dataset(feature_paths))
    assert "lda" in report["models"]
    assert "linear_svm" in report["models"]
    assert "random_forest" in report["models"]
    assert build_compare_output_path(feature_paths[0]).name == "model-compare-report.json"
