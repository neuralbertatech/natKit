from __future__ import annotations

import asyncio
import argparse
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

from natvr.reconstruct_session import DiscoveredRun
import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "libnatkit"
    / "scripts"
    / "natkit_ml_control_plane.py"
)
SPEC = importlib.util.spec_from_file_location("natkit_ml_control_plane", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

build_pipeline_namespace = MODULE.build_pipeline_namespace
build_thread_slot_id = MODULE.build_thread_slot_id
compute_busy_ratio = MODULE.compute_busy_ratio
ThreadSlotState = MODULE.ThreadSlotState
JobRecord = MODULE.JobRecord
MlControlPlaneServer = MODULE.MlControlPlaneServer
namespace_from_config = MODULE.namespace_from_config
PipelineCancelledError = MODULE.PipelineCancelledError
normalize_principal_id = MODULE.normalize_principal_id
resolve_worker_thread_count = MODULE.resolve_worker_thread_count
run_to_dict = MODULE.run_to_dict
sanitize_pipeline_report = MODULE.sanitize_pipeline_report
persist_scheduler_state_db = MODULE.persist_scheduler_state_db
load_scheduler_state_db_revision = MODULE.load_scheduler_state_db_revision
scheduler_state_revision = MODULE.scheduler_state_revision
slot_to_dict = MODULE.slot_to_dict
worker_to_dict = MODULE.worker_to_dict
worker_status_from_heartbeat = MODULE.worker_status_from_heartbeat
worker_is_past_auto_recover_deadline = MODULE.worker_is_past_auto_recover_deadline
recovered_worker_status_from_job_error = MODULE.recovered_worker_status_from_job_error


def build_run() -> DiscoveredRun:
    return DiscoveredRun(
        session_id="demo",
        run_index=2,
        start_us=1000,
        end_us=2000,
        device_ids=("emg01",),
        purpose="training",
        participant_id="subject-a",
        protocol_id="proto",
        tags=("right", "completed"),
        notes="demo notes",
        marker_count=66,
        last_activity_us=2000,
    )


def build_base_args() -> argparse.Namespace:
    return argparse.Namespace(
        host="127.0.0.1",
        port=8786,
        broker="127.0.0.1:29092",
        group_id="natkit-ml-control-plane",
        scratch_root=None,
        idle_timeout_s=2.0,
        no_direct_assign=False,
        partition=0,
        metadata_json=None,
        allow_missing_session_end=False,
        post_roll_us=1_000_000,
        rest_gesture="rest",
        active_gesture="fist",
        window_ms=200,
        hop_ms=50,
        vote_windows=5,
        confidence_threshold=0.6,
        min_hold_windows=2,
        emit_only_during_cue_hold=False,
        selected_fields=[],
        worker_id="worker-test",
        worker_threads=4,
        max_worker_restart_attempts=1,
        state_json=None,
        state_db=None,
        default_principal_id="default",
        log_level="INFO",
    )


def test_namespace_from_config_sets_direct_assign() -> None:
    args = namespace_from_config(build_base_args(), {"no_direct_assign": True})

    assert args.no_direct_assign is True
    assert args.direct_assign is False


def test_run_to_dict_serializes_expected_fields() -> None:
    payload = run_to_dict(build_run())

    assert payload["session_id"] == "demo"
    assert payload["run_index"] == 2
    assert payload["device_ids"] == ["emg01"]
    assert payload["tags"] == ["right", "completed"]


def test_normalize_principal_id_trims_and_drops_empty_values() -> None:
    assert normalize_principal_id("  user-a  ") == "user-a"
    assert normalize_principal_id("   ") is None
    assert normalize_principal_id(None) is None


def test_build_pipeline_namespace_maps_run_selectors() -> None:
    args = build_pipeline_namespace(
        build_base_args(),
        {
            "broker": "kafka:29092",
            "families": ["lda", "linear_svm"],
            "train_runs": [
                {"session_id": "demo", "run_index": 1},
                {"session_id": "demo", "run_index": 2},
            ],
            "eval_runs": [{"session_id": "eval", "run_index": 3}],
            "selected_fields": ["channels.0.samples", "channels.2.samples"],
            "window_ms": 250,
            "emit_only_during_cue_hold": True,
        },
        output_dir="scratch/job-123",
    )

    assert args.broker == "kafka:29092"
    assert args.output_dir == "scratch/job-123"
    assert args.families == ["lda", "linear_svm"]
    assert args.train_runs == ["demo:1", "demo:2"]
    assert args.eval_runs == ["eval:3"]
    assert args.selected_fields == ["channels.0.samples", "channels.2.samples"]
    assert args.window_ms == 250
    assert args.emit_only_during_cue_hold is True


def test_sanitize_pipeline_report_removes_filesystem_paths() -> None:
    report = sanitize_pipeline_report(
        {
            "broker": "kafka:29092",
            "output_dir": "/tmp/natkit-ml-abc",
            "selected_fields": ["channels.0.samples", "channels.1.samples"],
            "selected_channel_indexes": [0, 1],
            "train_runs": [
                {
                    "session_id": "demo",
                    "run_index": 1,
                    "device_id": "emg01",
                    "parquet_path": "/tmp/demo.parquet",
                    "marker_path": "/tmp/demo.markers.jsonl",
                    "feature_path": "/tmp/demo.features.jsonl",
                }
            ],
            "eval_runs": [
                {
                    "session_id": "eval",
                    "run_index": 2,
                    "device_id": "emg01",
                    "parquet_path": "/tmp/eval.parquet",
                }
            ],
            "results": [
                {
                    "family": "lda",
                    "model_path": "/tmp/lda.json",
                    "train_feature_paths": ["/tmp/demo.features.jsonl"],
                    "replay_reports": [
                        {
                            "session_id": "lda-demo",
                            "parquet_path": "/tmp/eval.parquet",
                            "model_path": "/tmp/lda.json",
                            "calibration_path": "/tmp/eval.calibration.json",
                            "accuracy": 0.9,
                            "coverage": 0.8,
                            "expected_windows": 10,
                            "predicted_windows": 8,
                            "matched_windows": 8,
                            "missing_windows": 2,
                            "unmatched_predictions": 0,
                            "confusion_matrix": {"rest": {"rest": 4}},
                        }
                    ],
                    "mean_accuracy": 0.9,
                    "min_accuracy": 0.9,
                    "mean_coverage": 0.8,
                }
            ],
            "selected_family": "lda",
            "selected_model_path": "/tmp/lda.json",
            "selected_mean_accuracy": 0.9,
            "selected_min_accuracy": 0.9,
            "selected_mean_coverage": 0.8,
        }
    )

    assert report["artifact_storage"] == "ephemeral_scratch"
    assert report["selected_fields"] == ["channels.0.samples", "channels.1.samples"]
    assert report["selected_channel_indexes"] == [0, 1]
    assert report["train_runs"] == [
        {"session_id": "demo", "run_index": 1, "device_id": "emg01"}
    ]
    assert report["results"][0]["replay_reports"][0]["session_id"] == "lda-demo"
    assert "selected_model_path" not in report


def test_resolve_worker_thread_count_prefers_explicit_value() -> None:
    assert resolve_worker_thread_count(8) == 8


def test_resolve_worker_thread_count_allows_explicit_zero() -> None:
    assert resolve_worker_thread_count(0) == 0


def test_build_thread_slot_id_formats_stable_identifier() -> None:
    assert build_thread_slot_id("worker-a", 2) == "worker-a:slot-03"


def test_compute_busy_ratio_uses_window_overlap() -> None:
    ratio = compute_busy_ratio([(100.0, 130.0), (150.0, None)], now=160.0, window_s=80.0)

    assert ratio == 0.5


def test_slot_to_dict_counts_assigned_and_queued_jobs() -> None:
    slot = ThreadSlotState(
        slot_id="worker-a:slot-01",
        worker_id="worker-a",
        slot_index=0,
        owner_principal_id="default",
    )
    slot.current_job_id = "job-running"
    slot.busy_intervals.append((10.0, 40.0))
    jobs = {
        "job-running": JobRecord(
            job_id="job-running",
            thread_slot_id=slot.slot_id,
            owner_principal_id="default",
            status="running",
            restart_count=1,
        ),
        "job-queued": JobRecord(
            job_id="job-queued",
            thread_slot_id=slot.slot_id,
            owner_principal_id="default",
            status="queued",
            restart_count=2,
        ),
        "job-done": JobRecord(
            job_id="job-done",
            thread_slot_id=slot.slot_id,
            owner_principal_id="default",
            status="completed",
            restart_count=3,
        ),
    }

    payload = slot_to_dict(slot, jobs, now_monotonic=70.0)

    assert payload["assigned_job_count"] == 2
    assert payload["queue_depth"] == 1
    assert payload["running_job_count"] == 1
    assert payload["current_job_id"] == "job-running"
    assert payload["restart_attempt_count"] == 6


def test_worker_to_dict_aggregates_visible_slot_capacity() -> None:
    slots = [
        ThreadSlotState(
            slot_id="worker-a:slot-01",
            worker_id="worker-a",
            slot_index=0,
            owner_principal_id="user-a",
        ),
        ThreadSlotState(
            slot_id="worker-a:slot-02",
            worker_id="worker-a",
            slot_index=1,
            owner_principal_id="user-b",
        ),
    ]
    slots[0].busy_intervals.append((20.0, 50.0))
    jobs = {
        "job-a": JobRecord(
            job_id="job-a",
            thread_slot_id="worker-a:slot-01",
            owner_principal_id="user-a",
            status="running",
            restart_count=1,
        ),
        "job-b": JobRecord(
            job_id="job-b",
            thread_slot_id="worker-a:slot-01",
            owner_principal_id="user-a",
            status="queued",
            restart_count=2,
        ),
        "job-c": JobRecord(
            job_id="job-c",
            thread_slot_id="worker-a:slot-02",
            owner_principal_id="user-b",
            status="queued",
            restart_count=9,
        ),
    }

    payload = worker_to_dict(
        "worker-a",
        slots,
        jobs,
        last_heartbeat_us=123,
        principal_id="user-a",
        now_monotonic=80.0,
    )

    assert payload["worker_id"] == "worker-a"
    assert payload["slot_count"] == 2
    assert payload["visible_slot_count"] == 1
    assert payload["assigned_slot_count"] == 2
    assert payload["queued_job_count"] == 1
    assert payload["running_job_count"] == 1
    assert payload["assigned_job_count"] == 2
    assert payload["restart_attempt_count"] == 3
    assert payload["busy_ratio_60s"] == 0.5
    assert payload["last_heartbeat_us"] == 123


def test_worker_to_dict_marks_stalled_worker_degraded_after_recoveries() -> None:
    jobs = {
        "job-recovered": JobRecord(
            job_id="job-recovered",
            worker_id="worker-a",
            thread_slot_id="worker-a:slot-01",
            owner_principal_id="user-a",
            status="failed",
            error="worker worker-a became stalled",
        )
    }

    payload = worker_to_dict(
        "worker-a",
        [],
        jobs,
        last_heartbeat_us=1,
        now_wall_us=60_000_000,
        embedded_worker_id="worker-test",
        worker_status="online",
    )

    assert payload["worker_status"] == "degraded"
    assert payload["recovered_job_count"] == 1


def test_worker_to_dict_reports_drain_readiness_from_full_worker_activity() -> None:
    slots = [
        ThreadSlotState(
            slot_id="worker-a:slot-01",
            worker_id="worker-a",
            slot_index=0,
            owner_principal_id="user-a",
        ),
        ThreadSlotState(
            slot_id="worker-a:slot-02",
            worker_id="worker-a",
            slot_index=1,
            owner_principal_id="user-b",
        ),
    ]
    jobs = {
        "job-hidden-running": JobRecord(
            job_id="job-hidden-running",
            worker_id="worker-a",
            thread_slot_id="worker-a:slot-02",
            owner_principal_id="user-b",
            status="running",
        )
    }

    payload = worker_to_dict(
        "worker-a",
        slots,
        jobs,
        last_heartbeat_us=123,
        principal_id="user-a",
        worker_status="draining",
        embedded_worker_id="worker-test",
    )

    assert payload["visible_slot_count"] == 1
    assert payload["assigned_job_count"] == 0
    assert payload["drain_remaining_job_count"] == 1
    assert payload["drain_ready"] is False
    assert payload["accepting_new_jobs"] is False


def test_worker_to_dict_marks_draining_worker_ready_when_no_active_jobs_remain() -> None:
    payload = worker_to_dict(
        "worker-a",
        [],
        {},
        last_heartbeat_us=123,
        worker_status="draining",
        embedded_worker_id="worker-test",
    )

    assert payload["worker_status"] == "draining"
    assert payload["drain_remaining_job_count"] == 0
    assert payload["drain_ready"] is True
    assert payload["accepting_new_jobs"] is False


def test_recovered_worker_status_from_job_error_accepts_all_recoverable_statuses() -> None:
    assert (
        recovered_worker_status_from_job_error(
            "worker-a",
            "worker worker-a became stalled",
        )
        == "stalled"
    )
    assert (
        recovered_worker_status_from_job_error(
            "worker-a",
            "worker worker-a became offline",
        )
        == "offline"
    )
    assert (
        recovered_worker_status_from_job_error(
            "worker-a",
            "worker worker-a became missing",
        )
        == "missing"
    )
    assert (
        recovered_worker_status_from_job_error(
            "worker-a",
            "worker worker-a became online",
        )
        is None
    )
    assert recovered_worker_status_from_job_error("worker-a", "other error") is None


def test_worker_to_dict_counts_offline_recoveries_in_degraded_summary() -> None:
    jobs = {
        "job-recovered": JobRecord(
            job_id="job-recovered",
            worker_id="worker-a",
            thread_slot_id="worker-a:slot-01",
            owner_principal_id="user-a",
            status="failed",
            error="worker worker-a became offline",
        )
    }

    payload = worker_to_dict(
        "worker-a",
        [],
        jobs,
        last_heartbeat_us=1,
        now_wall_us=60_000_000,
        embedded_worker_id="worker-test",
        worker_status="offline",
    )

    assert payload["worker_status"] == "degraded"
    assert payload["recovered_job_count"] == 1


def test_worker_status_from_heartbeat_marks_stale_external_workers() -> None:
    status = worker_status_from_heartbeat(
        worker_id="worker-remote",
        embedded_worker_id="worker-test",
        last_heartbeat_us=1_000_000,
        status="online",
        now_wall_us=17_000_000,
    )

    assert status == "stalled"


def test_worker_status_from_heartbeat_preserves_draining_status() -> None:
    status = worker_status_from_heartbeat(
        worker_id="worker-remote",
        embedded_worker_id="worker-test",
        last_heartbeat_us=1_000_000,
        status="draining",
        now_wall_us=17_000_000,
    )

    assert status == "draining"


def test_worker_to_dict_keeps_embedded_worker_status_without_stale_override() -> None:
    payload = worker_to_dict(
        "worker-test",
        [],
        {},
        last_heartbeat_us=1_000_000,
        now_wall_us=30_000_000,
        embedded_worker_id="worker-test",
        worker_status="online",
    )

    assert payload["worker_status"] == "online"


def test_merge_worker_status_preserves_explicit_draining_over_online_heartbeats() -> None:
    assert MODULE.merge_worker_status("draining", "online") == "draining"
    assert MODULE.merge_worker_status("draining", "starting") == "draining"
    assert MODULE.merge_worker_status("draining", "offline") == "offline"
    assert MODULE.merge_worker_status("online", "online") == "online"


def test_worker_is_past_auto_recover_deadline_uses_longer_timeout() -> None:
    assert (
        worker_is_past_auto_recover_deadline(
            worker_id="worker-remote",
            embedded_worker_id="worker-test",
            last_heartbeat_us=1_000_000,
            now_wall_us=50_000_000,
        )
        is True
    )
    assert (
        worker_is_past_auto_recover_deadline(
            worker_id="worker-remote",
            embedded_worker_id="worker-test",
            last_heartbeat_us=30_000_000,
            now_wall_us=50_000_000,
        )
        is False
    )


class FakeWebSocket:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def send(self, raw: str) -> None:
        import json

        self.messages.append(json.loads(raw))


@pytest.mark.anyio
async def test_send_workers_marks_stale_external_worker_in_summary() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=2,
        last_heartbeat_us=1,
        source="external",
        status="online",
    )

    await server._send_workers(
        websocket,
        request_id="req-workers-stale",
        principal_id=None,
    )

    message = websocket.messages[-1]
    remote = next(worker for worker in message["workers"] if worker["worker_id"] == "worker-remote")
    assert remote["worker_status"] == "stalled"


