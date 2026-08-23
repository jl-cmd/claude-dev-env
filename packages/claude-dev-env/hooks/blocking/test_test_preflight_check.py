"""Production-path tests for pytest-Django and Playwright preflight selection."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_BLOCKING_DIRECTORY = Path(__file__).resolve().parent
_DISPATCHER_PATH = _BLOCKING_DIRECTORY / "bash_pre_tool_use_dispatcher.py"


def _build_bash_payload(command: str) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


def _run_bash_dispatch(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_DISPATCHER_PATH)],
        check=False,
        input=_build_bash_payload(command),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _read_dispatch_decision(stdout_text: str) -> tuple[str, str]:
    dispatch_payload = json.loads(stdout_text)
    hook_specific_output = dispatch_payload["hookSpecificOutput"]
    return (
        hook_specific_output["permissionDecision"],
        hook_specific_output["permissionDecisionReason"],
    )


def _create_pytest_django_fixture(project_root: Path) -> None:
    (project_root / "tests").mkdir(parents=True)
    (project_root / "django_project").mkdir()
    (project_root / "manage.py").write_text(
        "import sys\n\nif __name__ == '__main__':\n    sys.exit(0)\n",
        encoding="utf-8",
    )
    (project_root / "pytest.ini").write_text(
        "[pytest]\nDJANGO_SETTINGS_MODULE = django_project.settings\n",
        encoding="utf-8",
    )
    (project_root / "django_project" / "settings.py").write_text(
        "SECRET_KEY = 'fixture'\n",
        encoding="utf-8",
    )
    (project_root / "tests" / "test_models.py").write_text(
        "import pytest\n\n@pytest.mark.django_db\ndef test_model_query():\n    assert True\n",
        encoding="utf-8",
    )


def _create_playwright_fixture(project_root: Path) -> None:
    (project_root / "tests").mkdir(parents=True)
    (project_root / "playwright.config.ts").write_text(
        "import { defineConfig } from '@playwright/test';\n"
        "export default defineConfig({ testDir: './tests' });\n",
        encoding="utf-8",
    )
    (project_root / "tests" / "account.spec.ts").write_text(
        "import { test, expect } from '@playwright/test';\n"
        "test('account page loads', async ({ page }) => {\n"
        "  await expect(page).toHaveTitle('Account');\n"
        "});\n",
        encoding="utf-8",
    )


def test_dispatcher_selects_pytest_django_changed_test(tmp_path: Path) -> None:
    project_root = tmp_path / "django-project"
    project_root.mkdir()
    _create_pytest_django_fixture(project_root)

    command = f'cd "{project_root}" && python -m pytest tests/test_models.py'
    completed_process = _run_bash_dispatch(command)

    assert completed_process.returncode == 0, completed_process.stderr
    decision, reason = _read_dispatch_decision(completed_process.stdout)
    assert decision == "deny"
    assert "No database file (db.sqlite3)" in reason


def test_dispatcher_selects_playwright_changed_spec(tmp_path: Path) -> None:
    project_root = tmp_path / "playwright-project"
    project_root.mkdir()
    _create_playwright_fixture(project_root)

    command = (
        f'cd "{project_root}" && '
        "npx playwright test tests/account.spec.ts "
        "--config playwright.config.ts --base-url http://127.0.0.1:1"
    )
    completed_process = _run_bash_dispatch(command)

    assert completed_process.returncode == 0, completed_process.stderr
    decision, reason = _read_dispatch_decision(completed_process.stdout)
    assert decision == "deny"
    assert "Server at http://127.0.0.1:1 is unreachable" in reason
