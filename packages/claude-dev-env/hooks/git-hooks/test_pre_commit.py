from __future__ import annotations

from pathlib import Path

import pre_commit
import pytest
from test_native_hook_support import (
    configure_native_repository,
    install_native_hook,
    run_native_git_action,
    run_native_hook,
)
from test_native_hook_support import run_git as run_shared_git


def test_main_always_returns_zero_when_notice_reports_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pre_commit, "verification_notice_main", lambda *args, **kwargs: 1)

    exit_code = pre_commit.main()

    assert exit_code == 0


def test_main_requests_notice_without_starting_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_notice_arguments: list[list[str]] = []

    def record_notice_arguments(all_arguments: list[str], **keyword_arguments: object) -> int:
        all_notice_arguments.append(all_arguments)
        return 0

    monkeypatch.setattr(pre_commit, "verification_notice_main", record_notice_arguments)

    assert pre_commit.main() == 0
    assert len(all_notice_arguments) == 1
    assert "--notice-only" in all_notice_arguments[0]


def test_native_git_commit_allows_missing_setup_and_prints_advisory(tmp_path: Path) -> None:
    repository_path = tmp_path / "repo with spaces Ω"
    repository_path.mkdir()
    configure_native_repository(
        repository_path,
        "https://github.com/JonEcho/python-automation.git",
    )
    hook_directory = tmp_path / "hooks"
    install_native_hook(repository_path, hook_directory, "pre-commit", "pre_commit")
    run_shared_git(repository_path, "add", "README.md")

    completed_commit = run_native_git_action(repository_path, "commit", "-m", "initial")

    current_head = run_shared_git(repository_path, "rev-parse", "HEAD").stdout.strip()
    completed_hook = run_native_hook(repository_path, "pre_commit.py")
    combined_output = completed_hook.stdout + completed_hook.stderr
    assert completed_commit.returncode == 0
    assert completed_hook.returncode == 0
    assert "LOCAL VERIFICATION ADVISORY" in combined_output
    assert f"Current SHA: {current_head}" in combined_output
    assert "State: pending" in combined_output