@pytest.mark.anyio
async def test_send_workers_marks_worker_degraded_after_stalled_recovery() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=1,
        source="external",
        status="online",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )
    server._jobs["job-recovered"] = JobRecord(
        job_id="job-recovered",
        owner_principal_id="user-a",
        worker_id="worker-remote",
        thread_slot_id=remote_slot_id,
        priority=1,
        status="failed",
        error="worker worker-remote became stalled",
        message="Automatically recovered after worker worker-remote remained stalled; the lost run must be resubmitted",
    )

    await server._send_workers(
        websocket,
        request_id="req-workers-degraded",
        principal_id=None,
    )

    message = websocket.messages[-1]
    remote = next(worker for worker in message["workers"] if worker["worker_id"] == "worker-remote")
    assert remote["worker_status"] == "degraded"
    assert remote["recovered_job_count"] == 1


@pytest.mark.anyio
async def test_send_workers_reports_draining_worker_ready_state() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=123,
        source="external",
        status="draining",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )

    await server._send_workers(
        websocket,
        request_id="req-workers-drain-ready",
        principal_id=None,
    )

    message = websocket.messages[-1]
    remote = next(worker for worker in message["workers"] if worker["worker_id"] == "worker-remote")
    assert remote["worker_status"] == "draining"
    assert remote["drain_ready"] is True
    assert remote["drain_remaining_job_count"] == 0


@pytest.mark.anyio
async def test_send_workers_marks_worker_degraded_after_offline_recovery() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=MODULE.now_us(),
        source="external",
        status="offline",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )
    server._jobs["job-recovered"] = JobRecord(
        job_id="job-recovered",
        owner_principal_id="user-a",
        worker_id="worker-remote",
        thread_slot_id=remote_slot_id,
        priority=1,
        status="failed",
        error="worker worker-remote became offline",
        message="Recovered after worker worker-remote became offline; the lost run must be resubmitted",
    )

    await server._send_workers(
        websocket,
        request_id="req-workers-degraded-offline",
        principal_id=None,
    )

    message = websocket.messages[-1]
    remote = next(worker for worker in message["workers"] if worker["worker_id"] == "worker-remote")
    assert remote["worker_status"] == "degraded"
    assert remote["recovered_job_count"] == 1


@pytest.mark.anyio
async def test_get_job_status_allows_worker_to_inspect_its_own_remote_job() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=MODULE.now_us(),
        source="external",
        status="online",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )
    server._jobs["job-remote-running"] = JobRecord(
        job_id="job-remote-running",
        owner_principal_id="user-a",
        worker_id="worker-remote",
        thread_slot_id=remote_slot_id,
        priority=2,
        status="cancelling",
        stop_requested=True,
        message="stop requested remotely",
    )

    await server._handle_get_job_status(
        websocket,
        {"worker_id": "worker-remote", "job_id": "job-remote-running"},
        request_id="req-worker-status",
    )

    message = websocket.messages[-1]
    assert message["type"] == "job_status"
    assert message["job_id"] == "job-remote-running"
    assert message["status"] == "cancelling"


@pytest.mark.anyio
async def test_get_job_status_returns_synthetic_failure_for_missing_worker_job() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()

    await server._handle_get_job_status(
        websocket,
        {"worker_id": "worker-remote", "job_id": "job-missing"},
        request_id="req-worker-status-missing",
    )

    message = websocket.messages[-1]
    assert message["type"] == "job_status"
    assert message["job_id"] == "job-missing"
    assert message["worker_id"] == "worker-remote"
    assert message["status"] == "failed"
    assert message["error"] == "job state missing after reconnect"


@pytest.mark.anyio
async def test_assign_thread_slots_updates_owner() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    slot_id = next(iter(server._slots.keys()))

    await server._handle_assign_thread_slots(
        websocket,
        {"principal_id": "user-a", "slot_ids": [slot_id]},
        request_id="req-1",
    )

    assert server._slots[slot_id].owner_principal_id == "user-a"
    assert websocket.messages[-1]["type"] == "thread_slots"


@pytest.mark.anyio
async def test_assign_thread_slots_allows_claim_from_default_owner() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    slot_id = next(iter(server._slots.keys()))

    await server._handle_assign_thread_slots(
        websocket,
        {"principal_id": "user-b", "slot_ids": [slot_id]},
        request_id="req-claim",
    )

    assert server._slots[slot_id].owner_principal_id == "user-b"
    assert websocket.messages[-1]["type"] == "thread_slots"


@pytest.mark.anyio
async def test_assign_thread_slots_rejects_foreign_idle_owner_without_release() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    slot_id = next(iter(server._slots.keys()))
    server._slots[slot_id].owner_principal_id = "owner-a"

    await server._handle_assign_thread_slots(
        websocket,
        {"principal_id": "owner-b", "slot_ids": [slot_id]},
        request_id="req-claim",
    )

    assert server._slots[slot_id].owner_principal_id == "owner-a"
    assert websocket.messages[-1]["type"] == "error"
    assert "must be released before reassignment" in str(websocket.messages[-1]["message"])


@pytest.mark.anyio
async def test_release_thread_slots_clears_owner() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    slot_id = next(iter(server._slots.keys()))
    server._slots[slot_id].owner_principal_id = "user-a"

    await server._handle_release_thread_slots(
        websocket,
        {"principal_id": "user-a", "slot_ids": [slot_id]},
        request_id="req-release",
    )

    assert server._slots[slot_id].owner_principal_id is None
    assert websocket.messages[-1]["type"] == "thread_slots"


@pytest.mark.anyio
async def test_release_thread_slots_rejects_active_jobs() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    slot = next(iter(server._slots.values()))
    slot.owner_principal_id = "user-a"
    server._jobs["job-1"] = JobRecord(
        job_id="job-1",
        owner_principal_id="user-a",
        worker_id=slot.worker_id,
        thread_slot_id=slot.slot_id,
        priority=1,
        status="queued",
    )

    await server._handle_release_thread_slots(
        websocket,
        {"principal_id": "user-a", "slot_ids": [slot.slot_id]},
        request_id="req-release",
    )

    assert server._slots[slot.slot_id].owner_principal_id == "user-a"
    assert websocket.messages[-1]["type"] == "error"
    assert "has active jobs" in str(websocket.messages[-1]["message"])


@pytest.mark.anyio
async def test_assign_thread_slots_rejects_reassign_with_active_foreign_jobs() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    slot = next(iter(server._slots.values()))
    slot.owner_principal_id = "owner-a"
    server._jobs["job-1"] = JobRecord(
        job_id="job-1",
        owner_principal_id="owner-a",
        worker_id=slot.worker_id,
        thread_slot_id=slot.slot_id,
        priority=1,
        status="queued",
    )

    await server._handle_assign_thread_slots(
        websocket,
        {"principal_id": "owner-b", "slot_ids": [slot.slot_id]},
        request_id="req-assign",
    )

    assert server._slots[slot.slot_id].owner_principal_id == "owner-a"
    assert websocket.messages[-1]["type"] == "error"
    assert "cannot be reassigned" in str(websocket.messages[-1]["message"])


