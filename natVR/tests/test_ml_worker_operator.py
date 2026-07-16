from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

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

OPERATOR_PATH = (
    Path(__file__).resolve().parents[2]
    / "libnatkit"
    / "scripts"
    / "natkit_ml_worker_operator.py"
)
OPERATOR_SPEC = importlib.util.spec_from_file_location(
    "natkit_ml_worker_operator",
    OPERATOR_PATH,
)
assert OPERATOR_SPEC is not None
assert OPERATOR_SPEC.loader is not None
OPERATOR_MODULE = importlib.util.module_from_spec(OPERATOR_SPEC)
sys.modules[OPERATOR_SPEC.name] = OPERATOR_MODULE
OPERATOR_SPEC.loader.exec_module(OPERATOR_MODULE)

DEFAULT_DRAIN_WAIT_TIMEOUT_S = CONTROL_PLANE_MODULE.DEFAULT_DRAIN_WAIT_TIMEOUT_S
build_request_id = OPERATOR_MODULE.build_request_id
format_human_output = OPERATOR_MODULE.format_human_output
load_worker_ids_from_json_file = OPERATOR_MODULE.load_worker_ids_from_json_file
parse_args = OPERATOR_MODULE.parse_args
request_response = OPERATOR_MODULE.request_response
run_operator_command = OPERATOR_MODULE.run_operator_command
load_worker_ids_from_file = OPERATOR_MODULE.load_worker_ids_from_file
resolve_worker_ids = OPERATOR_MODULE.resolve_worker_ids
worker_summary_from_workers_message = OPERATOR_MODULE.worker_summary_from_workers_message
worker_summaries_from_workers_message = OPERATOR_MODULE.worker_summaries_from_workers_message
workers_from_workers_message = OPERATOR_MODULE.workers_from_workers_message


class FakeWebSocket:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self._responses = [json.dumps(item) for item in responses]
        self.sent_messages: list[dict[str, object]] = []

    async def send(self, raw: str) -> None:
        self.sent_messages.append(json.loads(raw))

    async def recv(self) -> str:
        if not self._responses:
            raise AssertionError("recv called without a queued fake response")
        return self._responses.pop(0)


class FakeConnect:
    def __init__(self, websocket: FakeWebSocket) -> None:
        self.websocket = websocket
        self.urls: list[str] = []

    def __call__(self, url: str):
        self.urls.append(url)
        return self

    async def __aenter__(self) -> FakeWebSocket:
        return self.websocket

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


def test_parse_args_defaults_drain_timeout() -> None:
    args = parse_args(["drain", "--worker-id", "worker-a"])

    assert args.command == "drain"
    assert args.worker_ids == ["worker-a"]
    assert args.no_wait is False
    assert args.fail_fast is False
    assert args.timeout_s == DEFAULT_DRAIN_WAIT_TIMEOUT_S


def test_parse_args_supports_list_and_status_commands() -> None:
    list_args = parse_args(["list"])
    status_args = parse_args(["status", "--worker-id", "worker-a", "--worker-id", "worker-b"])

    assert list_args.command == "list"
    assert status_args.command == "status"
    assert status_args.worker_ids == ["worker-a", "worker-b"]


def test_parse_args_supports_fail_fast_for_multi_worker_actions() -> None:
    drain_args = parse_args(["drain", "--worker-id", "worker-a", "--fail-fast"])
    resume_args = parse_args(["resume", "--worker-id", "worker-a", "--fail-fast"])

    assert drain_args.fail_fast is True
    assert resume_args.fail_fast is True


def test_parse_args_supports_workers_json_and_group_filters() -> None:
    args = parse_args(
        [
            "drain",
            "--workers-json",
            "workers.json",
            "--worker-group",
            "blue",
            "--worker-group",
            "green",
        ]
    )

    assert args.command == "drain"
    assert args.workers_json == "workers.json"
    assert args.worker_groups == ["blue", "green"]


def test_parse_args_supports_result_json_out() -> None:
    args = parse_args(
        [
            "status",
            "--result-json-out",
            "results/operator.json",
            "--worker-id",
            "worker-a",
        ]
    )

    assert args.command == "status"
    assert args.result_json_out == "results/operator.json"


