import json
import os
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).parent / "hook_format_validator.py"


def _run_hook(
    payload: dict[str, object],
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **(extra_env or {})}
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def test_simple_pattern_blocks_with_deny_payload(tmp_path: Path) -> None:
    settings_path = tmp_path / ".claude" / "settings.json"
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(settings_path),
            "new_string": "python3 ~/.claude/hooks/blocking/my-hook.py",
        },
    }

    hook_run = _run_hook(payload)

    assert hook_run.returncode == 0
    deny_payload = json.loads(hook_run.stdout)
    hook_specific_output = deny_payload["hookSpecificOutput"]
    assert hook_specific_output["hookEventName"] == "PreToolUse"
    assert hook_specific_output["permissionDecision"] == "deny"


def test_write_payload_reads_the_content_field(tmp_path: Path) -> None:
    """_resolve_content's non-MultiEdit branch reads a Write payload's "content" key."""
    settings_path = tmp_path / ".claude" / "settings.json"
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(settings_path),
            "content": "python3 ~/.claude/hooks/blocking/my-hook.py",
        },
    }

    hook_run = _run_hook(payload)

    assert hook_run.returncode == 0
    deny_payload = json.loads(hook_run.stdout)
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_second_multi_edit_new_string_is_caught(tmp_path: Path) -> None:
    """A simple-pattern hook command in the second edit of a MultiEdit is denied."""
    settings_path = tmp_path / ".claude" / "settings.json"
    payload = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": str(settings_path),
            "edits": [
                {"old_string": "a", "new_string": "b"},
                {"old_string": "c", "new_string": "python3 ~/.claude/hooks/blocking/my-hook.py"},
            ],
        },
    }

    hook_run = _run_hook(payload)

    assert hook_run.returncode == 0
    deny_payload = json.loads(hook_run.stdout)
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_clean_multi_edit_passes(tmp_path: Path) -> None:
    settings_path = tmp_path / ".claude" / "settings.json"
    payload = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": str(settings_path),
            "edits": [
                {"old_string": "a", "new_string": "b"},
                {"old_string": "c", "new_string": "node -e \"require('run-hook-wrapper')\""},
            ],
        },
    }

    hook_run = _run_hook(payload)

    assert hook_run.returncode == 0
    assert hook_run.stdout.strip() == ""


def test_block_logs_pre_tool_use_event(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    settings_path = tmp_path / ".claude" / "settings.json"
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(settings_path),
            "new_string": "python3 ~/.claude/hooks/blocking/my-hook.py",
        },
    }

    hook_run = _run_hook(
        payload,
        extra_env={"HOME": str(fake_home), "USERPROFILE": str(fake_home)},
    )

    assert hook_run.returncode == 0
    log_path = fake_home / ".claude" / "logs" / "hook-blocks.log"
    logged_record = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert logged_record["event"] == "PreToolUse"