@pytest.mark.anyio
async def test_send_workers_returns_aggregated_summary() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    slot = next(iter(server._slots.values()))
    server._jobs["job-1"] = JobRecord(
        job_id="job-1",
        owner_principal_id="default",
        worker_id=slot.worker_id,
        thread_slot_id=slot.slot_id,
        priority=2,
        status="queued",
    )

    await server._send_workers(
        websocket,
        request_id="req-workers",
        principal_id="default",
    )

    message = websocket.messages[-1]
    assert message["type"] == "workers"
    assert message["request_id"] == "req-workers"
    assert message["principal_id"] == "default"
    assert len(message["workers"]) == 1
    assert message["workers"][0]["worker_id"] == "worker-test"
    assert message["workers"][0]["queued_job_count"] == 1


@pytest.mark.anyio
async def test_register_worker_adds_external_worker_summary() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()

    await server._handle_register_worker(
        websocket,
        {"worker_id": "worker-remote", "slot_count": 6, "status": "online"},
        request_id="req-register",
    )

    message = websocket.messages[-1]
    assert message["type"] == "workers"
    worker_ids = [worker["worker_id"] for worker in message["workers"]]
    assert worker_ids == ["worker-remote", "worker-test"]
    remote = next(worker for worker in message["workers"] if worker["worker_id"] == "worker-remote")
    assert remote["slot_count"] == 6
    assert remote["worker_source"] == "external"
    assert remote["slot_inventory_ready"] is False


@pytest.mark.anyio
async def test_register_worker_requeues_running_jobs_after_worker_process_restart() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=1,
        source="external",
        status="online",
        session_id="session-old",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )
    server._slots[remote_slot_id].current_job_id = "job-remote-running"
    server._slots[remote_slot_id].busy_intervals.append((10.0, None))
    server._jobs["job-remote-running"] = JobRecord(
        job_id="job-remote-running",
        owner_principal_id="user-a",
        worker_id="worker-remote",
        thread_slot_id=remote_slot_id,
        priority=3,
        status="running",
        message="running remotely",
        created_at_us=100,
        started_at_us=120,
        sequence=1,
        queue_token=0,
    )
    server._job_requests["job-remote-running"] = {
        "families": ["lda"],
        "train_runs": [{"session_id": "demo", "run_index": 1}],
        "eval_runs": [{"session_id": "demo", "run_index": 2}],
    }

    await server._handle_register_worker(
        websocket,
        {
            "worker_id": "worker-remote",
            "slot_count": 1,
            "status": "online",
            "worker_session_id": "session-new",
        },
        request_id="req-register-restart",
    )

    job = server._jobs["job-remote-running"]
    assert job.status == "queued"
    assert job.message == "Requeued after worker process restart"
    assert job.started_at_us is None
    assert job.restart_count == 1
    assert server._slots[remote_slot_id].current_job_id is None

    await server._handle_claim_worker_slot_job(
        websocket,
        {
            "worker_id": "worker-remote",
            "slot_id": remote_slot_id,
            "worker_session_id": "session-new",
        },
        request_id="req-claim-restarted",
    )

    claim_message = websocket.messages[-1]
    assert claim_message["type"] == "worker_job_claim"
    assert claim_message["job"]["job_id"] == "job-remote-running"
    assert server._jobs["job-remote-running"].status == "running"


@pytest.mark.anyio
async def test_register_worker_same_session_keeps_running_job_intact() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=1,
        source="external",
        status="online",
        session_id="session-stable",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )
    server._slots[remote_slot_id].current_job_id = "job-remote-running"
    server._slots[remote_slot_id].busy_intervals.append((10.0, None))
    server._jobs["job-remote-running"] = JobRecord(
        job_id="job-remote-running",
        owner_principal_id="user-a",
        worker_id="worker-remote",
        thread_slot_id=remote_slot_id,
        priority=3,
        status="running",
        message="running remotely",
        created_at_us=100,
        started_at_us=120,
        sequence=1,
        queue_token=0,
    )
    server._job_requests["job-remote-running"] = {
        "families": ["lda"],
        "train_runs": [{"session_id": "demo", "run_index": 1}],
        "eval_runs": [{"session_id": "demo", "run_index": 2}],
    }

    await server._handle_register_worker(
        websocket,
        {
            "worker_id": "worker-remote",
            "slot_count": 1,
            "status": "online",
            "worker_session_id": "session-stable",
        },
        request_id="req-register-same-session",
    )

    assert server._jobs["job-remote-running"].status == "running"
    assert server._slots[remote_slot_id].current_job_id == "job-remote-running"


@pytest.mark.anyio
async def test_register_worker_fails_job_when_restart_limit_is_exhausted() -> None:
    args = build_base_args()
    args.max_worker_restart_attempts = 1
    server = MlControlPlaneServer(args)
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=1,
        source="external",
        status="online",
        session_id="session-old",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )
    server._slots[remote_slot_id].current_job_id = "job-remote-running"
    server._slots[remote_slot_id].busy_intervals.append((10.0, None))
    server._jobs["job-remote-running"] = JobRecord(
        job_id="job-remote-running",
        owner_principal_id="user-a",
        worker_id="worker-remote",
        thread_slot_id=remote_slot_id,
        priority=3,
        status="running",
        message="running remotely",
        created_at_us=100,
        started_at_us=120,
        sequence=1,
        queue_token=1,
        restart_count=1,
    )
    server._job_requests["job-remote-running"] = {
        "families": ["lda"],
        "train_runs": [{"session_id": "demo", "run_index": 1}],
        "eval_runs": [{"session_id": "demo", "run_index": 2}],
    }

    await server._handle_register_worker(
        websocket,
        {
            "worker_id": "worker-remote",
            "slot_count": 1,
            "status": "online",
            "worker_session_id": "session-new",
        },
        request_id="req-register-limit-hit",
    )

    job = server._jobs["job-remote-running"]
    assert job.status == "failed"
    assert "automatic rerun limit was exhausted" in job.message
    assert job.error == "worker process restart rerun limit exhausted"
    assert job.restart_count == 1
    assert server._slots[remote_slot_id].current_job_id is None
    assert "job-remote-running" not in server._job_requests


@pytest.mark.anyio
async def test_zero_embedded_threads_keeps_control_plane_visible_without_local_slots() -> None:
    args = build_base_args()
    args.worker_threads = 0
    server = MlControlPlaneServer(args)

    assert server._slot_count == 0
    assert server._slots == {}
    assert server._workers["worker-test"].slot_count == 0

    await server.start()

    assert server._slot_workers == []
    assert server._heartbeat_task is not None

    server._heartbeat_task.cancel()
    await asyncio.gather(server._heartbeat_task, return_exceptions=True)


@pytest.mark.anyio
async def test_worker_heartbeat_updates_external_worker_summary() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=2,
        last_heartbeat_us=1,
        source="external",
        status="starting",
    )

    await server._handle_worker_heartbeat(
        websocket,
        {"worker_id": "worker-remote", "slot_count": 5, "status": "online"},
        request_id="req-heartbeat",
    )

    message = websocket.messages[-1]
    remote = next(worker for worker in message["workers"] if worker["worker_id"] == "worker-remote")
    assert remote["slot_count"] == 5
    assert remote["worker_status"] == "online"
    assert remote["last_heartbeat_us"] > 1


@pytest.mark.anyio
async def test_worker_heartbeat_rejects_stale_worker_session() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=2,
        last_heartbeat_us=1,
        source="external",
        status="online",
        session_id="session-live",
    )

    await server._handle_worker_heartbeat(
        websocket,
        {
            "worker_id": "worker-remote",
            "slot_count": 5,
            "status": "online",
            "worker_session_id": "session-stale",
        },
        request_id="req-heartbeat-stale-session",
    )

    assert websocket.messages[-1]["type"] == "error"
    assert "session mismatch" in str(websocket.messages[-1]["message"])
    assert server._workers["worker-remote"].slot_count == 2
    assert server._workers["worker-remote"].session_id == "session-live"


@pytest.mark.anyio
async def test_worker_heartbeat_reports_draining_status_without_stale_override() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=2,
        last_heartbeat_us=1,
        source="external",
        status="online",
    )

    await server._handle_worker_heartbeat(
        websocket,
        {"worker_id": "worker-remote", "slot_count": 2, "status": "draining"},
        request_id="req-heartbeat-draining",
    )

    message = websocket.messages[-1]
    remote = next(worker for worker in message["workers"] if worker["worker_id"] == "worker-remote")
    assert remote["worker_status"] == "draining"
    assert server._workers["worker-remote"].status == "draining"


@pytest.mark.anyio
async def test_sync_worker_slots_adds_external_slot_inventory() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=2,
        last_heartbeat_us=1,
        source="external",
        status="online",
    )

    await server._handle_sync_worker_slots(
        websocket,
        {"worker_id": "worker-remote", "slot_count": 2},
        request_id="req-sync",
    )

    assert build_thread_slot_id("worker-remote", 0) in server._slots
    assert build_thread_slot_id("worker-remote", 1) in server._slots
    assert websocket.messages[-1]["type"] == "thread_slots"


@pytest.mark.anyio
async def test_sync_worker_slots_rejects_stale_worker_session() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=2,
        last_heartbeat_us=1,
        source="external",
        status="online",
        session_id="session-live",
    )

    await server._handle_sync_worker_slots(
        websocket,
        {
            "worker_id": "worker-remote",
            "slot_count": 2,
            "worker_session_id": "session-stale",
        },
        request_id="req-sync-stale-session",
    )

    assert websocket.messages[-1]["type"] == "error"
    assert "session mismatch" in str(websocket.messages[-1]["message"])
    assert build_thread_slot_id("worker-remote", 0) not in server._slots


@pytest.mark.anyio
async def test_sync_worker_slots_rejects_shrink_with_assigned_slot() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 1)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=2,
        last_heartbeat_us=1,
        source="external",
        status="online",
    )
    server._slots[build_thread_slot_id("worker-remote", 0)] = ThreadSlotState(
        slot_id=build_thread_slot_id("worker-remote", 0),
        worker_id="worker-remote",
        slot_index=0,
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=1,
        owner_principal_id="user-a",
    )

    await server._handle_sync_worker_slots(
        websocket,
        {"worker_id": "worker-remote", "slot_count": 1},
        request_id="req-sync",
    )

    assert remote_slot_id in server._slots
    assert websocket.messages[-1]["type"] == "error"
    assert "cannot shrink inventory" in str(websocket.messages[-1]["message"])


@pytest.mark.anyio
async def test_unregister_worker_removes_external_worker_summary() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=2,
        last_heartbeat_us=1,
        source="external",
        status="online",
    )

    await server._handle_unregister_worker(
        websocket,
        {"worker_id": "worker-remote"},
        request_id="req-unregister",
    )

    message = websocket.messages[-1]
    worker_ids = [worker["worker_id"] for worker in message["workers"]]
    assert worker_ids == ["worker-test"]


@pytest.mark.anyio
async def test_stop_job_rejects_non_owner() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    slot = next(iter(server._slots.values()))
    server._jobs["job-1"] = JobRecord(
        job_id="job-1",
        owner_principal_id="owner-a",
        worker_id=slot.worker_id,
        thread_slot_id=slot.slot_id,
        priority=2,
        status="queued",
    )

    await server._handle_stop_job(
        websocket,
        {"job_id": "job-1", "principal_id": "owner-b"},
        request_id="req-stop",
    )

    assert server._jobs["job-1"].status == "queued"
    assert websocket.messages[-1]["type"] == "error"
    assert "cannot stop job job-1" in str(websocket.messages[-1]["message"])