def test_parse_args_supports_workers_file() -> None:
    args = parse_args(["status", "--workers-file", "workers.txt"])

    assert args.command == "status"
    assert args.workers_file == "workers.txt"


def test_load_worker_ids_from_file_ignores_blank_lines_and_comments(tmp_path: Path) -> None:
    path = tmp_path / "workers.txt"
    path.write_text(
        "\n# comment\nworker-a\n\n  worker-b  \n# other\nworker-c\n",
        encoding="utf-8",
    )

    assert load_worker_ids_from_file(path) == ["worker-a", "worker-b", "worker-c"]


def test_resolve_worker_ids_merges_cli_and_file_inputs_with_stable_dedup(tmp_path: Path) -> None:
    path = tmp_path / "workers.txt"
    path.write_text("worker-b\nworker-c\nworker-a\n", encoding="utf-8")
    args = argparse.Namespace(worker_ids=["worker-a", "worker-b", "worker-a"], workers_file=str(path))

    assert resolve_worker_ids(args) == ["worker-a", "worker-b", "worker-c"]


def test_load_worker_ids_from_json_file_accepts_list_and_manifest_shapes(tmp_path: Path) -> None:
    list_path = tmp_path / "workers-list.json"
    list_path.write_text('["worker-a", "worker-b"]\n', encoding="utf-8")
    manifest_path = tmp_path / "workers-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "workers": [
                    "worker-c",
                    {"worker_id": "worker-d"},
                ]
            }
        ),
        encoding="utf-8",
    )

    assert load_worker_ids_from_json_file(list_path) == ["worker-a", "worker-b"]
    assert load_worker_ids_from_json_file(manifest_path) == ["worker-c", "worker-d"]


def test_load_worker_ids_from_json_file_filters_object_entries_by_group(tmp_path: Path) -> None:
    path = tmp_path / "workers.json"
    path.write_text(
        json.dumps(
            {
                "workers": [
                    {"worker_id": "worker-a", "group": "blue"},
                    {"worker_id": "worker-b", "groups": ["green", "west"]},
                    {"worker_id": "worker-c", "group": "red"},
                    "worker-d",
                ]
            }
        ),
        encoding="utf-8",
    )

    assert load_worker_ids_from_json_file(path, worker_groups=["blue", "west"]) == [
        "worker-a",
        "worker-b",
    ]


def test_resolve_worker_ids_merges_cli_text_and_json_inputs_with_stable_dedup(
    tmp_path: Path,
) -> None:
    workers_file = tmp_path / "workers.txt"
    workers_file.write_text("worker-b\nworker-c\n", encoding="utf-8")
    workers_json = tmp_path / "workers.json"
    workers_json.write_text(
        json.dumps(
            {
                "workers": [
                    {"worker_id": "worker-c", "group": "blue"},
                    {"worker_id": "worker-d", "group": "blue"},
                    {"worker_id": "worker-e", "group": "red"},
                ]
            }
        ),
        encoding="utf-8",
    )
    args = argparse.Namespace(
        worker_ids=["worker-a", "worker-b"],
        workers_file=str(workers_file),
        workers_json=str(workers_json),
        worker_groups=["blue"],
    )

    assert resolve_worker_ids(args) == ["worker-a", "worker-b", "worker-c", "worker-d"]


def test_worker_summary_from_workers_message_selects_target_worker() -> None:
    worker = worker_summary_from_workers_message(
        {
            "workers": [
                {"worker_id": "worker-a", "worker_status": "online"},
                {"worker_id": "worker-b", "worker_status": "draining"},
            ]
        },
        worker_id="worker-b",
    )

    assert worker["worker_id"] == "worker-b"
    assert worker["worker_status"] == "draining"


def test_workers_from_workers_message_returns_all_worker_dicts() -> None:
    workers = workers_from_workers_message(
        {
            "workers": [
                {"worker_id": "worker-a", "worker_status": "online"},
                {"worker_id": "worker-b", "worker_status": "draining"},
            ]
        }
    )

    assert [worker["worker_id"] for worker in workers] == ["worker-a", "worker-b"]


