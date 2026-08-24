"""Production-path tests for pytest-Django and Playwright preflight selection."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_BLOCKING_DIRECTORY = Path(__file__).resolve().parent
_DISPATCHER_PATH = _BLOCKING_DIRECTORY / "bash_pre_tool_use_dispatcher.py"
if str(_BLOCKING_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_BLOCKING_DIRECTORY))

from test_hook_subprocess_support import (  # noqa: E402
    build_bash_payload,
    read_hook_permission_decision,
    run_hook_as_subprocess,
)


def _run_bash_dispatch(
    command: str, project_root: Path
) -> subprocess.CompletedProcess[str]:
    return run_hook_as_subprocess(
        hook_script_path=_DISPATCHER_PATH,
        payload_text=build_bash_payload(command),
        working_directory=project_root,
        home_directory=project_root,
        environment_updates_by_name={"PWD": str(project_root)},
    )


def _create_django_project_fixture(tmp_path: Path) -> Path:
    project_root = tmp_path / "django-project"
    project_root.mkdir()
    (project_root / "manage.py").write_text(
        "import sys\n\nif __name__ == '__main__':\n    sys.exit(0)\n",
        encoding="utf-8",
    )
    return project_root


def test_dispatcher_selects_pytest_django_changed_test(tmp_path: Path) -> None:
    project_root = _create_django_project_fixture(tmp_path)

    command = "python -m pytest tests/test_models.py"
    completed_process = _run_bash_dispatch(command, project_root)

    assert completed_process.returncode == 0, completed_process.stderr
    decision, reason = read_hook_permission_decision(completed_process.stdout)
    assert decision == "deny"
    assert "No database file (db.sqlite3)" in reason


def test_dispatcher_ignores_unrecognized_django_test_runner(tmp_path: Path) -> None:
    project_root = _create_django_project_fixture(tmp_path)

    command = "python -m unittest tests/test_models.py"
    completed_process = _run_bash_dispatch(command, project_root)

    assert completed_process.returncode == 0, completed_process.stderr
    assert completed_process.stdout == ""


def test_dispatcher_selects_playwright_changed_spec(tmp_path: Path) -> None:
    command = "npx playwright test tests/account.spec.ts --base-url http://127.0.0.1:1"
    completed_process = _run_bash_dispatch(command, tmp_path)

    assert completed_process.returncode == 0, completed_process.stderr
    decision, reason = read_hook_permission_decision(completed_process.stdout)
    assert decision == "deny"
    assert "Server at http://127.0.0.1:1 is unreachable" in reason


def test_dispatcher_ignores_non_playwright_test_runner(tmp_path: Path) -> None:
    command = "node tests/account.spec.ts"
    completed_process = _run_bash_dispatch(command, tmp_path)

    assert completed_process.returncode == 0, completed_process.stderr
    assert completed_process.stdout == ""