@pytest.mark.anyio
async def test_recover_job_marks_stalled_remote_run_failed_and_clears_slot() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=1,
        source="external",
        status="online",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )
    server._slots[remote_slot_id].current_job_id = "job-remote-running"
    server._slots[remote_slot_id].busy_intervals.append((10.0, None))
    server._jobs["job-remote-running"] = JobRecord(
        job_id="job-remote-running",
        owner_principal_id="user-a",
        worker_id="worker-remote",
        thread_slot_id=remote_slot_id,
        priority=2,
        status="running",
        message="running remotely",
    )
    server._job_requests["job-remote-running"] = {
        "families": ["lda"],
        "train_runs": [{"session_id": "demo", "run_index": 1}],
        "eval_runs": [{"session_id": "demo", "run_index": 2}],
    }

    await server._handle_recover_job(
        websocket,
        {"job_id": "job-remote-running", "principal_id": "user-a"},
        request_id="req-recover",
    )

    message = websocket.messages[-1]
    assert message["type"] == "job_status"
    assert message["status"] == "failed"
    assert server._slots[remote_slot_id].current_job_id is None
    assert server._jobs["job-remote-running"].error == "worker worker-remote became stalled"
    assert "job-remote-running" not in server._job_requests


@pytest.mark.anyio
async def test_recover_job_rejects_online_remote_run() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=MODULE.now_us(),
        source="external",
        status="online",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )
    server._slots[remote_slot_id].current_job_id = "job-remote-running"
    server._jobs["job-remote-running"] = JobRecord(
        job_id="job-remote-running",
        owner_principal_id="user-a",
        worker_id="worker-remote",
        thread_slot_id=remote_slot_id,
        priority=2,
        status="running",
        message="running remotely",
    )

    await server._handle_recover_job(
        websocket,
        {"job_id": "job-remote-running", "principal_id": "user-a"},
        request_id="req-recover-online",
    )

    assert websocket.messages[-1]["type"] == "error"
    assert "cannot be recovered yet" in str(websocket.messages[-1]["message"])
    assert server._jobs["job-remote-running"].status == "running"


@pytest.mark.anyio
async def test_recover_worker_marks_all_stalled_remote_runs_failed() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_a = build_thread_slot_id("worker-remote", 0)
    remote_slot_b = build_thread_slot_id("worker-remote", 1)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=2,
        last_heartbeat_us=1,
        source="external",
        status="online",
    )
    server._slots[remote_slot_a] = ThreadSlotState(
        slot_id=remote_slot_a,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )
    server._slots[remote_slot_b] = ThreadSlotState(
        slot_id=remote_slot_b,
        worker_id="worker-remote",
        slot_index=1,
        owner_principal_id="user-a",
    )
    server._slots[remote_slot_a].current_job_id = "job-remote-a"
    server._slots[remote_slot_b].current_job_id = "job-remote-b"
    server._jobs["job-remote-a"] = JobRecord(
        job_id="job-remote-a",
        owner_principal_id="user-a",
        worker_id="worker-remote",
        thread_slot_id=remote_slot_a,
        priority=2,
        status="running",
        message="running remotely",
    )
    server._jobs["job-remote-b"] = JobRecord(
        job_id="job-remote-b",
        owner_principal_id="user-a",
        worker_id="worker-remote",
        thread_slot_id=remote_slot_b,
        priority=1,
        status="cancelling",
        message="cancelling remotely",
        stop_requested=True,
    )
    server._job_requests["job-remote-a"] = {
        "families": ["lda"],
        "train_runs": [{"session_id": "demo", "run_index": 1}],
        "eval_runs": [{"session_id": "demo", "run_index": 2}],
    }
    server._job_requests["job-remote-b"] = {
        "families": ["lda"],
        "train_runs": [{"session_id": "demo", "run_index": 3}],
        "eval_runs": [{"session_id": "demo", "run_index": 4}],
    }

    await server._handle_recover_worker(
        websocket,
        {"worker_id": "worker-remote", "principal_id": "user-a"},
        request_id="req-recover-worker",
    )

    message = websocket.messages[-1]
    assert message["type"] == "workers"
    assert server._jobs["job-remote-a"].status == "failed"
    assert server._jobs["job-remote-b"].status == "failed"
    assert server._slots[remote_slot_a].current_job_id is None
    assert server._slots[remote_slot_b].current_job_id is None
    assert "job-remote-a" not in server._job_requests
    assert "job-remote-b" not in server._job_requests


@pytest.mark.anyio
async def test_recover_worker_rejects_when_active_job_belongs_to_another_principal() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=1,
        source="external",
        status="online",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="owner-a",
    )
    server._slots[remote_slot_id].current_job_id = "job-remote-owned"
    server._jobs["job-remote-owned"] = JobRecord(
        job_id="job-remote-owned",
        owner_principal_id="owner-a",
        worker_id="worker-remote",
        thread_slot_id=remote_slot_id,
        priority=2,
        status="running",
        message="running remotely",
    )

    await server._handle_recover_worker(
        websocket,
        {"worker_id": "worker-remote", "principal_id": "owner-b"},
        request_id="req-recover-worker-foreign",
    )

    assert websocket.messages[-1]["type"] == "error"
    assert "cannot recover worker worker-remote" in str(websocket.messages[-1]["message"])
    assert server._jobs["job-remote-owned"].status == "running"


@pytest.mark.anyio
async def test_auto_recover_stalled_workers_marks_lost_remote_jobs_failed() -> None:
    server = MlControlPlaneServer(build_base_args())
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=1,
        source="external",
        status="online",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )
    server._slots[remote_slot_id].current_job_id = "job-remote-running"
    server._jobs["job-remote-running"] = JobRecord(
        job_id="job-remote-running",
        owner_principal_id="user-a",
        worker_id="worker-remote",
        thread_slot_id=remote_slot_id,
        priority=2,
        status="running",
        message="running remotely",
    )
    server._job_requests["job-remote-running"] = {
        "families": ["lda"],
        "train_runs": [{"session_id": "demo", "run_index": 1}],
        "eval_runs": [{"session_id": "demo", "run_index": 2}],
    }

    await server._auto_recover_stalled_workers()

    assert server._jobs["job-remote-running"].status == "failed"
    assert "Automatically recovered" in server._jobs["job-remote-running"].message
    assert server._slots[remote_slot_id].current_job_id is None
    assert "job-remote-running" not in server._job_requests


@pytest.mark.anyio
async def test_auto_recover_stalled_workers_skips_jobs_before_deadline() -> None:
    server = MlControlPlaneServer(build_base_args())
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=MODULE.now_us() - 20_000_000,
        source="external",
        status="online",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )
    server._slots[remote_slot_id].current_job_id = "job-remote-running"
    server._jobs["job-remote-running"] = JobRecord(
        job_id="job-remote-running",
        owner_principal_id="user-a",
        worker_id="worker-remote",
        thread_slot_id=remote_slot_id,
        priority=2,
        status="running",
        message="running remotely",
    )

    await server._auto_recover_stalled_workers()

    assert server._jobs["job-remote-running"].status == "running"
    assert server._slots[remote_slot_id].current_job_id == "job-remote-running"


@pytest.mark.anyio
async def test_start_job_queues_external_worker_slot_for_claim() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=1,
        source="external",
        status="online",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )

    await server._handle_start_train_validate_job(
        websocket,
        {
            "owner_principal_id": "user-a",
            "thread_slot_id": remote_slot_id,
            "families": ["lda"],
            "train_runs": [{"session_id": "demo", "run_index": 1}],
            "eval_runs": [{"session_id": "demo", "run_index": 2}],
        },
        request_id="req-start-remote",
    )

    accepted = websocket.messages[-1]
    assert accepted["type"] == "job_accepted"
    job_id = str(accepted["job_id"])
    assert server._jobs[job_id].worker_id == "worker-remote"
    assert server._jobs[job_id].status == "queued"
    assert server._job_requests[job_id]["families"] == ["lda"]
    assert server._slots[remote_slot_id].current_job_id is None


@pytest.mark.anyio
async def test_claim_worker_slot_job_returns_remote_dispatch_payload() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=1,
        source="external",
        status="online",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )

    await server._handle_start_train_validate_job(
        websocket,
        {
            "owner_principal_id": "user-a",
            "thread_slot_id": remote_slot_id,
            "families": ["lda"],
            "train_runs": [{"session_id": "demo", "run_index": 1}],
            "eval_runs": [{"session_id": "demo", "run_index": 2}],
        },
        request_id="req-start-remote",
    )

    await server._handle_claim_worker_slot_job(
        websocket,
        {"worker_id": "worker-remote", "slot_id": remote_slot_id},
        request_id="req-claim-remote",
    )

    claim_message = websocket.messages[-1]
    assert claim_message["type"] == "worker_job_claim"
    assert claim_message["job"]["status"] == "running"
    assert claim_message["job"]["request"]["families"] == ["lda"]
    assert server._slots[remote_slot_id].current_job_id == claim_message["job"]["job_id"]


@pytest.mark.anyio
async def test_claim_worker_slot_job_rejects_stale_worker_session() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=1,
        source="external",
        status="online",
        session_id="session-live",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )

    await server._handle_claim_worker_slot_job(
        websocket,
        {
            "worker_id": "worker-remote",
            "slot_id": remote_slot_id,
            "worker_session_id": "session-stale",
        },
        request_id="req-claim-stale-session",
    )

    assert websocket.messages[-1]["type"] == "error"
    assert "session mismatch" in str(websocket.messages[-1]["message"])
    assert server._slots[remote_slot_id].current_job_id is None


@pytest.mark.anyio
async def test_claim_worker_slot_job_skips_claims_while_worker_draining() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=1,
        source="external",
        status="online",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )

    await server._handle_start_train_validate_job(
        websocket,
        {
            "owner_principal_id": "user-a",
            "thread_slot_id": remote_slot_id,
            "families": ["lda"],
            "train_runs": [{"session_id": "demo", "run_index": 1}],
            "eval_runs": [{"session_id": "demo", "run_index": 2}],
        },
        request_id="req-start-remote-draining",
    )
    job_id = str(websocket.messages[-1]["job_id"])
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=1,
        source="external",
        status="draining",
    )

    await server._handle_claim_worker_slot_job(
        websocket,
        {"worker_id": "worker-remote", "slot_id": remote_slot_id},
        request_id="req-claim-remote-draining",
    )

    claim_message = websocket.messages[-1]
    assert claim_message["type"] == "worker_job_claim"
    assert claim_message["job"] is None
    assert server._jobs[job_id].status == "queued"
    assert server._slots[remote_slot_id].current_job_id is None


@pytest.mark.anyio
async def test_update_worker_status_is_persistent_and_heartbeats_keep_draining() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=1,
        source="external",
        status="online",
        session_id="session-a",
    )

    await server._handle_update_worker_status(
        websocket,
        {"worker_id": "worker-remote", "status": "draining"},
        request_id="req-drain-worker",
    )

    assert server._workers["worker-remote"].status == "draining"
    drain_message = websocket.messages[-1]
    remote_summary = next(
        worker for worker in drain_message["workers"] if worker["worker_id"] == "worker-remote"
    )
    assert remote_summary["worker_status"] == "draining"

    await server._handle_worker_heartbeat(
        websocket,
        {
            "worker_id": "worker-remote",
            "slot_count": 1,
            "status": "online",
            "worker_session_id": "session-a",
        },
        request_id="req-worker-heartbeat",
    )

    assert server._workers["worker-remote"].status == "draining"

    await server._handle_update_worker_status(
        websocket,
        {"worker_id": "worker-remote", "status": "online"},
        request_id="req-resume-worker",
    )

    assert server._workers["worker-remote"].status == "online"


@pytest.mark.anyio
async def test_wait_worker_drain_ready_returns_immediately_for_ready_worker() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=MODULE.now_us(),
        source="external",
        status="draining",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )

    await server._handle_wait_worker_drain_ready(
        websocket,
        {"worker_id": "worker-remote", "timeout_s": 0},
        request_id="req-wait-drain-ready",
    )

    message = websocket.messages[-1]
    assert message["type"] == "worker_drain_status"
    assert message["worker_id"] == "worker-remote"
    assert message["drain_ready"] is True
    assert message["timed_out"] is False