def test_worker_summaries_from_workers_message_preserves_requested_order() -> None:
    workers = worker_summaries_from_workers_message(
        {
            "workers": [
                {"worker_id": "worker-a", "worker_status": "online"},
                {"worker_id": "worker-b", "worker_status": "draining"},
            ]
        },
        worker_ids=["worker-b", "worker-a"],
    )

    assert [worker["worker_id"] for worker in workers] == ["worker-b", "worker-a"]


def test_format_human_output_handles_drain_timeout() -> None:
    message = format_human_output(
        {
            "command": "drain",
            "waited": True,
            "worker": {
                "worker_id": "worker-a",
                "timed_out": True,
                "drain_ready": False,
                "drain_remaining_job_count": 2,
            },
        }
    )

    assert "worker-a" in message
    assert "2 active job(s) remaining" in message


def test_format_human_output_formats_list_and_status_views() -> None:
    list_message = format_human_output(
        {
            "command": "list",
            "workers": [
                {
                    "worker_id": "worker-a",
                    "worker_status": "online",
                    "assigned_job_count": 1,
                },
                {
                    "worker_id": "worker-b",
                    "worker_status": "draining",
                    "drain_ready": False,
                    "drain_remaining_job_count": 2,
                    "assigned_job_count": 2,
                },
            ],
        }
    )
    status_message = format_human_output(
        {
            "command": "status",
            "worker": {
                "worker_id": "worker-b",
                "worker_status": "draining",
                "assigned_job_count": 2,
                "drain_ready": True,
            },
        }
    )

    assert "worker-a online active=1" in list_message
    assert "worker-b draining 2 remaining active=2" in list_message
    assert status_message == "worker-b status=draining active=2 drain=ready"


def test_format_human_output_formats_multi_worker_errors() -> None:
    message = format_human_output(
        {
            "command": "resume",
            "workers": [
                {"worker_id": "worker-a", "worker_status": "online", "assigned_job_count": 0},
                {"worker_id": "worker-b", "error": "worker_id not found: worker-b"},
            ],
        }
    )

    assert "worker-a resumed with status online" in message
    assert "worker-b error=worker_id not found: worker-b" in message


@pytest.mark.anyio
async def test_run_operator_command_lists_workers() -> None:
    websocket = FakeWebSocket(
        [
            {"type": "hello", "service": "natkit-ml-control-plane"},
            {
                "type": "workers",
                "request_id": "req-list",
                "workers": [
                    {"worker_id": "worker-a", "worker_status": "online"},
                    {"worker_id": "worker-b", "worker_status": "draining"},
                ],
            },
        ]
    )
    connect = FakeConnect(websocket)
    args = argparse.Namespace(
        command="list",
        control_plane_url="ws://127.0.0.1:8786",
        json=False,
        log_level="INFO",
    )

    original = OPERATOR_MODULE.build_request_id
    OPERATOR_MODULE.build_request_id = lambda: "req-list"
    try:
        exit_code, result = await run_operator_command(args, connect_factory=connect)
    finally:
        OPERATOR_MODULE.build_request_id = original

    assert exit_code == 0
    assert [worker["worker_id"] for worker in result["workers"]] == ["worker-a", "worker-b"]
    assert websocket.sent_messages[0]["action"] == "list_workers"


@pytest.mark.anyio
async def test_run_operator_command_status_returns_target_worker() -> None:
    websocket = FakeWebSocket(
        [
            {
                "type": "workers",
                "request_id": "req-status",
                "workers": [
                    {"worker_id": "worker-a", "worker_status": "online"},
                    {"worker_id": "worker-b", "worker_status": "draining", "drain_ready": True},
                ],
            }
        ]
    )
    connect = FakeConnect(websocket)
    args = argparse.Namespace(
        command="status",
        control_plane_url="ws://127.0.0.1:8786",
        worker_ids=["worker-b"],
        json=False,
        log_level="INFO",
    )

    original = OPERATOR_MODULE.build_request_id
    OPERATOR_MODULE.build_request_id = lambda: "req-status"
    try:
        exit_code, result = await run_operator_command(args, connect_factory=connect)
    finally:
        OPERATOR_MODULE.build_request_id = original

    assert exit_code == 0
    assert result["requested_worker_ids"] == ["worker-b"]
    assert result["processed_worker_ids"] == ["worker-b"]
    assert result["worker"]["worker_id"] == "worker-b"
    assert websocket.sent_messages[0]["action"] == "list_workers"


