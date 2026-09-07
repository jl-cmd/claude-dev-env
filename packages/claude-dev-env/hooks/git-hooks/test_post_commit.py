from __future__ import annotations

from pathlib import Path

import post_commit
import pytest
from test_native_hook_support import (
    create_native_repository,
    install_native_hook,
    read_git_head,
    run_git,
    run_native_git_action,
)


def test_main_always_returns_zero_when_notice_reports_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(post_commit, "verification_notice_main", lambda *args, **kwargs: 1)

    exit_code = post_commit.main()

    assert exit_code == 0


def test_native_git_commit_notice_reports_the_new_head(tmp_path: Path) -> None:
    repository_path = create_native_repository(
        tmp_path,
        "repo",
        "https://github.com/JonEcho/python-automation.git",
    )
    hook_directory = tmp_path / "hooks"
    install_native_hook(repository_path, hook_directory, "post-commit", "post_commit")
    run_git(repository_path, "add", "README.md")

    completed_commit = run_native_git_action(repository_path, "commit", "-m", "initial")

    current_head = read_git_head(repository_path, "HEAD")
    combined_output = completed_commit.stdout + completed_commit.stderr
    assert completed_commit.returncode == 0
    assert "Event: commit" in combined_output
    assert f"Current SHA: {current_head}" in combined_output
    assert "State: pending" in combined_output
