from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import submodule_sync
from submodule_sync_constants.config.constants import (
    GH_COMMAND_TIMEOUT_SECONDS,
    GIT_COMMAND_TIMEOUT_SECONDS,
)


def _build_git_environment() -> dict[str, str]:
    return {
        each_name: each_content
        for each_name, each_content in os.environ.items()
        if not each_name.upper().startswith("GIT_")
    }


def _run_fixture_git(
    repository_path: Path,
    *all_arguments: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *all_arguments],
        cwd=repository_path,
        check=False,
        capture_output=True,
        text=True,
        env=_build_git_environment(),
        timeout=GIT_COMMAND_TIMEOUT_SECONDS,
    )


def _require_fixture_git(repository_path: Path, *all_arguments: str) -> str:
    completed_process = _run_fixture_git(repository_path, *all_arguments)
    assert completed_process.returncode == 0, completed_process.stderr
    return completed_process.stdout.strip()


def _configure_fixture_identity(repository_path: Path) -> None:
    _require_fixture_git(repository_path, "config", "user.name", "Fixture User")
    _require_fixture_git(
        repository_path,
        "config",
        "user.email",
        "fixture@example.invalid",
    )
    _require_fixture_git(repository_path, "config", "commit.gpgsign", "false")


def _initialize_fixture_repository(repository_path: Path) -> None:
    repository_path.mkdir(parents=True)
    _require_fixture_git(repository_path, "init", "-b", "main")
    _configure_fixture_identity(repository_path)


def _create_submodule_fixture(tmp_path: Path) -> tuple[Path, Path]:
    source_repository = tmp_path / "source-repository"
    parent_repository = tmp_path / "parent-repository"
    _initialize_fixture_repository(source_repository)
    (source_repository / "README.md").write_text("source\n", encoding="utf-8")
    _require_fixture_git(source_repository, "add", "README.md")
    _require_fixture_git(source_repository, "commit", "-m", "Create source")
    _initialize_fixture_repository(parent_repository)
    (parent_repository / "README.md").write_text("parent\n", encoding="utf-8")
    _require_fixture_git(parent_repository, "add", "README.md")
    _require_fixture_git(parent_repository, "commit", "-m", "Create parent")
    _require_fixture_git(
        parent_repository,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(source_repository),
        "nested/sub[module]",
    )
    _require_fixture_git(parent_repository, "commit", "-am", "Add submodule")
    submodule_repository = parent_repository / "nested" / "sub[module]"
    _configure_fixture_identity(submodule_repository)
    return parent_repository, submodule_repository


def _commit_child_change(submodule_repository: Path) -> str:
    (submodule_repository / "change.txt").write_text("change\n", encoding="utf-8")
    _require_fixture_git(submodule_repository, "add", "change.txt")
    _require_fixture_git(submodule_repository, "commit", "-m", "Record child change")
    return _require_fixture_git(submodule_repository, "rev-parse", "HEAD")


def _assert_parent_pointer_commit(
    parent_repository: Path,
    child_commit_hash: str,
) -> None:
    recorded_pointer = _require_fixture_git(
        parent_repository,
        "rev-parse",
        "HEAD:nested/sub[module]",
    )
    changed_path = _require_fixture_git(
        parent_repository,
        "diff",
        "HEAD^",
        "HEAD",
        "--name-only",
    )
    parent_commit_body = _require_fixture_git(
        parent_repository,
        "log",
        "-1",
        "--pretty=%B",
    )
    assert recorded_pointer == child_commit_hash
    assert changed_path == "nested/sub[module]"
    assert "Submodule commit: Record child change" in parent_commit_body
    assert "Co-Authored-By" not in parent_commit_body


def test_sync_updates_bracketed_pointer_and_preserves_staged_path(
    tmp_path: Path,
) -> None:
    parent_repository, submodule_repository = _create_submodule_fixture(tmp_path)
    staged_note_path = parent_repository / "staged-note.txt"
    staged_note_path.write_text("keep staged\n", encoding="utf-8")
    _require_fixture_git(parent_repository, "add", "staged-note.txt")
    child_commit_hash = _commit_child_change(submodule_repository)

    sync_report = submodule_sync.sync_repository(submodule_repository)

    assert sync_report.status is submodule_sync.SyncStatus.UPDATED
    assert sync_report.commit == child_commit_hash
    assert sync_report.submodule_path == "nested/sub[module]"
    assert (
        _require_fixture_git(parent_repository, "status", "--short")
        == "A  staged-note.txt"
    )
    _assert_parent_pointer_commit(parent_repository, child_commit_hash)


