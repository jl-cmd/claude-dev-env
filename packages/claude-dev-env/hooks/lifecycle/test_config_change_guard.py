import json
import os
import subprocess
import sys
from pathlib import Path


HOOK_PATH = Path(__file__).parent / "config_change_guard.py"


def _run_hook(
    source: str,
    file_path: str,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    payload = {"source": source, "file_path": file_path}
    env = {**os.environ, **(extra_env or {})}
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def _make_settings_with_hook_count(hook_count: int, tmp_path: Path) -> str:
    hooks_list = [
        {"type": "command", "command": f"hook_{each_index}.py"}
        for each_index in range(hook_count)
    ]
    settings = {"hooks": {"PreToolUse": [{"hooks": hooks_list}]}}
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps(settings))
    return str(settings_file)


def test_hook_count_increase_emits_user_visible_output(tmp_path: Path) -> None:
    known_count_file = tmp_path / "known-hook-count.txt"
    known_count_file.write_text("2")
    settings_path = _make_settings_with_hook_count(5, tmp_path)

    hook_run = _run_hook(
        source="user_settings",
        file_path=settings_path,
        extra_env={"KNOWN_HOOK_COUNT_FILE": str(known_count_file)},
    )

    assert hook_run.returncode == 0
    assert hook_run.stderr.strip() == ""
    block_payload = json.loads(hook_run.stdout)
    assert block_payload["decision"] == "block"
    assert "2" in block_payload["reason"] and "5" in block_payload["reason"]
    assert block_payload["hookSpecificOutput"]["hookEventName"] == "ConfigChange"
    assert "hook" in block_payload["hookSpecificOutput"]["additionalContext"].lower()


def test_hook_count_stable_produces_no_output(tmp_path: Path) -> None:
    known_count_file = tmp_path / "known-hook-count.txt"
    known_count_file.write_text("3")
    settings_path = _make_settings_with_hook_count(3, tmp_path)

    hook_run = _run_hook(
        source="user_settings",
        file_path=settings_path,
        extra_env={"KNOWN_HOOK_COUNT_FILE": str(known_count_file)},
    )

    assert hook_run.returncode == 0
    assert hook_run.stderr.strip() == ""
    assert hook_run.stdout.strip() == ""


def test_hook_count_decrease_produces_no_output(tmp_path: Path) -> None:
    known_count_file = tmp_path / "known-hook-count.txt"
    known_count_file.write_text("5")
    settings_path = _make_settings_with_hook_count(3, tmp_path)

    hook_run = _run_hook(
        source="user_settings",
        file_path=settings_path,
        extra_env={"KNOWN_HOOK_COUNT_FILE": str(known_count_file)},
    )

    assert hook_run.returncode == 0
    assert hook_run.stderr.strip() == ""
    assert hook_run.stdout.strip() == ""


def test_hook_count_increase_blocks_on_second_invocation(tmp_path: Path) -> None:
    known_count_file = tmp_path / "known-hook-count.txt"
    known_count_file.write_text("2")
    settings_path = _make_settings_with_hook_count(5, tmp_path)
    extra_env = {"KNOWN_HOOK_COUNT_FILE": str(known_count_file)}

    first_run = _run_hook("user_settings", settings_path, extra_env)
    assert first_run.returncode == 0
    assert first_run.stdout.strip() != ""

    second_run = _run_hook("user_settings", settings_path, extra_env)
    assert second_run.returncode == 0
    assert second_run.stdout.strip() != ""


def test_non_user_settings_source_produces_no_output(tmp_path: Path) -> None:
    settings_path = _make_settings_with_hook_count(10, tmp_path)
    hook_run = _run_hook(source="system", file_path=settings_path)
    assert hook_run.returncode == 0
    assert hook_run.stderr.strip() == ""
    assert hook_run.stdout.strip() == ""
