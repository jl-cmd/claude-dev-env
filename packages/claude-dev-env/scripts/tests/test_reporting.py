"""Behavior tests for repository-check report rendering."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
_TESTS_DIRECTORY = Path(__file__).resolve().parent
if str(_SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIRECTORY))
if str(_TESTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIRECTORY))

from repository_checks.models import RepositoryCheckReport, RepositoryFinding
from repository_checks.reporting import render_report
from repository_policy_test_support import (
    commit_tracked_files,
    initialize_repository,
    run_policy,
    write_text,
)


def test_should_render_findings_and_failed_checks_in_report_order() -> None:
    report = RepositoryCheckReport(
        (RepositoryFinding("check", "relative/file.py", "message"),),
        ("failed-check",),
    )
    assert render_report(report) == (
        "check: relative/file.py: message\nerror: rule failed: failed-check\n"
    )


def test_should_render_an_empty_clean_report() -> None:
    assert render_report(RepositoryCheckReport((), ())) == ""


def test_should_print_repository_relative_paths_only(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    write_text(
        repository_root / "notes" / "CLAUDE.md",
        "# notes\n\n"
        "| File | Role |\n"
        "|---|---|\n"
        "| `absent_helper.py` | Missing helper |\n",
    )
    commit_tracked_files(repository_root)
    _exit_code, stdout_text, stderr_text = run_policy(repository_root)
    absolute_root_text = str(repository_root.resolve())
    assert absolute_root_text not in stdout_text
    assert absolute_root_text not in stderr_text
    assert "notes/CLAUDE.md" in stdout_text
