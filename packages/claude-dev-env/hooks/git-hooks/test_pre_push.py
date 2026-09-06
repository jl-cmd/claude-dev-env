from __future__ import annotations

import io
import sys
from pathlib import Path

import pre_push
import pytest
from test_native_hook_support import (
    configure_remote_url_rewrite,
    create_bare_repository,
    create_native_repository,
    install_native_hook,
    read_git_head,
    run_git,
    run_native_git_action,
)


def test_main_keeps_protected_destination_as_advisory(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(
            "refs/heads/topic "
            + "a" * 40
            + " refs/heads/main "
            + "b" * 40
            + "\n"
        ),
    )

    exit_code = pre_push.main()

    captured_streams = capsys.readouterr()
    assert exit_code == 0
    assert "push would send local branch 'topic'" in captured_streams.err


def test_native_git_push_to_local_bare_remote_allows_missing_setup(tmp_path: Path) -> None:
    repository_path = create_native_repository(
        tmp_path,
        "repo",
        "https://github.com/JonEcho/python-automation.git",
        initial_branch="main",
    )
    run_git(repository_path, "add", "README.md")
    run_git(repository_path, "commit", "--quiet", "-m", "initial")

    bare_repository_path = create_bare_repository(tmp_path)
    configure_remote_url_rewrite(
        repository_path,
        bare_repository_path,
        "https://github.com/JonEcho/python-automation.git",
    )
    hook_directory = tmp_path / "hooks"
    install_native_hook(repository_path, hook_directory, "pre-push", "pre_push")

    completed_push = run_native_git_action(repository_path, "push", "origin", "main")

    pushed_head = read_git_head(bare_repository_path, "refs/heads/main")
    current_head = read_git_head(repository_path, "HEAD")
    combined_output = completed_push.stdout + completed_push.stderr
    assert completed_push.returncode == 0
    assert pushed_head == current_head
    assert "LOCAL VERIFICATION ADVISORY" in combined_output
    assert "Event: push" in combined_output
    assert f"Current SHA: {current_head}" in combined_output
    assert "State: pending" in combined_output