@pytest.mark.anyio
async def test_wait_worker_drain_ready_times_out_when_work_remains() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=MODULE.now_us(),
        source="external",
        status="draining",
    )
    slot = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )
    slot.current_job_id = "job-remote-running"
    server._slots[remote_slot_id] = slot
    server._jobs["job-remote-running"] = JobRecord(
        job_id="job-remote-running",
        owner_principal_id="user-a",
        worker_id="worker-remote",
        thread_slot_id=remote_slot_id,
        priority=1,
        status="running",
    )

    await server._handle_wait_worker_drain_ready(
        websocket,
        {"worker_id": "worker-remote", "timeout_s": 0},
        request_id="req-wait-drain-timeout",
    )

    message = websocket.messages[-1]
    assert message["type"] == "worker_drain_status"
    assert message["drain_ready"] is False
    assert message["drain_remaining_job_count"] == 1
    assert message["timed_out"] is True


@pytest.mark.anyio
async def test_wait_worker_drain_ready_waits_until_running_job_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=MODULE.now_us(),
        source="external",
        status="draining",
    )
    slot = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )
    slot.current_job_id = "job-remote-running"
    server._slots[remote_slot_id] = slot
    server._jobs["job-remote-running"] = JobRecord(
        job_id="job-remote-running",
        owner_principal_id="user-a",
        worker_id="worker-remote",
        thread_slot_id=remote_slot_id,
        priority=1,
        status="running",
    )

    monkeypatch.setattr(MODULE, "SHARED_STATE_DB_POLL_INTERVAL_S", 0.01)

    async def finish_job() -> None:
        await asyncio.sleep(0.02)
        server._jobs["job-remote-running"].status = "completed"
        server._jobs["job-remote-running"].finished_at_us = MODULE.now_us()
        await server._finish_slot_run(slot)

    finisher = asyncio.create_task(finish_job())
    try:
        await server._handle_wait_worker_drain_ready(
            websocket,
            {"worker_id": "worker-remote", "timeout_s": 0.2},
            request_id="req-wait-drain-finish",
        )
    finally:
        await asyncio.gather(finisher, return_exceptions=True)

    message = websocket.messages[-1]
    assert message["type"] == "worker_drain_status"
    assert message["drain_ready"] is True
    assert message["drain_remaining_job_count"] == 0
    assert message["timed_out"] is False


@pytest.mark.anyio
async def test_embedded_draining_defers_local_queue_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = MlControlPlaneServer(build_base_args())
    slot = next(iter(server._slots.values()))
    server._workers[server._worker_id] = MODULE.WorkerNodeRecord(
        worker_id=server._worker_id,
        slot_count=server._slot_count,
        last_heartbeat_us=1,
        source="embedded",
        status="draining",
    )
    server._jobs["job-local-draining"] = JobRecord(
        job_id="job-local-draining",
        owner_principal_id=server._default_principal_id,
        worker_id=server._worker_id,
        thread_slot_id=slot.slot_id,
        priority=1,
        status="queued",
        message="Queued while draining",
        created_at_us=100,
        sequence=1,
        queue_token=0,
    )
    server._job_requests["job-local-draining"] = {
        "broker": "kafka:29092",
        "families": ["lda"],
        "train_runs": [{"session_id": "demo", "run_index": 1}],
        "eval_runs": [{"session_id": "demo", "run_index": 2}],
    }
    await slot.queue.put((-1, 1, "job-local-draining", 0))

    def fail_run_pipeline(*args, **kwargs):
        raise AssertionError("run_pipeline should not start while the worker is draining")

    monkeypatch.setattr(MODULE, "run_pipeline", fail_run_pipeline)

    slot_task = asyncio.create_task(server._run_slot(slot))
    try:
        await asyncio.sleep(0.05)
        assert server._jobs["job-local-draining"].status == "queued"
        assert slot.current_job_id is None
    finally:
        slot_task.cancel()
        await asyncio.gather(slot_task, return_exceptions=True)


@pytest.mark.anyio
async def test_report_worker_job_state_completes_remote_job() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=1,
        source="external",
        status="online",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )

    await server._handle_start_train_validate_job(
        websocket,
        {
            "owner_principal_id": "user-a",
            "thread_slot_id": remote_slot_id,
            "families": ["lda"],
            "train_runs": [{"session_id": "demo", "run_index": 1}],
            "eval_runs": [{"session_id": "demo", "run_index": 2}],
        },
        request_id="req-start-remote",
    )
    job_id = str(websocket.messages[-1]["job_id"])

    await server._handle_claim_worker_slot_job(
        websocket,
        {"worker_id": "worker-remote", "slot_id": remote_slot_id},
        request_id="req-claim-remote",
    )

    await server._handle_report_worker_job_state(
        websocket,
        {
            "worker_id": "worker-remote",
            "job_id": job_id,
            "status": "completed",
            "message": "remote run complete",
            "report": {
                "broker": "kafka:29092",
                "train_runs": [{"session_id": "demo", "run_index": 1, "device_id": "emg01"}],
                "eval_runs": [{"session_id": "demo", "run_index": 2, "device_id": "emg01"}],
                "results": [],
                "selected_family": "lda",
            },
        },
        request_id="req-report-remote",
    )

    status_message = websocket.messages[-1]
    assert status_message["type"] == "job_status"
    assert status_message["status"] == "completed"
    assert server._jobs[job_id].report["artifact_storage"] == "ephemeral_scratch"
    assert server._slots[remote_slot_id].current_job_id is None
    assert job_id not in server._job_requests


@pytest.mark.anyio
async def test_report_worker_job_state_rejects_stale_worker_session() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=1,
        source="external",
        status="online",
        session_id="session-live",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )
    server._jobs["job-remote"] = JobRecord(
        job_id="job-remote",
        owner_principal_id="user-a",
        worker_id="worker-remote",
        thread_slot_id=remote_slot_id,
        priority=1,
        status="running",
        message="running",
        created_at_us=100,
        started_at_us=120,
        sequence=1,
    )
    server._slots[remote_slot_id].current_job_id = "job-remote"

    await server._handle_report_worker_job_state(
        websocket,
        {
            "worker_id": "worker-remote",
            "worker_session_id": "session-stale",
            "job_id": "job-remote",
            "status": "completed",
            "message": "remote run complete",
        },
        request_id="req-report-stale-session",
    )

    assert websocket.messages[-1]["type"] == "error"
    assert "session mismatch" in str(websocket.messages[-1]["message"])
    assert server._jobs["job-remote"].status == "running"


@pytest.mark.anyio
async def test_start_job_rejects_unassigned_slot() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    slot = next(iter(server._slots.values()))
    slot.owner_principal_id = None

    await server._handle_start_train_validate_job(
        websocket,
        {
            "owner_principal_id": "user-a",
            "thread_slot_id": slot.slot_id,
            "train_runs": [{"session_id": "demo", "run_index": 1}],
            "eval_runs": [{"session_id": "demo", "run_index": 2}],
        },
        request_id="req-start",
    )

    assert websocket.messages[-1]["type"] == "error"
    assert "is unassigned; assign it before starting a job" in str(
        websocket.messages[-1]["message"]
    )


@pytest.mark.anyio
async def test_start_job_rejects_draining_worker_slot() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=MODULE.now_us(),
        source="external",
        status="draining",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )

    await server._handle_start_train_validate_job(
        websocket,
        {
            "owner_principal_id": "user-a",
            "thread_slot_id": remote_slot_id,
            "train_runs": [{"session_id": "demo", "run_index": 1}],
            "eval_runs": [{"session_id": "demo", "run_index": 2}],
        },
        request_id="req-start-draining",
    )

    assert websocket.messages[-1]["type"] == "error"
    assert "is draining and not accepting new jobs" in str(websocket.messages[-1]["message"])


@pytest.mark.anyio
async def test_start_job_rejects_unsupported_selected_fields() -> None:
    server = MlControlPlaneServer(build_base_args())
    websocket = FakeWebSocket()
    slot = next(iter(server._slots.values()))
    server._require_authenticated_user = (
        lambda *_args, **_kwargs: asyncio.sleep(
            0,
            result=argparse.Namespace(
                username="user-a",
                is_admin=False,
                shared_compute_access=True,
            ),
        )
    )

    await server._handle_start_train_validate_job(
        websocket,
        {
            "owner_principal_id": "user-a",
            "thread_slot_id": slot.slot_id,
            "train_runs": [{"session_id": "demo", "run_index": 1}],
            "eval_runs": [{"session_id": "demo", "run_index": 2}],
            "selected_fields": ["device_ts_us"],
        },
        request_id="req-start-invalid-fields",
    )

    assert websocket.messages[-1]["type"] == "error"
    assert "unsupported selected fields" in str(websocket.messages[-1]["message"])


@pytest.mark.anyio
async def test_run_job_marks_cancelled_when_pipeline_raises_cancel(monkeypatch, tmp_path) -> None:
    server = MlControlPlaneServer(build_base_args())
    slot = next(iter(server._slots.values()))
    job = JobRecord(
        job_id="job-cancel",
        owner_principal_id="default",
        worker_id=slot.worker_id,
        thread_slot_id=slot.slot_id,
        priority=0,
        status="queued",
    )
    server._jobs[job.job_id] = job
    server._job_stop_events[job.job_id] = MODULE.threading.Event()

    def fake_run_pipeline(args, progress, should_stop):
        server._job_stop_events[job.job_id].set()
        if should_stop():
            raise PipelineCancelledError("pipeline cancelled")
        raise AssertionError("expected cancellation path")

    monkeypatch.setattr(MODULE, "run_pipeline", fake_run_pipeline)

    await server._run_job_in_slot(
        slot,
        job.job_id,
        argparse.Namespace(output_dir=str(tmp_path), no_direct_assign=False),
        tmp_path,
    )

    assert server._jobs[job.job_id].status == "cancelled"


@pytest.mark.anyio
async def test_scheduler_state_persists_slot_owner_and_jobs(tmp_path) -> None:
    args = build_base_args()
    args.state_json = str(tmp_path / "scheduler-state.json")
    server = MlControlPlaneServer(args)
    slot = next(iter(server._slots.values()))
    slot.owner_principal_id = "user-a"
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=3,
        last_heartbeat_us=1234,
        source="external",
        status="online",
    )
    server._slots[build_thread_slot_id("worker-remote", 0)] = ThreadSlotState(
        slot_id=build_thread_slot_id("worker-remote", 0),
        worker_id="worker-remote",
        slot_index=0,
    )
    server._jobs["job-1"] = JobRecord(
        job_id="job-1",
        owner_principal_id="user-a",
        worker_id=slot.worker_id,
        thread_slot_id=slot.slot_id,
        priority=3,
        status="completed",
        message="done",
        created_at_us=100,
        finished_at_us=200,
        sequence=1,
        restart_count=2,
    )

    await server._persist_state()

    payload = json.loads(Path(args.state_json).read_text(encoding="utf-8"))
    assert payload["workers"][0]["worker_id"] == "worker-remote"
    assert any(slot_payload["worker_id"] == "worker-remote" for slot_payload in payload["slots"])
    assert any(slot_payload["owner_principal_id"] == "user-a" for slot_payload in payload["slots"])
    assert payload["jobs"][0]["job_id"] == "job-1"

    reloaded = MlControlPlaneServer(args)

    assert reloaded._workers["worker-remote"].slot_count == 3
    assert build_thread_slot_id("worker-remote", 0) in reloaded._slots
    assert reloaded._slots[slot.slot_id].owner_principal_id == "user-a"
    assert reloaded._jobs["job-1"].status == "completed"
    assert reloaded._jobs["job-1"].restart_count == 2


