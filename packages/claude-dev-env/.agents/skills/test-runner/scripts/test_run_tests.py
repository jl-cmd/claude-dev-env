"""Focused behavior tests for the explicit test runner."""

from __future__ import annotations

import importlib
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

run_tests = importlib.import_module("run_tests")

FRONTEND_COMMANDS = [
    ["ps", "aux"],
    ["npm", "run", "build"],
    ["python", "manage.py", "collectstatic", "--noinput"],
    [
        "curl",
        "-s",
        "-o",
        "/dev/null",
        "-w",
        "%{http_code}",
        "--max-time",
        "2",
        "http://localhost:3000",
    ],
    ["playwright", "test"],
]


def _create_django_project(project_root: Path, *, has_database: bool) -> None:
    project_root.mkdir()
    (project_root / "manage.py").write_text(
        "import sys\n\nif __name__ == '__main__':\n    sys.exit(0)\n",
        encoding="utf-8",
    )
    if has_database:
        (project_root / "db.sqlite3").write_bytes(b"database")


def _completed_process(
    all_arguments: list[str],
    return_code: int = 0,
    stdout_text: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=all_arguments,
        returncode=return_code,
        stdout=stdout_text,
        stderr="",
    )


def _build_recording_process(
    all_calls: list[tuple[list[str], dict[str, object]]],
) -> Callable[..., subprocess.CompletedProcess[str]]:
    def run_process(
        all_arguments: list[str],
        **keyword_arguments: object,
    ) -> subprocess.CompletedProcess[str]:
        all_calls.append((all_arguments, keyword_arguments))
        stdout_text = "200" if all_arguments[0] == "curl" else ""
        return _completed_process(all_arguments, stdout_text=stdout_text)

    return run_process


def test_select_runner_recognizes_supported_forms() -> None:
    assert run_tests.select_runner(["pytest", "tests"]).name == "pytest"
    assert run_tests.select_runner(["python", "-m", "pytest"]).name == "pytest"
    assert run_tests.select_runner(["npx", "playwright", "test"]).is_playwright


def test_extract_target_url_reads_explicit_base_url() -> None:
    assert (
        run_tests.extract_target_url(
            ["playwright", "test", "--base-url", "http://127.0.0.1:9000"], True
        )
        == "http://127.0.0.1:9000"
    )


def test_run_preflight_skips_plain_pytest_without_django(
    tmp_path: Path,
) -> None:
    selected_runner = run_tests.select_runner(["python", "-m", "pytest"])
    assert (
        run_tests.run_preflight(selected_runner, tmp_path, ["python", "-m", "pytest"])
        is None
    )


def test_run_child_process_returns_child_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child_process = _completed_process(["pytest"], return_code=6)
    monkeypatch.setattr(
        run_tests.subprocess, "run", lambda *_args, **_kwargs: child_process
    )
    assert run_tests.run_child_process(["pytest"], tmp_path) == 6


def test_main_runs_plain_pytest_without_django_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child_process = _completed_process(["python", "-m", "pytest", "tests"], 7)
    all_calls: list[dict[str, object]] = []

    def run_child(
        all_arguments: list[str],
        **keyword_arguments: object,
    ) -> subprocess.CompletedProcess[str]:
        all_calls.append({"arguments": all_arguments, **keyword_arguments})
        return child_process

    monkeypatch.setattr(run_tests.subprocess, "run", run_child)
    exit_code = run_tests.main(
        ["--project", str(tmp_path), "--", "python", "-m", "pytest", "tests"]
    )

    assert exit_code == 7
    assert all_calls == [
        {
            "arguments": ["python", "-m", "pytest", "tests"],
            "cwd": tmp_path.resolve(),
            "check": False,
        }
    ]


def test_missing_django_database_stops_before_child_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "django-project"
    _create_django_project(project_root, has_database=False)
    all_calls: list[list[str]] = []

    def record_launch(all_arguments: list[str], **_keyword_arguments: object) -> None:
        all_calls.append(all_arguments)

    monkeypatch.setattr(run_tests.subprocess, "run", record_launch)
    exit_code = run_tests.main(
        ["--project", str(project_root), "--", "python", "-m", "pytest"]
    )

    assert exit_code != 0
    assert all_calls == []


def test_django_pytest_passes_server_check_and_returns_child_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "django-project"
    _create_django_project(project_root, has_database=True)
    all_calls: list[tuple[list[str], dict[str, object]]] = []

    monkeypatch.setattr(
        run_tests.subprocess, "run", _build_recording_process(all_calls)
    )
    exit_code = run_tests.main(
        ["--project", str(project_root), "--", "python", "-m", "pytest", "tests"]
    )

    assert exit_code == 0
    assert all_calls[-1][0] == ["python", "-m", "pytest", "tests"]


def test_playwright_server_failure_stops_before_child_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "manage.py").write_text("", encoding="utf-8")
    all_calls: list[list[str]] = []

    def run_process(
        all_arguments: list[str],
        **_keyword_arguments: object,
    ) -> subprocess.CompletedProcess[str]:
        all_calls.append(all_arguments)
        return _completed_process(all_arguments, stdout_text="000")

    monkeypatch.setattr(run_tests.subprocess, "run", run_process)
    exit_code = run_tests.main(
        [
            "--project",
            str(tmp_path),
            "--",
            "npx",
            "playwright",
            "test",
            "--base-url",
            "http://127.0.0.1:1",
        ]
    )

    assert exit_code != 0
    assert [each_call[0] for each_call in all_calls] == ["ps", "curl"]


def test_playwright_missing_test_database_flag_stops_before_health_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "manage.py").write_text("", encoding="utf-8")
    process_listing = "python manage.py runserver 8000\n"
    all_calls: list[list[str]] = []

    def run_process(
        all_arguments: list[str],
        **_keyword_arguments: object,
    ) -> subprocess.CompletedProcess[str]:
        all_calls.append(all_arguments)
        return _completed_process(all_arguments, stdout_text=process_listing)

    monkeypatch.setattr(run_tests.subprocess, "run", run_process)
    exit_code = run_tests.main(
        [
            "--project",
            str(tmp_path),
            "--",
            "playwright",
            "test",
            "--base-url",
            "http://localhost:8000",
        ]
    )

    assert exit_code != 0
    assert [each_call[0] for each_call in all_calls] == ["ps"]


def test_playwright_builds_frontend_and_collects_static_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "django-project"
    _create_django_project(project_root, has_database=True)
    (project_root / "frontend").mkdir()
    all_calls: list[tuple[list[str], dict[str, object]]] = []
    monkeypatch.setattr(run_tests, "check_runserver_port_conflicts", lambda *_: None)
    monkeypatch.setattr(
        run_tests.subprocess, "run", _build_recording_process(all_calls)
    )

    exit_code = run_tests.main(
        ["--project", str(project_root), "--", "playwright", "test"]
    )

    assert exit_code == 0
    assert [each_call[0] for each_call in all_calls] == FRONTEND_COMMANDS
    assert all_calls[1][1]["cwd"] == project_root / "frontend"
    assert all_calls[2][1]["cwd"] == project_root.resolve()


def test_invalid_runner_does_not_launch_a_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_calls: list[list[str]] = []

    def record_launch(all_arguments: list[str], **_keyword_arguments: object) -> None:
        all_calls.append(all_arguments)

    monkeypatch.setattr(run_tests.subprocess, "run", record_launch)
    exit_code = run_tests.main(
        ["--project", str(tmp_path), "--", "python", "-m", "unittest"]
    )

    assert exit_code == 2
    assert all_calls == []
