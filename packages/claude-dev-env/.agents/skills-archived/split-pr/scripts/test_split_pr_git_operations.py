"""Git materialization stages only slice paths and restores on failure."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from split_pr_git_operations import (
    assert_clean_worktree,
    materialize_slice_commit,
    read_head_sha,
    restore_repository_state,
)
from split_pr_process_runner import CapturedProcessOutcome


class _FakeRunner:
    def __init__(self) -> None:
        self.all_calls: list[list[str]] = []
        self.head_sha = "base111"
        self.fail_commit = False
        self.is_dirty = False

    def __call__(
        self, all_command: list[str], working_directory: str
    ) -> CapturedProcessOutcome:
        self.all_calls.append(list(all_command))
        all_git_args = all_command[1:]
        if all_git_args[:2] == ["status", "--porcelain"]:
            text = " M dirty.py\n" if self.is_dirty else ""
            return CapturedProcessOutcome(0, text, "")
        if all_git_args[:2] == ["rev-parse", "HEAD"]:
            return CapturedProcessOutcome(0, self.head_sha + "\n", "")
        if all_git_args[:1] == ["add"]:
            return CapturedProcessOutcome(0, "", "")
        if all_git_args[:1] == ["commit"]:
            if self.fail_commit:
                return CapturedProcessOutcome(1, "", "commit failed")
            self.head_sha = "commit222"
            return CapturedProcessOutcome(0, "", "")
        if all_git_args[:1] == ["checkout"]:
            self.head_sha = all_git_args[-1]
            return CapturedProcessOutcome(0, "", "")
        if all_git_args[:1] == ["restore"]:
            return CapturedProcessOutcome(0, "", "")
        if all_git_args[:1] == ["clean"]:
            return CapturedProcessOutcome(0, "", "")
        return CapturedProcessOutcome(1, "", f"unexpected {all_command}")


def test_read_head_sha_returns_current_head(tmp_path: Path) -> None:
    runner = _FakeRunner()
    assert read_head_sha(tmp_path, run=runner) == "base111"


def test_assert_clean_worktree_passes_on_empty_status(tmp_path: Path) -> None:
    runner = _FakeRunner()
    assert_clean_worktree(tmp_path, run=runner)


def test_restore_repository_state_checks_out_target(tmp_path: Path) -> None:
    runner = _FakeRunner()
    restore_repository_state(tmp_path, "restore999", run=runner)
    assert runner.head_sha == "restore999"


def test_materialize_slice_commit_stages_only_slice_paths(tmp_path: Path) -> None:
    runner = _FakeRunner()
    commit_record = materialize_slice_commit(
        repository_path=tmp_path,
        all_slice_paths=["a.py", "b.py"],
        commit_message="chore: slice",
        expected_base_sha="base111",
        run=runner,
    )
    assert commit_record["commit_sha"] == "commit222"
    assert commit_record["all_paths"] == ["a.py", "b.py"]
    add_call = next(each for each in runner.all_calls if each[1] == "add")
    assert add_call[3:] == ["a.py", "b.py"]


def test_materialize_slice_commit_refuses_dirty_tree(tmp_path: Path) -> None:
    runner = _FakeRunner()
    runner.is_dirty = True
    with pytest.raises(RuntimeError, match="dirty"):
        materialize_slice_commit(
            repository_path=tmp_path,
            all_slice_paths=["a.py"],
            commit_message="chore: x",
            expected_base_sha="base111",
            run=runner,
        )


def test_materialize_slice_commit_restores_on_commit_failure(tmp_path: Path) -> None:
    runner = _FakeRunner()
    runner.fail_commit = True
    with pytest.raises(RuntimeError, match="commit failed"):
        materialize_slice_commit(
            repository_path=tmp_path,
            all_slice_paths=["a.py"],
            commit_message="chore: x",
            expected_base_sha="base111",
            run=runner,
        )
    assert any(each[1] == "checkout" for each in runner.all_calls)
    assert runner.head_sha == "base111"


def test_materialize_slice_commit_rejects_base_mismatch(tmp_path: Path) -> None:
    runner = _FakeRunner()
    with pytest.raises(RuntimeError, match="does not match"):
        materialize_slice_commit(
            repository_path=tmp_path,
            all_slice_paths=["a.py"],
            commit_message="chore: x",
            expected_base_sha="other999",
            run=runner,
        )