@pytest.mark.anyio
async def test_scheduler_state_db_persists_slot_owner_and_jobs(tmp_path) -> None:
    args = build_base_args()
    args.state_db = str(tmp_path / "scheduler-state.db")
    server = MlControlPlaneServer(args)
    slot = next(iter(server._slots.values()))
    slot.owner_principal_id = "user-db"
    server._workers["worker-db"] = MODULE.WorkerNodeRecord(
        worker_id="worker-db",
        slot_count=7,
        last_heartbeat_us=4321,
        source="external",
        status="online",
    )
    server._slots[build_thread_slot_id("worker-db", 0)] = ThreadSlotState(
        slot_id=build_thread_slot_id("worker-db", 0),
        worker_id="worker-db",
        slot_index=0,
    )
    server._jobs["job-db"] = JobRecord(
        job_id="job-db",
        owner_principal_id="user-db",
        worker_id=slot.worker_id,
        thread_slot_id=slot.slot_id,
        priority=4,
        status="completed",
        message="done in db",
        created_at_us=111,
        finished_at_us=222,
        sequence=2,
        restart_count=1,
    )

    await server._persist_state()

    with sqlite3.connect(args.state_db) as connection:
        worker_row = connection.execute(
            "SELECT slot_count, status FROM scheduler_workers WHERE worker_id = ?",
            ("worker-db",),
        ).fetchone()
        slot_row = connection.execute(
            "SELECT owner_principal_id FROM scheduler_slots WHERE slot_id = ?",
            (slot.slot_id,),
        ).fetchone()
        job_row = connection.execute(
            "SELECT status, message, restart_count FROM scheduler_jobs WHERE job_id = ?",
            ("job-db",),
        ).fetchone()

    assert worker_row == (7, "online")
    assert slot_row == ("user-db",)
    assert job_row == ("completed", "done in db", 1)

    reloaded = MlControlPlaneServer(args)

    assert reloaded._workers["worker-db"].slot_count == 7
    assert build_thread_slot_id("worker-db", 0) in reloaded._slots
    assert reloaded._slots[slot.slot_id].owner_principal_id == "user-db"
    assert reloaded._jobs["job-db"].status == "completed"
    assert reloaded._jobs["job-db"].restart_count == 1


@pytest.mark.anyio
async def test_scheduler_state_db_persistence_increments_revision(tmp_path) -> None:
    args = build_base_args()
    args.state_db = str(tmp_path / "scheduler-state.db")
    server = MlControlPlaneServer(args)

    await server._persist_state()
    first_revision = scheduler_state_revision(MODULE.load_scheduler_state_db(Path(args.state_db)))
    assert server._state_db_revision == first_revision

    next(iter(server._slots.values())).owner_principal_id = "user-revision"
    await server._persist_state()
    second_revision = scheduler_state_revision(MODULE.load_scheduler_state_db(Path(args.state_db)))

    assert first_revision >= 1
    assert second_revision == first_revision + 1
    assert server._state_db_revision == second_revision
    assert load_scheduler_state_db_revision(Path(args.state_db)) == second_revision


@pytest.mark.anyio
async def test_scheduler_state_db_persistence_removes_stale_rows(tmp_path) -> None:
    args = build_base_args()
    args.state_db = str(tmp_path / "scheduler-state.db")
    server = MlControlPlaneServer(args)
    remote_slot_id = build_thread_slot_id("worker-stale", 0)
    embedded_slot_id = next(iter(server._slots.keys()))

    server._workers["worker-stale"] = MODULE.WorkerNodeRecord(
        worker_id="worker-stale",
        slot_count=1,
        last_heartbeat_us=99,
        source="external",
        status="online",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-stale",
        slot_index=0,
        owner_principal_id="user-stale",
    )
    server._jobs["job-stale"] = JobRecord(
        job_id="job-stale",
        owner_principal_id="user-stale",
        worker_id="worker-stale",
        thread_slot_id=remote_slot_id,
        priority=1,
        status="completed",
        message="stale job",
        created_at_us=100,
        finished_at_us=200,
        sequence=1,
    )

    await server._persist_state()

    server._workers.pop("worker-stale", None)
    server._slots.pop(remote_slot_id, None)
    server._jobs.pop("job-stale", None)
    server._slots[embedded_slot_id].owner_principal_id = "user-live"

    await server._persist_state()

    with sqlite3.connect(args.state_db) as connection:
        stale_worker_row = connection.execute(
            "SELECT worker_id FROM scheduler_workers WHERE worker_id = ?",
            ("worker-stale",),
        ).fetchone()
        stale_slot_row = connection.execute(
            "SELECT slot_id FROM scheduler_slots WHERE slot_id = ?",
            (remote_slot_id,),
        ).fetchone()
        stale_job_row = connection.execute(
            "SELECT job_id FROM scheduler_jobs WHERE job_id = ?",
            ("job-stale",),
        ).fetchone()
        live_slot_row = connection.execute(
            "SELECT owner_principal_id FROM scheduler_slots WHERE slot_id = ?",
            (embedded_slot_id,),
        ).fetchone()

    assert stale_worker_row is None
    assert stale_slot_row is None
    assert stale_job_row is None
    assert live_slot_row == ("user-live",)


@pytest.mark.anyio
async def test_scheduler_state_db_persistence_skips_unchanged_entity_row_updates(
    tmp_path,
) -> None:
    args = build_base_args()
    args.state_db = str(tmp_path / "scheduler-state.db")
    server = MlControlPlaneServer(args)
    embedded_slot_id = next(iter(server._slots.keys()))

    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=2,
        last_heartbeat_us=123,
        source="external",
        status="online",
    )
    server._slots[build_thread_slot_id("worker-remote", 0)] = ThreadSlotState(
        slot_id=build_thread_slot_id("worker-remote", 0),
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-remote",
    )
    server._slots[embedded_slot_id].owner_principal_id = "user-local"
    server._jobs["job-audit"] = JobRecord(
        job_id="job-audit",
        owner_principal_id="user-local",
        worker_id=server._worker_id,
        thread_slot_id=embedded_slot_id,
        priority=2,
        status="completed",
        message="audit baseline",
        created_at_us=100,
        finished_at_us=200,
        sequence=1,
    )

    await server._persist_state()

    with sqlite3.connect(args.state_db) as connection:
        connection.execute(
            """
            CREATE TABLE scheduler_update_audit (
                table_name TEXT NOT NULL,
                row_key TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TRIGGER scheduler_workers_update_audit
            AFTER UPDATE ON scheduler_workers
            BEGIN
                INSERT INTO scheduler_update_audit (table_name, row_key)
                VALUES ('scheduler_workers', NEW.worker_id);
            END
            """
        )
        connection.execute(
            """
            CREATE TRIGGER scheduler_slots_update_audit
            AFTER UPDATE ON scheduler_slots
            BEGIN
                INSERT INTO scheduler_update_audit (table_name, row_key)
                VALUES ('scheduler_slots', NEW.slot_id);
            END
            """
        )
        connection.execute(
            """
            CREATE TRIGGER scheduler_jobs_update_audit
            AFTER UPDATE ON scheduler_jobs
            BEGIN
                INSERT INTO scheduler_update_audit (table_name, row_key)
                VALUES ('scheduler_jobs', NEW.job_id);
            END
            """
        )
        connection.commit()

    await server._persist_state()

    with sqlite3.connect(args.state_db) as connection:
        unchanged_updates = connection.execute(
            """
            SELECT table_name, row_key
            FROM scheduler_update_audit
            ORDER BY table_name, row_key
            """
        ).fetchall()

    assert unchanged_updates == []

    server._jobs["job-audit"].message = "audit updated"
    await server._persist_state()

    with sqlite3.connect(args.state_db) as connection:
        changed_updates = connection.execute(
            """
            SELECT table_name, row_key
            FROM scheduler_update_audit
            ORDER BY table_name, row_key
            """
        ).fetchall()

    assert changed_updates == [("scheduler_jobs", "job-audit")]


@pytest.mark.anyio
async def test_scheduler_state_db_persistence_uses_key_only_probes_for_row_diff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    args = build_base_args()
    args.state_db = str(tmp_path / "scheduler-state.db")
    trace_statements: list[str] = []
    original_open_scheduler_state_db = MODULE.open_scheduler_state_db

    def traced_open_scheduler_state_db(path: Path) -> sqlite3.Connection:
        connection = original_open_scheduler_state_db(path)
        connection.set_trace_callback(trace_statements.append)
        return connection

    monkeypatch.setattr(
        MODULE,
        "open_scheduler_state_db",
        traced_open_scheduler_state_db,
    )
    server = MlControlPlaneServer(args)
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    embedded_slot_id = next(iter(server._slots.keys()))

    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=123,
        source="external",
        status="online",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-remote",
    )
    server._slots[embedded_slot_id].owner_principal_id = "user-local"
    server._jobs["job-audit"] = JobRecord(
        job_id="job-audit",
        owner_principal_id="user-local",
        worker_id=server._worker_id,
        thread_slot_id=embedded_slot_id,
        priority=2,
        status="completed",
        message="audit baseline",
        created_at_us=100,
        finished_at_us=200,
        sequence=1,
    )

    await server._persist_state()
    trace_statements.clear()

    server._jobs["job-audit"].message = "audit updated"
    await server._persist_state()

    normalized_statements = [" ".join(statement.split()) for statement in trace_statements]

    assert any(
        "SELECT worker_id FROM scheduler_workers" in statement
        for statement in normalized_statements
    )
    assert any(
        "SELECT slot_id FROM scheduler_slots" in statement
        for statement in normalized_statements
    )
    assert any(
        "SELECT job_id FROM scheduler_jobs" in statement
        for statement in normalized_statements
    )
    assert not any(
        "SELECT worker_id, slot_count, last_heartbeat_us, source, status, session_id "
        "FROM scheduler_workers" in statement
        for statement in normalized_statements
    )
    assert not any(
        "SELECT slot_id, slot_index, worker_id, owner_principal_id "
        "FROM scheduler_slots" in statement
        for statement in normalized_statements
    )
    assert not any(
        "SELECT job_id, job_type, owner_principal_id, worker_id, thread_slot_id, priority, "
        "status, message, request_json, report_json, error, traceback_text, stop_requested, "
        "created_at_us, started_at_us, finished_at_us, sequence, queue_token, restart_count "
        "FROM scheduler_jobs" in statement
        for statement in normalized_statements
    )


@pytest.mark.anyio
async def test_scheduler_state_db_refreshes_external_state_without_restart(tmp_path) -> None:
    args = build_base_args()
    args.state_db = str(tmp_path / "scheduler-state.db")
    server = MlControlPlaneServer(args)
    websocket = FakeWebSocket()
    remote_slot_id = build_thread_slot_id("worker-remote", 0)

    persist_scheduler_state_db(
        Path(args.state_db),
        worker_id=server._worker_id,
        slot_count=server._slot_count,
        default_principal_id=server._default_principal_id,
        workers=[
            {
                "worker_id": "worker-remote",
                "slot_count": 1,
                "last_heartbeat_us": 321,
                "source": "external",
                "status": "online",
            }
        ],
        slots=[
            {
                "slot_id": remote_slot_id,
                "slot_index": 0,
                "worker_id": "worker-remote",
                "owner_principal_id": "user-a",
            }
        ],
        jobs=[
            {
                "job_id": "job-remote-queued",
                "job_type": "train_validate",
                "owner_principal_id": "user-a",
                "worker_id": "worker-remote",
                "thread_slot_id": remote_slot_id,
                "priority": 5,
                "status": "queued",
                "message": "queued in shared db",
                "request": {
                    "broker": "kafka:29092",
                    "families": ["lda"],
                    "train_runs": [{"session_id": "demo", "run_index": 1}],
                    "eval_runs": [{"session_id": "demo", "run_index": 2}],
                    "rest_gesture": "rest",
                    "active_gesture": "fist",
                    "window_ms": 200,
                    "hop_ms": 50,
                    "vote_windows": 5,
                    "confidence_threshold": 0.6,
                    "min_hold_windows": 2,
                    "emit_only_during_cue_hold": False,
                },
                "created_at_us": 100,
                "sequence": 1,
                "queue_token": 0,
            }
        ],
    )

    await server._handle_message(
        websocket,
        json.dumps({"action": "list_workers", "request_id": "req-workers-refresh"}),
    )
    workers_message = websocket.messages[-1]
    assert any(
        worker["worker_id"] == "worker-remote" for worker in workers_message["workers"]
    )
    assert server._state_db_revision >= 1

    await server._handle_message(
        websocket,
        json.dumps({"action": "list_thread_slots", "request_id": "req-slots-refresh"}),
    )
    slots_message = websocket.messages[-1]
    assert any(slot["slot_id"] == remote_slot_id for slot in slots_message["slots"])

    await server._handle_message(
        websocket,
        json.dumps({"action": "list_jobs", "request_id": "req-jobs-refresh"}),
    )
    jobs_message = websocket.messages[-1]
    assert any(job["job_id"] == "job-remote-queued" for job in jobs_message["jobs"])

    await server._handle_message(
        websocket,
        json.dumps(
            {
                "action": "claim_worker_slot_job",
                "request_id": "req-claim-refresh",
                "worker_id": "worker-remote",
                "slot_id": remote_slot_id,
            }
        ),
    )
    claim_message = websocket.messages[-1]
    assert claim_message["type"] == "worker_job_claim"
    assert claim_message["job"]["job_id"] == "job-remote-queued"
    assert claim_message["job"]["request"]["families"] == ["lda"]


