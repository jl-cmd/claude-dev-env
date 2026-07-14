"""Behavioral tests for the staged_test_running parts module."""

import subprocess
from pathlib import Path

from code_rules_gate_parts import git_file_sets, staged_test_running


def _init_repository(repository_root: Path) -> None:
    def run(*arguments: str) -> None:
        subprocess.run(
            ["git", *arguments],
            cwd=str(repository_root),
            check=True,
            capture_output=True,
            env=git_file_sets.repository_environment(),
        )

    run("init", "--initial-branch=main")
    run("config", "user.email", "test@example.com")
    run("config", "user.name", "Test")
    run("config", "commit.gpgsign", "false")
    (repository_root / "seed.txt").write_text("seed\n", encoding="utf-8")
    run("add", "-A")
    run("commit", "-m", "seed")


def test_run_staged_test_files_returns_zero_when_nothing_staged(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_repository(repository_root)

    assert staged_test_running.run_staged_test_files(repository_root) == 0


def test_batched_pytest_arguments_splits_over_the_budget() -> None:
    all_batches = staged_test_running._batched_pytest_arguments(["aaaa", "bbbb", "cccc"], 10)
    assert all_batches == [["aaaa", "bbbb"], ["cccc"]]


def test_batched_pytest_arguments_keeps_oversized_argument_in_its_own_batch() -> None:
    all_batches = staged_test_running._batched_pytest_arguments(["wide_argument"], 4)
    assert all_batches == [["wide_argument"]]
