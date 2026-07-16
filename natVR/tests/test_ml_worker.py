from __future__ import annotations

import asyncio
import argparse
import importlib.util
from pathlib import Path
import sys
import types

import pytest


CONTROL_PLANE_PATH = (
    Path(__file__).resolve().parents[2]
    / "libnatkit"
    / "scripts"
    / "natkit_ml_control_plane.py"
)
CONTROL_PLANE_SPEC = importlib.util.spec_from_file_location(
    "natkit_ml_control_plane",
    CONTROL_PLANE_PATH,
)
assert CONTROL_PLANE_SPEC is not None
assert CONTROL_PLANE_SPEC.loader is not None
CONTROL_PLANE_MODULE = importlib.util.module_from_spec(CONTROL_PLANE_SPEC)
sys.modules[CONTROL_PLANE_SPEC.name] = CONTROL_PLANE_MODULE
CONTROL_PLANE_SPEC.loader.exec_module(CONTROL_PLANE_MODULE)

WORKER_PATH = (
    Path(__file__).resolve().parents[2]
    / "libnatkit"
    / "scripts"
    / "natkit_ml_worker.py"
)
WORKER_SPEC = importlib.util.spec_from_file_location("natkit_ml_worker", WORKER_PATH)
assert WORKER_SPEC is not None
assert WORKER_SPEC.loader is not None
WORKER_MODULE = importlib.util.module_from_spec(WORKER_SPEC)
sys.modules[WORKER_SPEC.name] = WORKER_MODULE
WORKER_SPEC.loader.exec_module(WORKER_MODULE)

MlWorkerClient = WORKER_MODULE.MlWorkerClient
PipelineCancelledError = WORKER_MODULE.PipelineCancelledError
build_worker_slot_ids = WORKER_MODULE.build_worker_slot_ids
normalize_max_reconnect_delay = WORKER_MODULE.normalize_max_reconnect_delay
normalize_reconnect_delay = WORKER_MODULE.normalize_reconnect_delay
worker_job_should_stop = WORKER_MODULE.worker_job_should_stop


def build_worker_args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        control_plane_url="ws://127.0.0.1:8786",
        worker_id="worker-remote",
        worker_threads=2,
        scratch_root=str(tmp_path),
        claim_poll_interval_s=0.01,
        heartbeat_interval_s=0.01,
        reconnect_delay_s=0.01,
        max_reconnect_delay_s=0.1,
        shutdown_grace_period_s=0.01,
        log_level="INFO",
    )


def build_job_payload(*, status: str = "running", stop_requested: bool = False) -> dict[str, object]:
    return {
        "job_id": "job-1",
        "status": status,
        "stop_requested": stop_requested,
        "request": {
            "families": ["lda"],
            "train_runs": [{"session_id": "demo", "run_index": 1}],
            "eval_runs": [{"session_id": "demo", "run_index": 2}],
        },
    }


def test_build_worker_slot_ids_formats_slot_identifiers() -> None:
    assert build_worker_slot_ids("worker-a", 3) == [
        "worker-a:slot-01",
        "worker-a:slot-02",
        "worker-a:slot-03",
    ]


def test_worker_job_should_stop_uses_status_or_flag() -> None:
    assert worker_job_should_stop({"stop_requested": True}) is True
    assert worker_job_should_stop({"status": "cancelling"}) is True
    assert worker_job_should_stop({"status": "cancelled"}) is True
    assert worker_job_should_stop({"status": "running"}) is False


def test_normalize_reconnect_delays_clamp_to_valid_bounds() -> None:
    assert normalize_reconnect_delay(0.0) == 0.1
    assert normalize_reconnect_delay(2.5) == 2.5
    assert normalize_max_reconnect_delay(1.0, 0.25) == 1.0
    assert normalize_max_reconnect_delay(1.0, 4.0) == 4.0


