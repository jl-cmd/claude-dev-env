"""Focused tests for explicit test-runner preflight helpers."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

preflight_checks = importlib.import_module("preflight_checks")


def test_check_server_health_reports_unhealthy_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed_process = subprocess.CompletedProcess(
        args=["curl"], returncode=0, stdout="503", stderr=""
    )
    monkeypatch.setattr(
        preflight_checks.subprocess,
        "run",
        lambda *_arguments, **_keywords: completed_process,
    )

    assert preflight_checks.check_server_health("http://localhost:3000") == (
        "BLOCKED: Server at http://localhost:3000 is not healthy (HTTP 503). "
        "Fix the server before running tests."
    )


def test_check_django_database_requires_db_sqlite3(tmp_path: Path) -> None:
    (tmp_path / "manage.py").write_text("", encoding="utf-8")

    assert preflight_checks.check_django_database(tmp_path) == (
        f"BLOCKED: No database file (db.sqlite3) found in {tmp_path}. "
        "Run migrations before running tests."
    )


def test_extract_port_from_url_uses_explicit_or_default_port() -> None:
    assert preflight_checks.extract_port_from_url("http://localhost:9000") == "9000"
    assert preflight_checks.extract_port_from_url("http://localhost") == "8000"


def test_check_test_db_flag_requires_detected_server_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "manage.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        preflight_checks,
        "_read_process_listing",
        lambda: "python manage.py runserver",
    )

    assert preflight_checks.check_test_db_flag("http://localhost:8000", tmp_path) == (
        "BLOCKED: Django server on port 8000 is not running with --test-db. "
        "Restart with: python manage.py runserver --test-db 0.0.0.0:8000"
    )


def test_check_test_db_flag_ignores_test_database_flag_on_another_port(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "manage.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        preflight_checks,
        "_read_process_listing",
        lambda: (
            "python manage.py runserver --test-db 9000\n8000 python manage.py runserver"
        ),
    )

    assert preflight_checks.check_test_db_flag("http://localhost:8000", tmp_path) == (
        "BLOCKED: Django server on port 8000 is not running with --test-db. "
        "Restart with: python manage.py runserver --test-db 0.0.0.0:8000"
    )


def test_check_test_db_flag_skips_value_taking_runserver_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "manage.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        preflight_checks,
        "_read_process_listing",
        lambda: "python manage.py runserver --settings project.settings 8000",
    )

    assert preflight_checks.check_test_db_flag("http://localhost:8000", tmp_path) == (
        "BLOCKED: Django server on port 8000 is not running with --test-db. "
        "Restart with: python manage.py runserver --test-db 0.0.0.0:8000"
    )


def test_check_test_db_flag_accepts_value_taking_options_with_test_db(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "manage.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        preflight_checks,
        "_read_process_listing",
        lambda: "python manage.py runserver --settings project.settings --test-db 8000",
    )

    assert (
        preflight_checks.check_test_db_flag("http://localhost:8000", tmp_path) is None
    )


def test_check_runserver_port_conflicts_reports_other_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    other_project_root = tmp_path / "other-project"
    project_root.mkdir()
    other_project_root.mkdir()
    monkeypatch.setattr(
        preflight_checks,
        "_get_runserver_processes_on_port",
        lambda _port: [(1, str(project_root)), (2, str(other_project_root))],
    )

    assert (
        preflight_checks.check_runserver_port_conflicts(
            "http://localhost:8000", project_root
        )
        == f"BLOCKED: Multiple Django runserver processes are bound to port 8000 across worktrees: {other_project_root.resolve()}. Stop stale servers first."
    )


def test_build_frontend_runs_build_then_collectstatic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "manage.py").write_text("", encoding="utf-8")
    (tmp_path / "frontend").mkdir()
    all_calls: list[tuple[list[str], Path]] = []

    def run_process(
        all_arguments: list[str], **keyword_arguments: object
    ) -> subprocess.CompletedProcess[str]:
        all_calls.append((all_arguments, keyword_arguments["cwd"]))
        return subprocess.CompletedProcess(
            args=all_arguments, returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr(preflight_checks.subprocess, "run", run_process)

    assert preflight_checks.build_frontend(tmp_path) is None
    assert all_calls == [
        (["npm", "run", "build"], tmp_path / "frontend"),
        (["python", "manage.py", "collectstatic", "--noinput"], tmp_path),
    ]


def test_build_frontend_skips_collectstatic_without_manage_py(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "frontend").mkdir()
    all_calls: list[list[str]] = []

    def run_process(
        all_arguments: list[str], **_keyword_arguments: object
    ) -> subprocess.CompletedProcess[str]:
        all_calls.append(all_arguments)
        return subprocess.CompletedProcess(
            args=all_arguments, returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr(preflight_checks.subprocess, "run", run_process)

    assert preflight_checks.build_frontend(tmp_path) is None
    assert all_calls == [["npm", "run", "build"]]
