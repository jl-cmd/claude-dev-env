"""Behavior tests for committed CLAUDE.md references."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

_TESTS_DIRECTORY = Path(__file__).resolve().parent
if str(_TESTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIRECTORY))

from repository_checks.config.constants import (
    CHECK_ID_CLAUDE_MD_ORPHANS,
    FAILED_CHECK_EXIT_CODE,
    FINDINGS_EXIT_CODE,
)
from repository_policy_test_support import (
    commit_tracked_files,
    initialize_repository,
    run_policy,
    write_text,
)


def test_should_flag_a_broken_claude_md_file_reference(tmp_path: Path) -> None:
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
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == FINDINGS_EXIT_CODE
    assert CHECK_ID_CLAUDE_MD_ORPHANS in stdout_text
    assert "notes/CLAUDE.md" in stdout_text
    assert "absent_helper.py" in stdout_text


def test_should_fail_closed_when_claude_md_walk_fails_after_first_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

    def fail_after_first_entry(_file_path: Path, _pattern: str = "*") -> Iterator[Path]:
        yield repository_root / "notes" / "CLAUDE.md"
        raise OSError("scan root unreadable")

    monkeypatch.setattr(Path, "rglob", fail_after_first_entry)
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == FAILED_CHECK_EXIT_CODE
    assert CHECK_ID_CLAUDE_MD_ORPHANS in stdout_text
    assert "error: rule failed:" in stdout_text