@pytest.mark.anyio
async def test_scheduler_state_db_refresh_skips_full_load_when_revision_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    args = build_base_args()
    args.state_db = str(tmp_path / "scheduler-state.db")
    server = MlControlPlaneServer(args)
    await server._persist_state()

    monkeypatch.setattr(MODULE, "load_scheduler_state_db_revision", lambda path: server._state_db_revision)

    def fail_full_load(path: Path) -> dict[str, object]:
        raise AssertionError("full scheduler-state load should not run")

    monkeypatch.setattr(MODULE, "load_scheduler_state_db", fail_full_load)

    await server._refresh_shared_state_from_db_if_needed()


@pytest.mark.anyio
async def test_scheduler_state_db_refresh_loads_full_state_after_revision_advance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    args = build_base_args()
    args.state_db = str(tmp_path / "scheduler-state.db")
    server = MlControlPlaneServer(args)
    current_revision = server._state_db_revision

    payload = {
        "metadata": {"state_revision": str(current_revision + 1)},
        "workers": [
            {
                "worker_id": "worker-refresh",
                "slot_count": 1,
                "last_heartbeat_us": 123,
                "source": "external",
                "status": "online",
            }
        ],
        "slots": [
            {
                "slot_id": build_thread_slot_id("worker-refresh", 0),
                "slot_index": 0,
                "worker_id": "worker-refresh",
                "owner_principal_id": "user-refresh",
            }
        ],
        "jobs": [],
    }

    monkeypatch.setattr(
        MODULE,
        "load_scheduler_state_db_revision",
        lambda path: current_revision + 1,
    )
    monkeypatch.setattr(MODULE, "load_scheduler_state_db", lambda path: payload)

    await server._refresh_shared_state_from_db_if_needed()

    assert server._state_db_revision == current_revision + 1
    assert "worker-refresh" in server._workers
    assert build_thread_slot_id("worker-refresh", 0) in server._slots