@pytest.mark.anyio
async def test_run_operator_command_status_returns_multiple_workers() -> None:
    websocket = FakeWebSocket(
        [
            {
                "type": "workers",
                "request_id": "req-status-many",
                "workers": [
                    {"worker_id": "worker-a", "worker_status": "online"},
                    {"worker_id": "worker-b", "worker_status": "draining", "drain_ready": True},
                ],
            }
        ]
    )
    connect = FakeConnect(websocket)
    args = argparse.Namespace(
        command="status",
        control_plane_url="ws://127.0.0.1:8786",
        worker_ids=["worker-b", "worker-a"],
        json=False,
        log_level="INFO",
    )

    original = OPERATOR_MODULE.build_request_id
    OPERATOR_MODULE.build_request_id = lambda: "req-status-many"
    try:
        exit_code, result = await run_operator_command(args, connect_factory=connect)
    finally:
        OPERATOR_MODULE.build_request_id = original

    assert exit_code == 0
    assert result["requested_worker_ids"] == ["worker-b", "worker-a"]
    assert result["processed_worker_ids"] == ["worker-b", "worker-a"]
    assert [worker["worker_id"] for worker in result["workers"]] == ["worker-b", "worker-a"]


@pytest.mark.anyio
async def test_run_operator_command_status_uses_workers_file(tmp_path: Path) -> None:
    path = tmp_path / "workers.txt"
    path.write_text("worker-b\nworker-a\n", encoding="utf-8")
    websocket = FakeWebSocket(
        [
            {
                "type": "workers",
                "request_id": "req-status-file",
                "workers": [
                    {"worker_id": "worker-a", "worker_status": "online"},
                    {"worker_id": "worker-b", "worker_status": "draining", "drain_ready": True},
                ],
            }
        ]
    )
    connect = FakeConnect(websocket)
    args = argparse.Namespace(
        command="status",
        control_plane_url="ws://127.0.0.1:8786",
        worker_ids=[],
        workers_file=str(path),
        json=False,
        log_level="INFO",
    )

    original = OPERATOR_MODULE.build_request_id
    OPERATOR_MODULE.build_request_id = lambda: "req-status-file"
    try:
        exit_code, result = await run_operator_command(args, connect_factory=connect)
    finally:
        OPERATOR_MODULE.build_request_id = original

    assert exit_code == 0
    assert result["requested_worker_ids"] == ["worker-b", "worker-a"]
    assert result["processed_worker_ids"] == ["worker-b", "worker-a"]
    assert [worker["worker_id"] for worker in result["workers"]] == ["worker-b", "worker-a"]


@pytest.mark.anyio
async def test_run_operator_command_status_uses_workers_json_manifest_with_group_filter(
    tmp_path: Path,
) -> None:
    path = tmp_path / "workers.json"
    path.write_text(
        json.dumps(
            {
                "workers": [
                    {"worker_id": "worker-b", "group": "blue"},
                    {"worker_id": "worker-a", "group": "green"},
                    {"worker_id": "worker-c", "group": "blue"},
                ]
            }
        ),
        encoding="utf-8",
    )
    websocket = FakeWebSocket(
        [
            {
                "type": "workers",
                "request_id": "req-status-json",
                "workers": [
                    {"worker_id": "worker-a", "worker_status": "online"},
                    {"worker_id": "worker-b", "worker_status": "draining", "drain_ready": True},
                    {"worker_id": "worker-c", "worker_status": "online"},
                ],
            }
        ]
    )
    connect = FakeConnect(websocket)
    args = argparse.Namespace(
        command="status",
        control_plane_url="ws://127.0.0.1:8786",
        worker_ids=[],
        workers_file=None,
        workers_json=str(path),
        worker_groups=["blue"],
        json=False,
        log_level="INFO",
    )

    original = OPERATOR_MODULE.build_request_id
    OPERATOR_MODULE.build_request_id = lambda: "req-status-json"
    try:
        exit_code, result = await run_operator_command(args, connect_factory=connect)
    finally:
        OPERATOR_MODULE.build_request_id = original

    assert exit_code == 0
    assert result["requested_worker_ids"] == ["worker-b", "worker-c"]
    assert result["processed_worker_ids"] == ["worker-b", "worker-c"]
    assert [worker["worker_id"] for worker in result["workers"]] == ["worker-b", "worker-c"]