def test_second_sync_is_unchanged_without_new_commit(tmp_path: Path) -> None:
    parent_repository, submodule_repository = _create_submodule_fixture(tmp_path)
    _commit_child_change(submodule_repository)

    first_report = submodule_sync.sync_repository(submodule_repository)
    parent_commit = _require_fixture_git(parent_repository, "rev-parse", "HEAD")
    second_report = submodule_sync.sync_repository(submodule_repository)

    assert first_report.status is submodule_sync.SyncStatus.UPDATED
    assert second_report.status is submodule_sync.SyncStatus.UNCHANGED
    assert second_report.parent_commit == parent_commit
    assert _require_fixture_git(parent_repository, "rev-parse", "HEAD") == parent_commit


def test_standalone_repository_is_a_noop(tmp_path: Path) -> None:
    standalone_repository = tmp_path / "standalone"
    _initialize_fixture_repository(standalone_repository)
    (standalone_repository / "note.txt").write_text("unchanged\n", encoding="utf-8")
    _require_fixture_git(standalone_repository, "add", "note.txt")
    before_status = _require_fixture_git(standalone_repository, "status", "--short")

    sync_report = submodule_sync.sync_repository(standalone_repository)

    assert sync_report.status is submodule_sync.SyncStatus.NOT_SUBMODULE
    assert sync_report.repository == standalone_repository.resolve().as_posix()
    assert (
        _require_fixture_git(standalone_repository, "status", "--short")
        == before_status
    )


@pytest.mark.parametrize(
    ("failed_git_operation", "failure_exit_code"),
    [("add", 1), ("diff", 2), ("commit", 1)],
)
def test_git_failures_return_error_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failed_git_operation: str,
    failure_exit_code: int,
) -> None:
    _, submodule_repository = _create_submodule_fixture(tmp_path)
    _commit_child_change(submodule_repository)
    original_execute_git = submodule_sync._execute_git

    def fail_selected_operation(
        all_arguments: tuple[str, ...],
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        if all_arguments[0] == failed_git_operation:
            return subprocess.CompletedProcess(
                ["git", *all_arguments],
                failure_exit_code,
                "",
                f"fatal: fixture {failed_git_operation} failure",
            )
        return original_execute_git(all_arguments, cwd)

    monkeypatch.setattr(submodule_sync, "_execute_git", fail_selected_operation)
    sync_report = submodule_sync.sync_repository(submodule_repository)

    assert sync_report.status is submodule_sync.SyncStatus.ERROR
    assert sync_report.diagnostic == f"fatal: fixture {failed_git_operation} failure"


def test_inherited_git_dir_does_not_redirect_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unrelated_repository = tmp_path / "unrelated"
    _initialize_fixture_repository(unrelated_repository)
    parent_repository, submodule_repository = _create_submodule_fixture(tmp_path)
    child_commit_hash = _commit_child_change(submodule_repository)
    monkeypatch.setenv("GIT_DIR", str(unrelated_repository / ".git"))

    sync_report = submodule_sync.sync_repository(submodule_repository)

    assert sync_report.status is submodule_sync.SyncStatus.UPDATED
    recorded_pointer = _require_fixture_git(
        parent_repository,
        "rev-parse",
        "HEAD:nested/sub[module]",
    )
    assert recorded_pointer == child_commit_hash


def test_pull_request_lookup_returns_url_on_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed_process = subprocess.CompletedProcess(
        ["gh"],
        0,
        "https://github.com/example/repo/pull/1\n",
        "",
    )

    def return_completed_process(
        *all_arguments: object,
        **all_keyword_arguments: object,
    ) -> subprocess.CompletedProcess[str]:
        return completed_process

    monkeypatch.setattr(submodule_sync.subprocess, "run", return_completed_process)

    assert submodule_sync.lookup_pull_request_url(tmp_path) == (
        "https://github.com/example/repo/pull/1"
    )


@pytest.mark.parametrize(
    "completed_process",
    [
        subprocess.CompletedProcess(["gh"], 1, "", "no pull request"),
        subprocess.CompletedProcess(["gh"], 1, "", "auth failed"),
        subprocess.CompletedProcess(["gh"], 0, "", ""),
    ],
)
def test_pull_request_lookup_soft_failures_return_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    completed_process: subprocess.CompletedProcess[str],
) -> None:
    def return_completed_process(
        *all_arguments: object,
        **all_keyword_arguments: object,
    ) -> subprocess.CompletedProcess[str]:
        return completed_process

    monkeypatch.setattr(submodule_sync.subprocess, "run", return_completed_process)

    assert submodule_sync.lookup_pull_request_url(tmp_path) is None


@pytest.mark.parametrize(
    "lookup_exception",
    [
        FileNotFoundError(),
        subprocess.TimeoutExpired("gh", GH_COMMAND_TIMEOUT_SECONDS),
    ],
)
def test_pull_request_lookup_unavailable_returns_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    lookup_exception: Exception,
) -> None:
    def raise_lookup_exception(
        *all_arguments: object,
        **all_keyword_arguments: object,
    ) -> None:
        raise lookup_exception

    monkeypatch.setattr(submodule_sync.subprocess, "run", raise_lookup_exception)

    assert submodule_sync.lookup_pull_request_url(tmp_path) is None