@pytest.mark.anyio
async def test_scheduler_state_db_refresh_skips_revision_probe_inside_poll_window(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    args = build_base_args()
    args.state_db = str(tmp_path / "scheduler-state.db")
    server = MlControlPlaneServer(args)
    server._last_state_db_refresh_check_monotonic = 100.0

    monkeypatch.setattr(MODULE.time, "monotonic", lambda: 100.1)

    def fail_revision_probe(path: Path) -> int:
        raise AssertionError("revision probe should not run inside poll window")

    monkeypatch.setattr(MODULE, "load_scheduler_state_db_revision", fail_revision_probe)

    await server._refresh_shared_state_from_db_if_needed()


@pytest.mark.anyio
async def test_scheduler_state_db_refresh_force_bypasses_poll_window(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    args = build_base_args()
    args.state_db = str(tmp_path / "scheduler-state.db")
    server = MlControlPlaneServer(args)
    current_revision = server._state_db_revision
    server._last_state_db_refresh_check_monotonic = 100.0

    payload = {
        "metadata": {"state_revision": str(current_revision + 1)},
        "workers": [],
        "slots": [],
        "jobs": [],
    }

    monkeypatch.setattr(MODULE.time, "monotonic", lambda: 100.1)
    monkeypatch.setattr(
        MODULE,
        "load_scheduler_state_db_revision",
        lambda path: current_revision + 1,
    )
    monkeypatch.setattr(MODULE, "load_scheduler_state_db", lambda path: payload)

    await server._refresh_shared_state_from_db_if_needed(force=True)

    assert server._state_db_revision == current_revision + 1


def test_scheduler_load_marks_inflight_jobs_failed_after_restart(tmp_path) -> None:
    state_path = tmp_path / "scheduler-state.json"
    state_path.write_text(
        json.dumps(
            {
                "slots": [
                    {
                        "slot_id": "worker-test:slot-01",
                        "slot_index": 0,
                        "worker_id": "worker-test",
                        "owner_principal_id": "default",
                    }
                ],
                "jobs": [
                    {
                        "job_id": "job-inflight",
                        "job_type": "train_validate",
                        "owner_principal_id": "default",
                        "worker_id": "worker-test",
                        "thread_slot_id": "worker-test:slot-01",
                        "priority": 1,
                        "status": "running",
                        "message": "running before restart",
                        "created_at_us": 100,
                        "started_at_us": 120,
                        "sequence": 1,
                        "queue_token": 0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    args = build_base_args()
    args.state_json = str(state_path)
    reloaded = MlControlPlaneServer(args)

    assert reloaded._jobs["job-inflight"].status == "failed"
    assert "control-plane restart" in reloaded._jobs["job-inflight"].message


def test_scheduler_load_keeps_external_running_job_recoverable_after_restart(
    tmp_path,
) -> None:
    state_path = tmp_path / "scheduler-state.json"
    state_path.write_text(
        json.dumps(
            {
                "workers": [
                    {
                        "worker_id": "worker-remote",
                        "slot_count": 1,
                        "last_heartbeat_us": 90,
                        "source": "external",
                        "status": "online",
                    }
                ],
                "slots": [
                    {
                        "slot_id": "worker-remote:slot-01",
                        "slot_index": 0,
                        "worker_id": "worker-remote",
                        "owner_principal_id": "user-a",
                    }
                ],
                "jobs": [
                    {
                        "job_id": "job-remote-running",
                        "job_type": "train_validate",
                        "owner_principal_id": "user-a",
                        "worker_id": "worker-remote",
                        "thread_slot_id": "worker-remote:slot-01",
                        "priority": 1,
                        "status": "running",
                        "message": "running before restart",
                        "created_at_us": 100,
                        "started_at_us": 120,
                        "sequence": 1,
                        "queue_token": 0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    args = build_base_args()
    args.state_json = str(state_path)
    reloaded = MlControlPlaneServer(args)

    job = reloaded._jobs["job-remote-running"]
    slot = reloaded._slots["worker-remote:slot-01"]
    assert job.status == "running"
    assert "awaiting external worker state" in job.message
    assert slot.current_job_id == "job-remote-running"
    assert slot.busy_intervals[-1][1] is None


@pytest.mark.anyio
async def test_scheduler_load_restores_queued_remote_job_for_claim_after_restart(
    tmp_path,
) -> None:
    state_path = tmp_path / "scheduler-state.json"
    state_path.write_text(
        json.dumps(
            {
                "workers": [
                    {
                        "worker_id": "worker-remote",
                        "slot_count": 1,
                        "last_heartbeat_us": 90,
                        "source": "external",
                        "status": "online",
                    }
                ],
                "slots": [
                    {
                        "slot_id": "worker-remote:slot-01",
                        "slot_index": 0,
                        "worker_id": "worker-remote",
                        "owner_principal_id": "user-a",
                    }
                ],
                "jobs": [
                    {
                        "job_id": "job-remote-queued",
                        "job_type": "train_validate",
                        "owner_principal_id": "user-a",
                        "worker_id": "worker-remote",
                        "thread_slot_id": "worker-remote:slot-01",
                        "priority": 3,
                        "status": "queued",
                        "message": "queued before restart",
                        "request": {
                            "broker": "kafka:29092",
                            "families": ["lda"],
                            "train_runs": [{"session_id": "demo", "run_index": 1}],
                            "eval_runs": [{"session_id": "demo", "run_index": 2}],
                            "rest_gesture": "rest",
                            "active_gesture": "fist",
                            "window_ms": 200,
                            "hop_ms": 50,
                            "vote_windows": 5,
                            "confidence_threshold": 0.6,
                            "min_hold_windows": 2,
                            "emit_only_during_cue_hold": False,
                        },
                        "created_at_us": 100,
                        "sequence": 1,
                        "queue_token": 0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    args = build_base_args()
    args.state_json = str(state_path)
    reloaded = MlControlPlaneServer(args)
    websocket = FakeWebSocket()

    await reloaded._handle_claim_worker_slot_job(
        websocket,
        {"worker_id": "worker-remote", "slot_id": "worker-remote:slot-01"},
        request_id="req-claim-recovered",
    )

    claim_message = websocket.messages[-1]
    assert claim_message["type"] == "worker_job_claim"
    assert claim_message["job"]["job_id"] == "job-remote-queued"
    assert claim_message["job"]["request"]["families"] == ["lda"]
    assert reloaded._slots["worker-remote:slot-01"].current_job_id == "job-remote-queued"


def test_scheduler_state_db_load_marks_inflight_jobs_failed_after_restart(
    tmp_path,
) -> None:
    state_db_path = tmp_path / "scheduler-state.db"
    with sqlite3.connect(state_db_path) as connection:
        connection.execute(
            """
            CREATE TABLE scheduler_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE scheduler_slots (
                slot_id TEXT PRIMARY KEY,
                slot_index INTEGER NOT NULL,
                worker_id TEXT NOT NULL,
                owner_principal_id TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE scheduler_jobs (
                job_id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                owner_principal_id TEXT,
                worker_id TEXT NOT NULL,
                thread_slot_id TEXT NOT NULL,
                priority INTEGER NOT NULL,
                status TEXT NOT NULL,
                message TEXT NOT NULL,
                report_json TEXT,
                error TEXT,
                traceback_text TEXT,
                stop_requested INTEGER NOT NULL,
                created_at_us INTEGER NOT NULL,
                started_at_us INTEGER,
                finished_at_us INTEGER,
                sequence INTEGER NOT NULL,
                queue_token INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO scheduler_slots (
                slot_id, slot_index, worker_id, owner_principal_id
            ) VALUES (?, ?, ?, ?)
            """,
            ("worker-test:slot-01", 0, "worker-test", "default"),
        )
        connection.execute(
            """
            INSERT INTO scheduler_jobs (
                job_id,
                job_type,
                owner_principal_id,
                worker_id,
                thread_slot_id,
                priority,
                status,
                message,
                report_json,
                error,
                traceback_text,
                stop_requested,
                created_at_us,
                started_at_us,
                finished_at_us,
                sequence,
                queue_token
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job-inflight-db",
                "train_validate",
                "default",
                "worker-test",
                "worker-test:slot-01",
                1,
                "running",
                "running before restart",
                None,
                None,
                None,
                0,
                100,
                120,
                None,
                1,
                0,
            ),
        )
        connection.commit()

    args = build_base_args()
    args.state_db = str(state_db_path)
    reloaded = MlControlPlaneServer(args)

    assert reloaded._jobs["job-inflight-db"].status == "failed"
    assert "control-plane restart" in reloaded._jobs["job-inflight-db"].message

    with sqlite3.connect(state_db_path) as connection:
        job_row = connection.execute(
            "SELECT status, message, finished_at_us FROM scheduler_jobs WHERE job_id = ?",
            ("job-inflight-db",),
        ).fetchone()
        revision_row = connection.execute(
            "SELECT value FROM scheduler_metadata WHERE key = 'state_revision'"
        ).fetchone()

    assert job_row is not None
    assert job_row[0] == "failed"
    assert "control-plane restart" in str(job_row[1])
    assert job_row[2] is not None
    assert revision_row is not None


def test_scheduler_state_db_load_keeps_external_running_job_recoverable_after_restart(
    tmp_path,
) -> None:
    state_db_path = tmp_path / "scheduler-state.db"
    with sqlite3.connect(state_db_path) as connection:
        connection.execute(
            """
            CREATE TABLE scheduler_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE scheduler_slots (
                slot_id TEXT PRIMARY KEY,
                slot_index INTEGER NOT NULL,
                worker_id TEXT NOT NULL,
                owner_principal_id TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE scheduler_jobs (
                job_id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                owner_principal_id TEXT,
                worker_id TEXT NOT NULL,
                thread_slot_id TEXT NOT NULL,
                priority INTEGER NOT NULL,
                status TEXT NOT NULL,
                message TEXT NOT NULL,
                report_json TEXT,
                error TEXT,
                traceback_text TEXT,
                stop_requested INTEGER NOT NULL,
                created_at_us INTEGER NOT NULL,
                started_at_us INTEGER,
                finished_at_us INTEGER,
                sequence INTEGER NOT NULL,
                queue_token INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE scheduler_workers (
                worker_id TEXT PRIMARY KEY,
                slot_count INTEGER NOT NULL,
                last_heartbeat_us INTEGER NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO scheduler_workers (
                worker_id, slot_count, last_heartbeat_us, source, status
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("worker-remote", 1, 90, "external", "online"),
        )
        connection.execute(
            """
            INSERT INTO scheduler_slots (
                slot_id, slot_index, worker_id, owner_principal_id
            ) VALUES (?, ?, ?, ?)
            """,
            ("worker-remote:slot-01", 0, "worker-remote", "user-a"),
        )
        connection.execute(
            """
            INSERT INTO scheduler_jobs (
                job_id,
                job_type,
                owner_principal_id,
                worker_id,
                thread_slot_id,
                priority,
                status,
                message,
                report_json,
                error,
                traceback_text,
                stop_requested,
                created_at_us,
                started_at_us,
                finished_at_us,
                sequence,
                queue_token
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job-remote-running-db",
                "train_validate",
                "user-a",
                "worker-remote",
                "worker-remote:slot-01",
                1,
                "running",
                "running before restart",
                None,
                None,
                None,
                0,
                100,
                120,
                None,
                1,
                0,
            ),
        )
        connection.commit()

    args = build_base_args()
    args.state_db = str(state_db_path)
    reloaded = MlControlPlaneServer(args)

    job = reloaded._jobs["job-remote-running-db"]
    slot = reloaded._slots["worker-remote:slot-01"]
    assert job.status == "running"
    assert "awaiting external worker state" in job.message
    assert slot.current_job_id == "job-remote-running-db"

    with sqlite3.connect(state_db_path) as connection:
        job_row = connection.execute(
            "SELECT status, message, finished_at_us FROM scheduler_jobs WHERE job_id = ?",
            ("job-remote-running-db",),
        ).fetchone()
        revision_row = connection.execute(
            "SELECT value FROM scheduler_metadata WHERE key = 'state_revision'"
        ).fetchone()

    assert job_row == (
        "running",
        "Recovered after control-plane restart; awaiting external worker state",
        None,
    )
    assert revision_row is not None


@pytest.mark.anyio
async def test_scheduler_state_db_restores_queued_remote_job_for_claim_after_restart(
    tmp_path,
) -> None:
    args = build_base_args()
    args.state_db = str(tmp_path / "scheduler-state.db")
    server = MlControlPlaneServer(args)
    remote_slot_id = build_thread_slot_id("worker-remote", 0)
    server._workers["worker-remote"] = MODULE.WorkerNodeRecord(
        worker_id="worker-remote",
        slot_count=1,
        last_heartbeat_us=99,
        source="external",
        status="online",
    )
    server._slots[remote_slot_id] = ThreadSlotState(
        slot_id=remote_slot_id,
        worker_id="worker-remote",
        slot_index=0,
        owner_principal_id="user-a",
    )
    server._jobs["job-db-queued"] = JobRecord(
        job_id="job-db-queued",
        owner_principal_id="user-a",
        worker_id="worker-remote",
        thread_slot_id=remote_slot_id,
        priority=4,
        status="queued",
        message="queued in db",
        created_at_us=100,
        sequence=1,
        queue_token=0,
    )
    server._job_requests["job-db-queued"] = {
        "broker": "kafka:29092",
        "families": ["lda"],
        "train_runs": [{"session_id": "demo", "run_index": 1}],
        "eval_runs": [{"session_id": "demo", "run_index": 2}],
        "rest_gesture": "rest",
        "active_gesture": "fist",
        "window_ms": 200,
        "hop_ms": 50,
        "vote_windows": 5,
        "confidence_threshold": 0.6,
        "min_hold_windows": 2,
        "emit_only_during_cue_hold": False,
    }

    await server._persist_state()

    reloaded = MlControlPlaneServer(args)
    websocket = FakeWebSocket()

    await reloaded._handle_claim_worker_slot_job(
        websocket,
        {"worker_id": "worker-remote", "slot_id": remote_slot_id},
        request_id="req-claim-db-recovered",
    )

    claim_message = websocket.messages[-1]
    assert claim_message["type"] == "worker_job_claim"
    assert claim_message["job"]["job_id"] == "job-db-queued"
    assert claim_message["job"]["request"]["families"] == ["lda"]


@pytest.mark.anyio
async def test_scheduler_load_restores_queued_local_job_execution_after_restart(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "scheduler-state.json"
    state_path.write_text(
        json.dumps(
            {
                "slots": [
                    {
                        "slot_id": "worker-test:slot-01",
                        "slot_index": 0,
                        "worker_id": "worker-test",
                        "owner_principal_id": "default",
                    }
                ],
                "jobs": [
                    {
                        "job_id": "job-local-queued",
                        "job_type": "train_validate",
                        "owner_principal_id": "default",
                        "worker_id": "worker-test",
                        "thread_slot_id": "worker-test:slot-01",
                        "priority": 2,
                        "status": "queued",
                        "message": "queued before restart",
                        "request": {
                            "broker": "kafka:29092",
                            "families": ["lda"],
                            "train_runs": [{"session_id": "demo", "run_index": 1}],
                            "eval_runs": [{"session_id": "demo", "run_index": 2}],
                            "rest_gesture": "rest",
                            "active_gesture": "fist",
                            "window_ms": 200,
                            "hop_ms": 50,
                            "vote_windows": 5,
                            "confidence_threshold": 0.6,
                            "min_hold_windows": 2,
                            "emit_only_during_cue_hold": False,
                        },
                        "created_at_us": 100,
                        "sequence": 1,
                        "queue_token": 0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    def fake_run_pipeline(args, progress, should_stop):
        assert should_stop() is False
        progress("recovered queue running")
        return {
            "broker": args.broker,
            "output_dir": args.output_dir,
            "train_runs": [{"session_id": "demo", "run_index": 1, "device_id": "emg01"}],
            "eval_runs": [{"session_id": "demo", "run_index": 2, "device_id": "emg01"}],
            "results": [],
            "selected_family": "lda",
        }

    monkeypatch.setattr(MODULE, "run_pipeline", fake_run_pipeline)

    args = build_base_args()
    args.state_json = str(state_path)
    reloaded = MlControlPlaneServer(args)
    slot = reloaded._slots["worker-test:slot-01"]

    worker_task = asyncio.create_task(reloaded._run_slot(slot))
    try:
        for _ in range(50):
            if reloaded._jobs["job-local-queued"].status == "completed":
                break
            await asyncio.sleep(0.01)
        assert reloaded._jobs["job-local-queued"].status == "completed"
        assert reloaded._jobs["job-local-queued"].report["artifact_storage"] == "ephemeral_scratch"
        assert "job-local-queued" not in reloaded._job_requests
        assert "job-local-queued" not in reloaded._job_payloads
        assert "job-local-queued" not in reloaded._job_stop_events
    finally:
        worker_task.cancel()
        await asyncio.gather(worker_task, return_exceptions=True)


@pytest.mark.anyio
async def test_report_worker_job_state_accepts_running_update_after_restart_recovery(
    tmp_path,
) -> None:
    state_path = tmp_path / "scheduler-state.json"
    state_path.write_text(
        json.dumps(
            {
                "workers": [
                    {
                        "worker_id": "worker-remote",
                        "slot_count": 1,
                        "last_heartbeat_us": 90,
                        "source": "external",
                        "status": "online",
                    }
                ],
                "slots": [
                    {
                        "slot_id": "worker-remote:slot-01",
                        "slot_index": 0,
                        "worker_id": "worker-remote",
                        "owner_principal_id": "user-a",
                    }
                ],
                "jobs": [
                    {
                        "job_id": "job-remote-running",
                        "job_type": "train_validate",
                        "owner_principal_id": "user-a",
                        "worker_id": "worker-remote",
                        "thread_slot_id": "worker-remote:slot-01",
                        "priority": 1,
                        "status": "running",
                        "message": "running before restart",
                        "created_at_us": 100,
                        "started_at_us": 120,
                        "sequence": 1,
                        "queue_token": 0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    args = build_base_args()
    args.state_json = str(state_path)
    reloaded = MlControlPlaneServer(args)
    websocket = FakeWebSocket()

    await reloaded._handle_report_worker_job_state(
        websocket,
        {
            "worker_id": "worker-remote",
            "job_id": "job-remote-running",
            "status": "running",
            "message": "External worker reconnected and confirmed active execution",
        },
        request_id="req-report-running-recovered",
    )

    status_message = websocket.messages[-1]
    assert status_message["type"] == "job_status"
    assert status_message["status"] == "running"
    assert (
        reloaded._jobs["job-remote-running"].message
        == "External worker reconnected and confirmed active execution"
    )
    assert reloaded._slots["worker-remote:slot-01"].current_job_id == "job-remote-running"


@pytest.mark.anyio
async def test_report_worker_job_state_accepts_terminal_update_after_restart_recovery(
    tmp_path,
) -> None:
    state_path = tmp_path / "scheduler-state.json"
    state_path.write_text(
        json.dumps(
            {
                "workers": [
                    {
                        "worker_id": "worker-remote",
                        "slot_count": 1,
                        "last_heartbeat_us": 90,
                        "source": "external",
                        "status": "online",
                    }
                ],
                "slots": [
                    {
                        "slot_id": "worker-remote:slot-01",
                        "slot_index": 0,
                        "worker_id": "worker-remote",
                        "owner_principal_id": "user-a",
                    }
                ],
                "jobs": [
                    {
                        "job_id": "job-remote-running",
                        "job_type": "train_validate",
                        "owner_principal_id": "user-a",
                        "worker_id": "worker-remote",
                        "thread_slot_id": "worker-remote:slot-01",
                        "priority": 1,
                        "status": "running",
                        "message": "running before restart",
                        "created_at_us": 100,
                        "started_at_us": 120,
                        "sequence": 1,
                        "queue_token": 0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    args = build_base_args()
    args.state_json = str(state_path)
    reloaded = MlControlPlaneServer(args)
    websocket = FakeWebSocket()

    await reloaded._handle_report_worker_job_state(
        websocket,
        {
            "worker_id": "worker-remote",
            "job_id": "job-remote-running",
            "status": "completed",
            "message": "remote run complete after reconnect",
            "report": {
                "broker": "kafka:29092",
                "train_runs": [{"session_id": "demo", "run_index": 1, "device_id": "emg01"}],
                "eval_runs": [{"session_id": "demo", "run_index": 2, "device_id": "emg01"}],
                "results": [],
                "selected_family": "lda",
            },
        },
        request_id="req-report-recovered",
    )

    status_message = websocket.messages[-1]
    assert status_message["type"] == "job_status"
    assert status_message["status"] == "completed"
    assert reloaded._slots["worker-remote:slot-01"].current_job_id is None
    assert reloaded._jobs["job-remote-running"].report["artifact_storage"] == "ephemeral_scratch"