@pytest.mark.anyio
async def test_request_response_ignores_unrelated_broadcasts() -> None:
    websocket = FakeWebSocket(
        [
            {"type": "workers", "workers": [{"worker_id": "worker-a"}]},
            {"type": "workers", "request_id": "other", "workers": []},
            {
                "type": "worker_drain_status",
                "request_id": "req-1",
                "worker_id": "worker-a",
                "drain_ready": True,
                "timed_out": False,
            },
        ]
    )

    monkeypatched_ids = iter(["req-1"])
    original = OPERATOR_MODULE.build_request_id
    OPERATOR_MODULE.build_request_id = lambda: next(monkeypatched_ids)
    try:
        response = await request_response(
            websocket,
            {"action": "wait_worker_drain_ready", "worker_id": "worker-a"},
            expected_types={"worker_drain_status"},
        )
    finally:
        OPERATOR_MODULE.build_request_id = original

    assert websocket.sent_messages[0]["action"] == "wait_worker_drain_ready"
    assert response["worker_id"] == "worker-a"
    assert response["drain_ready"] is True


@pytest.mark.anyio
async def test_run_operator_command_drains_and_waits_until_ready() -> None:
    websocket = FakeWebSocket(
        [
            {
                "type": "workers",
                "request_id": "req-update",
                "workers": [{"worker_id": "worker-a", "worker_status": "draining"}],
            },
            {"type": "workers", "workers": [{"worker_id": "worker-a"}]},
            {
                "type": "worker_drain_status",
                "request_id": "req-wait",
                "worker_id": "worker-a",
                "worker_status": "draining",
                "drain_ready": True,
                "drain_remaining_job_count": 0,
                "timed_out": False,
            },
        ]
    )
    connect = FakeConnect(websocket)
    args = argparse.Namespace(
        command="drain",
        control_plane_url="ws://127.0.0.1:8786",
        worker_ids=["worker-a"],
        no_wait=False,
        timeout_s=5.0,
        json=False,
        log_level="INFO",
    )

    monkeypatched_ids = iter(["req-update", "req-wait"])
    original = OPERATOR_MODULE.build_request_id
    OPERATOR_MODULE.build_request_id = lambda: next(monkeypatched_ids)
    try:
        exit_code, result = await run_operator_command(args, connect_factory=connect)
    finally:
        OPERATOR_MODULE.build_request_id = original

    assert connect.urls == ["ws://127.0.0.1:8786"]
    assert exit_code == 0
    assert result["requested_worker_ids"] == ["worker-a"]
    assert result["processed_worker_ids"] == ["worker-a"]
    assert result["worker"]["drain_ready"] is True
    assert websocket.sent_messages[0]["action"] == "update_worker_status"
    assert websocket.sent_messages[1]["action"] == "wait_worker_drain_ready"


@pytest.mark.anyio
async def test_run_operator_command_drains_multiple_workers_with_timeout_aggregate_exit() -> None:
    websocket = FakeWebSocket(
        [
            {
                "type": "workers",
                "request_id": "req-update-a",
                "workers": [{"worker_id": "worker-a", "worker_status": "draining"}],
            },
            {
                "type": "worker_drain_status",
                "request_id": "req-wait-a",
                "worker_id": "worker-a",
                "worker_status": "draining",
                "drain_ready": True,
                "drain_remaining_job_count": 0,
                "timed_out": False,
            },
            {
                "type": "workers",
                "request_id": "req-update-b",
                "workers": [{"worker_id": "worker-b", "worker_status": "draining"}],
            },
            {
                "type": "worker_drain_status",
                "request_id": "req-wait-b",
                "worker_id": "worker-b",
                "worker_status": "draining",
                "drain_ready": False,
                "drain_remaining_job_count": 2,
                "timed_out": True,
            },
        ]
    )
    connect = FakeConnect(websocket)
    args = argparse.Namespace(
        command="drain",
        control_plane_url="ws://127.0.0.1:8786",
        worker_ids=["worker-a", "worker-b"],
        no_wait=False,
        timeout_s=5.0,
        fail_fast=False,
        json=False,
        log_level="INFO",
    )

    monkeypatched_ids = iter(["req-update-a", "req-wait-a", "req-update-b", "req-wait-b"])
    original = OPERATOR_MODULE.build_request_id
    OPERATOR_MODULE.build_request_id = lambda: next(monkeypatched_ids)
    try:
        exit_code, result = await run_operator_command(args, connect_factory=connect)
    finally:
        OPERATOR_MODULE.build_request_id = original

    assert exit_code == 2
    assert result["requested_worker_ids"] == ["worker-a", "worker-b"]
    assert result["processed_worker_ids"] == ["worker-a", "worker-b"]
    assert [worker["worker_id"] for worker in result["workers"]] == ["worker-a", "worker-b"]
    assert result["workers"][1]["timed_out"] is True