def test_state_update_conflict_requires_stop_matches_terminal_and_missing_job_errors(
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))

    assert client._state_update_conflict_requires_stop(
        "job job-1 is already terminal in status failed"
    )
    assert client._state_update_conflict_requires_stop("job_id not found: job-1")
    assert client._state_update_conflict_requires_stop("other error") is False


def test_request_shutdown_sets_stop_flags_and_active_job_stop_events(tmp_path: Path) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    stop_event = WORKER_MODULE.threading.Event()
    client._active_job_stop_events["job-1"] = stop_event

    client.request_shutdown()

    assert client._stop_requested.is_set() is True
    assert client._shutdown_event.is_set() is True
    assert stop_event.is_set() is True


@pytest.mark.anyio
async def test_run_returns_without_connecting_after_shutdown_requested(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    client.request_shutdown()

    def fail_connect(*args, **kwargs):
        raise AssertionError("websocket connect should not run after shutdown request")

    monkeypatch.setitem(sys.modules, "websockets", types.SimpleNamespace(connect=fail_connect))

    await client.run()


@pytest.mark.anyio
async def test_run_claimed_job_reports_progress_and_completion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    reports: list[dict[str, object]] = []

    async def fake_report_job_state(job_id: str, **payload: object) -> None:
        reports.append({"job_id": job_id, **payload})

    def fake_run_pipeline(args, emit_progress, should_stop):
        assert args.output_dir
        assert should_stop() is False
        emit_progress("halfway there")
        return {
            "broker": args.broker,
            "output_dir": args.output_dir,
            "train_runs": [{"session_id": "demo", "run_index": 1, "device_id": "emg01"}],
            "eval_runs": [{"session_id": "demo", "run_index": 2, "device_id": "emg01"}],
            "results": [],
            "selected_family": "lda",
        }

    monkeypatch.setattr(client, "_report_job_state", fake_report_job_state)
    monkeypatch.setattr(WORKER_MODULE, "run_pipeline", fake_run_pipeline)

    await client._run_claimed_job("worker-remote:slot-01", build_job_payload())

    assert reports[0]["status"] == "running"
    assert reports[0]["message"] == "Training and validation started"
    assert any(report["message"] == "halfway there" for report in reports)
    assert reports[-1]["status"] == "completed"
    assert reports[-1]["report"]["artifact_storage"] == "ephemeral_scratch"
    assert client._active_job_stop_events == {}
    assert list(tmp_path.iterdir()) == []


@pytest.mark.anyio
async def test_run_claimed_job_tolerates_progress_report_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    reports: list[dict[str, object]] = []

    async def fake_report_job_state(job_id: str, **payload: object) -> None:
        reports.append({"job_id": job_id, **payload})

    class FakeConcurrentFuture:
        def result(self, timeout: float | None = None) -> None:
            raise TimeoutError("progress delivery timed out")

    def fake_run_coroutine_threadsafe(coro, loop):
        coro.close()
        return FakeConcurrentFuture()

    def fake_run_pipeline(args, emit_progress, should_stop):
        emit_progress("halfway there")
        return {
            "broker": args.broker,
            "output_dir": args.output_dir,
            "train_runs": [{"session_id": "demo", "run_index": 1, "device_id": "emg01"}],
            "eval_runs": [{"session_id": "demo", "run_index": 2, "device_id": "emg01"}],
            "results": [],
            "selected_family": "lda",
        }

    monkeypatch.setattr(client, "_report_job_state", fake_report_job_state)
    monkeypatch.setattr(WORKER_MODULE, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(
        WORKER_MODULE.asyncio,
        "run_coroutine_threadsafe",
        fake_run_coroutine_threadsafe,
    )

    await client._run_claimed_job("worker-remote:slot-01", build_job_payload())

    assert reports[0]["status"] == "running"
    assert reports[-1]["status"] == "completed"
    assert not any(report["status"] == "failed" for report in reports)
    assert client._active_job_stop_events == {}


@pytest.mark.anyio
async def test_run_claimed_job_reports_cancelled_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    reports: list[dict[str, object]] = []

    async def fake_report_job_state(job_id: str, **payload: object) -> None:
        reports.append({"job_id": job_id, **payload})

    def fake_run_pipeline(args, emit_progress, should_stop):
        assert should_stop() is True
        raise PipelineCancelledError("cancelled")

    monkeypatch.setattr(client, "_report_job_state", fake_report_job_state)
    monkeypatch.setattr(WORKER_MODULE, "run_pipeline", fake_run_pipeline)

    await client._run_claimed_job(
        "worker-remote:slot-01",
        build_job_payload(status="cancelling", stop_requested=True),
    )

    assert reports[0]["status"] == "running"
    assert reports[-1]["status"] == "cancelled"
    assert reports[-1]["message"] == "Job cancelled during pipeline execution"
    assert client._active_job_stop_events == {}


@pytest.mark.anyio
async def test_report_job_state_defers_terminal_update_on_connection_loss(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    client._shutdown_event.set()

    async def fake_request(payload: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("connection closed")

    monkeypatch.setattr(client, "_request", fake_request)

    await client._report_job_state(
        "job-1",
        status="failed",
        message="connection lost",
        error="connection lost",
    )

    assert client._deferred_terminal_reports["job-1"]["status"] == "failed"
    assert client._deferred_terminal_reports["job-1"]["error"] == "connection lost"


@pytest.mark.anyio
async def test_report_job_state_drops_running_update_while_disconnected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    client._shutdown_event.set()

    async def fake_request(payload: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("connection closed")

    monkeypatch.setattr(client, "_request", fake_request)

    await client._report_job_state(
        "job-1",
        status="running",
        message="still working",
    )

    assert client._deferred_terminal_reports == {}


@pytest.mark.anyio
async def test_report_job_state_stops_job_when_control_plane_already_marked_terminal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    stop_event = WORKER_MODULE.threading.Event()
    client._active_job_stop_events["job-1"] = stop_event

    async def fake_request(payload: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("job job-1 is already terminal in status failed")

    monkeypatch.setattr(client, "_request", fake_request)

    await client._report_job_state(
        "job-1",
        status="running",
        message="still working",
    )

    assert stop_event.is_set() is True


@pytest.mark.anyio
async def test_sync_active_job_statuses_sets_stop_event_for_cancelling_job(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    stop_event = WORKER_MODULE.threading.Event()
    client._active_job_stop_events["job-1"] = stop_event

    async def fake_request(payload: dict[str, object]) -> dict[str, object]:
        assert payload["action"] == "get_job_status"
        assert payload["worker_id"] == "worker-remote"
        assert payload["job_id"] == "job-1"
        return {
            "type": "job_status",
            "job_id": "job-1",
            "status": "cancelling",
            "stop_requested": True,
            "message": "stop requested remotely",
        }

    monkeypatch.setattr(client, "_request", fake_request)

    await client._sync_active_job_statuses()

    assert stop_event.is_set() is True


@pytest.mark.anyio
async def test_sync_active_job_statuses_reasserts_running_job_after_reconnect(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    stop_event = WORKER_MODULE.threading.Event()
    client._active_job_stop_events["job-1"] = stop_event
    sent_reports: list[dict[str, object]] = []

    async def fake_request(payload: dict[str, object]) -> dict[str, object]:
        return {
            "type": "job_status",
            "job_id": "job-1",
            "status": "running",
            "stop_requested": False,
            "message": "Recovered after control-plane restart; awaiting external worker state",
        }

    async def fake_report_job_state(job_id: str, **payload: object) -> None:
        sent_reports.append({"job_id": job_id, **payload})

    monkeypatch.setattr(client, "_request", fake_request)
    monkeypatch.setattr(client, "_report_job_state", fake_report_job_state)

    await client._sync_active_job_statuses()

    assert stop_event.is_set() is False
    assert sent_reports == [
        {
            "job_id": "job-1",
            "status": "running",
            "message": "External worker reconnected and confirmed active execution",
        }
    ]


@pytest.mark.anyio
async def test_sync_active_job_statuses_stops_job_when_control_plane_lost_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    stop_event = WORKER_MODULE.threading.Event()
    client._active_job_stop_events["job-1"] = stop_event

    async def fake_request(payload: dict[str, object]) -> dict[str, object]:
        return {
            "type": "job_status",
            "job_id": "job-1",
            "status": "failed",
            "message": "Control plane no longer has state for this worker job",
            "error": "job state missing after reconnect",
        }

    monkeypatch.setattr(client, "_request", fake_request)

    await client._sync_active_job_statuses()

    assert stop_event.is_set() is True


@pytest.mark.anyio
async def test_flush_deferred_terminal_reports_replays_saved_payloads(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    sent_payloads: list[dict[str, object]] = []
    client._deferred_terminal_reports["job-1"] = {
        "action": "report_worker_job_state",
        "worker_id": "worker-remote",
        "job_id": "job-1",
        "status": "cancelled",
        "message": "cancelled after disconnect",
    }

    async def fake_request(payload: dict[str, object]) -> dict[str, object]:
        sent_payloads.append(payload)
        return {"type": "job_status", "job_id": payload["job_id"]}

    monkeypatch.setattr(client, "_request", fake_request)

    await client._flush_deferred_terminal_reports()

    assert [payload["job_id"] for payload in sent_payloads] == ["job-1"]
    assert client._deferred_terminal_reports == {}


@pytest.mark.anyio
async def test_register_worker_sends_stable_worker_session_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    sent_payloads: list[dict[str, object]] = []

    async def fake_request(payload: dict[str, object]) -> dict[str, object]:
        sent_payloads.append(payload)
        return {"type": "workers"}

    monkeypatch.setattr(client, "_request", fake_request)

    await client._register_worker()

    assert sent_payloads[0]["action"] == "register_worker"
    assert sent_payloads[0]["worker_id"] == "worker-remote"
    assert sent_payloads[0]["worker_session_id"] == client._worker_session_id


@pytest.mark.anyio
async def test_set_worker_status_sends_stable_worker_session_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    sent_payloads: list[dict[str, object]] = []
    client._ws = object()

    async def fake_request(payload: dict[str, object]) -> dict[str, object]:
        sent_payloads.append(payload)
        return {"type": "workers"}

    monkeypatch.setattr(client, "_request", fake_request)

    await client._set_worker_status("draining")

    assert sent_payloads[0]["action"] == "worker_heartbeat"
    assert sent_payloads[0]["status"] == "draining"
    assert sent_payloads[0]["worker_session_id"] == client._worker_session_id


@pytest.mark.anyio
async def test_sync_slots_sends_stable_worker_session_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    sent_payloads: list[dict[str, object]] = []

    async def fake_request(payload: dict[str, object]) -> dict[str, object]:
        sent_payloads.append(payload)
        return {"type": "thread_slots"}

    monkeypatch.setattr(client, "_request", fake_request)

    await client._sync_slots()

    assert sent_payloads[0]["action"] == "sync_worker_slots"
    assert sent_payloads[0]["worker_session_id"] == client._worker_session_id


@pytest.mark.anyio
async def test_report_job_state_sends_stable_worker_session_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    sent_payloads: list[dict[str, object]] = []

    async def fake_request(payload: dict[str, object]) -> dict[str, object]:
        sent_payloads.append(payload)
        return {"type": "job_status", "job_id": payload["job_id"]}

    monkeypatch.setattr(client, "_request", fake_request)

    await client._report_job_state(
        "job-1",
        status="running",
        message="progress",
    )

    assert sent_payloads[0]["action"] == "report_worker_job_state"
    assert sent_payloads[0]["worker_session_id"] == client._worker_session_id


@pytest.mark.anyio
async def test_claim_loop_sends_stable_worker_session_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    sent_payloads: list[dict[str, object]] = []

    async def fake_request(payload: dict[str, object]) -> dict[str, object]:
        sent_payloads.append(payload)
        client._shutdown_event.set()
        return {"type": "worker_job_claim", "job": None}

    monkeypatch.setattr(client, "_request", fake_request)

    await client._claim_loop()

    assert sent_payloads[0]["action"] == "claim_worker_slot_job"
    assert sent_payloads[0]["worker_session_id"] == client._worker_session_id


@pytest.mark.anyio
async def test_close_connected_session_skips_unregister_while_active_work_remains(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    sent_payloads: list[dict[str, object]] = []
    blocker = asyncio.Event()

    async def fake_request(payload: dict[str, object]) -> dict[str, object]:
        sent_payloads.append(payload)
        return {"type": "ack"}

    async def wait_forever() -> None:
        await blocker.wait()

    monkeypatch.setattr(client, "_request", fake_request)
    client._receiver_task = asyncio.create_task(wait_forever())
    client._heartbeat_task = asyncio.create_task(wait_forever())
    active_task = asyncio.create_task(wait_forever())
    client._active_slot_tasks["worker-remote:slot-01"] = active_task

    try:
        await client._close_connected_session()
        assert sent_payloads == []
        assert active_task.cancelled() is False
    finally:
        active_task.cancel()
        blocker.set()
        await asyncio.gather(active_task, return_exceptions=True)


@pytest.mark.anyio
async def test_close_connected_session_unregisters_when_idle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    sent_payloads: list[dict[str, object]] = []
    blocker = asyncio.Event()

    async def fake_request(payload: dict[str, object]) -> dict[str, object]:
        sent_payloads.append(payload)
        return {"type": "ack"}

    async def wait_forever() -> None:
        await blocker.wait()

    monkeypatch.setattr(client, "_request", fake_request)
    client._receiver_task = asyncio.create_task(wait_forever())
    client._heartbeat_task = asyncio.create_task(wait_forever())

    await client._close_connected_session()

    assert sent_payloads == [
        {
            "action": "unregister_worker",
            "worker_id": "worker-remote",
            "worker_session_id": client._worker_session_id,
        }
    ]


@pytest.mark.anyio
async def test_drain_active_jobs_marks_worker_draining_and_finishes_cleanly(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    reported_statuses: list[str] = []

    async def fake_set_worker_status(status: str) -> None:
        reported_statuses.append(status)

    async def complete_soon() -> None:
        await asyncio.sleep(0)

    monkeypatch.setattr(client, "_set_worker_status", fake_set_worker_status)
    task = asyncio.create_task(complete_soon())
    client._active_slot_tasks["worker-remote:slot-01"] = task

    drained_cleanly = await client._drain_active_jobs(timeout_s=0.1)

    assert drained_cleanly is True
    assert reported_statuses == ["draining"]
    assert client._abandoned_inflight_work is False
    assert client._active_slot_tasks == {}


@pytest.mark.anyio
async def test_drain_active_jobs_marks_worker_offline_after_forced_cancel(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = MlWorkerClient(build_worker_args(tmp_path))
    reported_statuses: list[str] = []
    blocker = asyncio.Event()

    async def fake_set_worker_status(status: str) -> None:
        reported_statuses.append(status)

    async def wait_forever() -> None:
        await blocker.wait()

    monkeypatch.setattr(client, "_set_worker_status", fake_set_worker_status)
    task = asyncio.create_task(wait_forever())
    client._active_slot_tasks["worker-remote:slot-01"] = task

    drained_cleanly = await client._drain_active_jobs(timeout_s=0.0)

    assert drained_cleanly is False
    assert reported_statuses == ["draining", "offline"]
    assert client._abandoned_inflight_work is True
    assert client._has_reconnectable_inflight_work() is True
    blocker.set()
    await asyncio.gather(task, return_exceptions=True)
