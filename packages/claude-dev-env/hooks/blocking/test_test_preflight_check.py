"""Production-path tests for pytest-Django and Playwright preflight selection."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_BLOCKING_DIRECTORY = Path(__file__).resolve().parent
_DISPATCHER_PATH = _BLOCKING_DIRECTORY / "bash_pre_tool_use_dispatcher.py"


def _build_bash_payload(command: str) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


def _run_bash_dispatch(
    command: str, working_directory: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_DISPATCHER_PATH)],
        check=False,
        input=_build_bash_payload(command),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PWD": str(working_directory)},
    )


def _read_dispatch_decision(stdout_text: str) -> tuple[str, str]:
    if not stdout_text.strip():
        return "", ""
    dispatch_payload = json.loads(stdout_text)
    hook_specific_output = dispatch_payload["hookSpecificOutput"]
    return (
        hook_specific_output["permissionDecision"],
        hook_specific_output["permissionDecisionReason"],
    )


def _create_django_project_fixture(project_root: Path) -> None:
    (project_root / "manage.py").write_text(
        "import sys\n\nif __name__ == '__main__':\n    sys.exit(0)\n",
        encoding="utf-8",
    )


def test_dispatcher_selects_pytest_django_changed_test(tmp_path: Path) -> None:
    project_root = tmp_path / "django-project"
    project_root.mkdir()
    _create_django_project_fixture(project_root)

    command = "python -m pytest tests/test_models.py"
    completed_process = _run_bash_dispatch(command, project_root)

    assert completed_process.returncode == 0, completed_process.stderr
    decision, reason = _read_dispatch_decision(completed_process.stdout)
    assert decision == "deny"
    assert "No database file (db.sqlite3)" in reason


def test_dispatcher_ignores_unrecognized_django_test_runner(tmp_path: Path) -> None:
    project_root = tmp_path / "django-project"
    project_root.mkdir()
    _create_django_project_fixture(project_root)

    command = "python -m unittest tests/test_models.py"
    completed_process = _run_bash_dispatch(command, project_root)

    assert completed_process.returncode == 0, completed_process.stderr
    assert completed_process.stdout == ""


def test_dispatcher_selects_playwright_changed_spec(tmp_path: Path) -> None:
    project_root = tmp_path / "playwright-project"
    project_root.mkdir()

    command = "npx playwright test tests/account.spec.ts --base-url http://127.0.0.1:1"
    completed_process = _run_bash_dispatch(command, project_root)

    assert completed_process.returncode == 0, completed_process.stderr
    decision, reason = _read_dispatch_decision(completed_process.stdout)
    assert decision == "deny"
    assert "Server at http://127.0.0.1:1 is unreachable" in reason


def test_dispatcher_ignores_non_playwright_test_runner(tmp_path: Path) -> None:
    project_root = tmp_path / "playwright-project"
    project_root.mkdir()

    command = "node tests/account.spec.ts"
    completed_process = _run_bash_dispatch(command, project_root)

    assert completed_process.returncode == 0, completed_process.stderr
    assert completed_process.stdout == ""