@pytest.mark.anyio
async def test_run_operator_command_resume_multiple_workers_returns_error_exit_when_any_fail() -> None:
    websocket = FakeWebSocket(
        [
            {
                "type": "workers",
                "request_id": "req-resume-a",
                "workers": [{"worker_id": "worker-a", "worker_status": "online"}],
            },
            {
                "type": "error",
                "request_id": "req-resume-b",
                "message": "worker_id not found: worker-b",
            },
        ]
    )
    connect = FakeConnect(websocket)
    args = argparse.Namespace(
        command="resume",
        control_plane_url="ws://127.0.0.1:8786",
        worker_ids=["worker-a", "worker-b"],
        fail_fast=False,
        json=False,
        log_level="INFO",
    )

    monkeypatched_ids = iter(["req-resume-a", "req-resume-b"])
    original = OPERATOR_MODULE.build_request_id
    OPERATOR_MODULE.build_request_id = lambda: next(monkeypatched_ids)
    try:
        exit_code, result = await run_operator_command(args, connect_factory=connect)
    finally:
        OPERATOR_MODULE.build_request_id = original

    assert exit_code == 1
    assert result["requested_worker_ids"] == ["worker-a", "worker-b"]
    assert result["processed_worker_ids"] == ["worker-a", "worker-b"]
    assert result["workers"][0]["worker_id"] == "worker-a"
    assert result["workers"][1]["worker_id"] == "worker-b"
    assert "error" in result["workers"][1]


@pytest.mark.anyio
async def test_run_operator_command_resume_fail_fast_stops_after_first_error() -> None:
    websocket = FakeWebSocket(
        [
            {
                "type": "error",
                "request_id": "req-resume-a",
                "message": "worker_id not found: worker-a",
            }
        ]
    )
    connect = FakeConnect(websocket)
    args = argparse.Namespace(
        command="resume",
        control_plane_url="ws://127.0.0.1:8786",
        worker_ids=["worker-a", "worker-b", "worker-c"],
        fail_fast=True,
        json=False,
        log_level="INFO",
    )

    monkeypatched_ids = iter(["req-resume-a", "req-resume-b", "req-resume-c"])
    original = OPERATOR_MODULE.build_request_id
    OPERATOR_MODULE.build_request_id = lambda: next(monkeypatched_ids)
    try:
        exit_code, result = await run_operator_command(args, connect_factory=connect)
    finally:
        OPERATOR_MODULE.build_request_id = original

    assert exit_code == 1
    assert result["requested_worker_ids"] == ["worker-a", "worker-b", "worker-c"]
    assert result["processed_worker_ids"] == ["worker-a"]
    assert result["worker"]["worker_id"] == "worker-a"
    assert "error" in result["worker"]
    assert len(websocket.sent_messages) == 1


