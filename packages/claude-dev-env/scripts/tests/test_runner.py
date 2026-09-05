"""Behavior tests for repository-check orchestration."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TESTS_DIRECTORY = Path(__file__).resolve().parent
if str(_TESTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIRECTORY))

from repository_checks.config.constants import (
    FAILED_CHECK_EXIT_CODE,
    FINDINGS_EXIT_CODE,
)
from repository_policy_test_support import (
    commit_tracked_files,
    initialize_repository,
    run_policy,
    seed_clean_repository,
    write_text,
)


def test_should_fail_closed_when_tracked_paths_cannot_be_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = seed_clean_repository(tmp_path / "repo")

    def fail_tracked_paths(_repository_root: Path) -> tuple[str, ...]:
        raise OSError("git ls-files failed")

    monkeypatch.setattr(
        "repository_checks.tracked_tree.tracked_relative_paths", fail_tracked_paths
    )
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == FAILED_CHECK_EXIT_CODE
    assert "error: rule failed:" in stdout_text


def test_should_emit_stable_sorted_findings(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    write_text(
        repository_root / "zeta" / "CLAUDE.md",
        "# zeta\n\n| File | Role |\n|---|---|\n| `missing_zeta.py` | Missing |\n",
    )
    write_text(
        repository_root / "alpha" / "CLAUDE.md",
        "# alpha\n\n| File | Role |\n|---|---|\n| `missing_alpha.py` | Missing |\n",
    )
    commit_tracked_files(repository_root)
    first_exit_code, first_stdout, _first_stderr = run_policy(repository_root)
    _second_exit_code, second_stdout, _second_stderr = run_policy(repository_root)
    assert first_exit_code == FINDINGS_EXIT_CODE
    assert first_stdout == second_stdout
    assert first_stdout.index("alpha/CLAUDE.md") < first_stdout.index("zeta/CLAUDE.md")
