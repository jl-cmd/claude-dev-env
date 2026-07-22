import json
import subprocess
import sys
from pathlib import Path

import pytest

from codex_capability_bridge import translate_capability


@pytest.mark.parametrize("source_surface, expected_target, capability_payload", [("TaskList", "update_plan", {"plan": []}), ("TaskCreate", "update_plan", {"name": "review", "status": "pending"}), ("TaskUpdate", "update_plan", {"name": "review", "status": "pending"}), ("Task", "multi_agent_v1__spawn_agent", {"prompt": "review"}), ("SendMessage", "multi_agent_v1__send_input", {"message": "review"}), ("TaskOutput", "multi_agent_v1__wait_agent", {"task_id": "task-1"}), ("TaskStop", "multi_agent_v1__close_agent", {"task_id": "task-1"})])
def test_maps_capability(source_surface: str, expected_target: str, capability_payload: dict[str, object]) -> None:
    translated_record = translate_capability(source_surface, capability_payload)
    assert translated_record["target"] == expected_target


def test_normalizes_alias_and_task_payload() -> None:
    translated_record = translate_capability("task_create", {"subject": "write tests", "status": "in-progress"})
    assert translated_record["payload"] == {"plan": [{"step": "write tests", "status": "in_progress"}]}


def test_rejects_bad_payload_and_schedule() -> None:
    assert translate_capability("TaskUpdate", {"name": "x", "status": "later"})["status"] == "malformed"
    assert translate_capability("ScheduleWakeup", {})["status"] == "unsupported"


def test_rejects_unknown_and_private_paths() -> None:
    assert translate_capability("NoSuchSurface", {})["status"] == "unknown"
    assert translate_capability("SendMessage", {"message": "C:\\Users\\melan\\secret"})["status"] == "rejected"


@pytest.mark.parametrize("private_path", ["C:/private/file", "\\\\server\\share\\file", "/private/file", "~/secret", "$HOME/secret", "%USERPROFILE%\\secret", "safe/../secret"])
def test_rejects_absolute_private_and_traversal_paths(private_path: str) -> None:
    assert translate_capability("SendMessage", {"message": private_path})["status"] == "rejected"


def test_validates_mapped_surface_payloads() -> None:
    assert translate_capability("spawn", {"message": "hello"})["status"] == "malformed"
    assert translate_capability("stop", {"task_id": 3})["status"] == "malformed"
    assert translate_capability("TaskList", {"plan": [{"step": "review"}]})["status"] == "malformed"


def test_translation_is_byte_identical_for_repeated_input() -> None:
    payload = {"message": "hello", "agent_id": "agent-1"}
    first_json = json.dumps(translate_capability("message", payload), sort_keys=True, separators=(",", ":"))
    second_json = json.dumps(translate_capability("message", payload), sort_keys=True, separators=(",", ":"))
    assert first_json == second_json


def test_translation_does_not_execute_payload() -> None:
    payload = {"message": "__import__('subprocess').run('whoami')"}
    translated_record = translate_capability("message", payload)
    assert translated_record["payload"] == payload


def test_translation_is_deterministic_and_cli_is_json() -> None:
    payload = {"message": "hello", "agent_id": "agent-1"}
    first_record = translate_capability("SendMessage", payload)
    second_record = translate_capability("SendMessage", payload)
    assert first_record == second_record
    script_path = Path(__file__).parents[1] / "codex_capability_bridge.py"
    cli_run = subprocess.run([sys.executable, str(script_path), "SendMessage", json.dumps(payload)], capture_output=True, text=True, check=True)
    assert json.loads(cli_run.stdout) == first_record


def test_cli_rejects_malformed_payload_with_one_json_error_record() -> None:
    script_path = Path(__file__).parents[1] / "codex_capability_bridge.py"
    cli_run = subprocess.run(
        [sys.executable, str(script_path), "SendMessage", "{"],
        capture_output=True,
        text=True,
    )
    assert cli_run.returncode != 0
    assert json.loads(cli_run.stdout) == {
        "source": "unknown",
        "status": "error",
        "error": "payload must be valid JSON",
    }
    assert cli_run.stderr == ""


def test_cli_rejects_malformed_arguments_with_one_json_error_record() -> None:
    script_path = Path(__file__).parents[1] / "codex_capability_bridge.py"
    cli_run = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
    )
    assert cli_run.returncode != 0
    assert json.loads(cli_run.stdout)["status"] == "error"
    assert cli_run.stderr == ""