@pytest.mark.anyio
async def test_run_operator_command_drain_fail_fast_stops_after_first_error() -> None:
    websocket = FakeWebSocket(
        [
            {
                "type": "workers",
                "request_id": "req-update-a",
                "workers": [{"worker_id": "worker-a", "worker_status": "draining"}],
            },
            {
                "type": "worker_drain_status",
                "request_id": "req-wait-a",
                "worker_id": "worker-a",
                "worker_status": "draining",
                "drain_ready": True,
                "drain_remaining_job_count": 0,
                "timed_out": False,
            },
            {
                "type": "error",
                "request_id": "req-update-b",
                "message": "worker_id not found: worker-b",
            },
        ]
    )
    connect = FakeConnect(websocket)
    args = argparse.Namespace(
        command="drain",
        control_plane_url="ws://127.0.0.1:8786",
        worker_ids=["worker-a", "worker-b", "worker-c"],
        no_wait=False,
        timeout_s=5.0,
        fail_fast=True,
        json=False,
        log_level="INFO",
    )

    monkeypatched_ids = iter(
        ["req-update-a", "req-wait-a", "req-update-b", "req-wait-b", "req-update-c"]
    )
    original = OPERATOR_MODULE.build_request_id
    OPERATOR_MODULE.build_request_id = lambda: next(monkeypatched_ids)
    try:
        exit_code, result = await run_operator_command(args, connect_factory=connect)
    finally:
        OPERATOR_MODULE.build_request_id = original

    assert exit_code == 1
    assert result["requested_worker_ids"] == ["worker-a", "worker-b", "worker-c"]
    assert result["processed_worker_ids"] == ["worker-a", "worker-b"]
    assert [worker["worker_id"] for worker in result["workers"]] == ["worker-a", "worker-b"]
    assert len(websocket.sent_messages) == 3


@pytest.mark.anyio
async def test_run_operator_command_resume_sets_online_status() -> None:
    websocket = FakeWebSocket(
        [
            {
                "type": "workers",
                "request_id": "req-resume",
                "workers": [{"worker_id": "worker-a", "worker_status": "online"}],
            }
        ]
    )
    connect = FakeConnect(websocket)
    args = argparse.Namespace(
        command="resume",
        control_plane_url="ws://127.0.0.1:8786",
        worker_ids=["worker-a"],
        json=False,
        log_level="INFO",
    )

    original = OPERATOR_MODULE.build_request_id
    OPERATOR_MODULE.build_request_id = lambda: "req-resume"
    try:
        exit_code, result = await run_operator_command(args, connect_factory=connect)
    finally:
        OPERATOR_MODULE.build_request_id = original

    assert exit_code == 0
    assert result["requested_worker_ids"] == ["worker-a"]
    assert result["processed_worker_ids"] == ["worker-a"]
    assert result["worker"]["worker_status"] == "online"
    assert websocket.sent_messages[0]["status"] == "online"


def test_main_writes_result_json_out_for_success(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    result_path = tmp_path / "nested" / "worker-result.json"

    async def fake_run_operator_command(args, *, connect_factory=None):
        return 2, {
            "command": "drain",
            "requested_worker_ids": ["worker-a"],
            "processed_worker_ids": ["worker-a"],
            "waited": True,
            "worker": {
                "worker_id": "worker-a",
                "timed_out": True,
                "drain_ready": False,
                "drain_remaining_job_count": 1,
            },
        }

    original = OPERATOR_MODULE.run_operator_command
    OPERATOR_MODULE.run_operator_command = fake_run_operator_command
    try:
        exit_code = OPERATOR_MODULE.main(
            [
                "drain",
                "--result-json-out",
                str(result_path),
                "--worker-id",
                "worker-a",
            ]
        )
    finally:
        OPERATOR_MODULE.run_operator_command = original

    captured = capsys.readouterr()
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert "timeout" in captured.out
    assert payload["ok"] is False
    assert payload["exit_code"] == 2
    assert payload["command"] == "drain"
    assert payload["requested_worker_ids"] == ["worker-a"]
    assert payload["processed_worker_ids"] == ["worker-a"]
    assert payload["worker"]["timed_out"] is True


def test_main_writes_result_json_out_for_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    result_path = tmp_path / "worker-result.json"

    async def fake_run_operator_command(args, *, connect_factory=None):
        raise RuntimeError("control-plane unavailable")

    original = OPERATOR_MODULE.run_operator_command
    OPERATOR_MODULE.run_operator_command = fake_run_operator_command
    try:
        exit_code = OPERATOR_MODULE.main(
            [
                "status",
                "--result-json-out",
                str(result_path),
                "--worker-id",
                "worker-a",
            ]
        )
    finally:
        OPERATOR_MODULE.run_operator_command = original

    captured = capsys.readouterr()
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert "control-plane unavailable" in captured.out
    assert payload == {
        "ok": False,
        "exit_code": 1,
        "error": "control-plane unavailable",
    }
