"""Local slice materialization walks dependency order with restore on error."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from execute_split_slices import materialize_plan_locally
from split_pr_process_runner import CapturedProcessOutcome


class _SequenceRunner:
    def __init__(self) -> None:
        self.head = "sha0"
        self.commit_count = 0
        self.fail_on_commit_index: int | None = None

    def __call__(
        self, all_command: list[str], working_directory: str
    ) -> CapturedProcessOutcome:
        all_git_args = all_command[1:]
        if all_git_args[:2] == ["status", "--porcelain"]:
            return CapturedProcessOutcome(0, "", "")
        if all_git_args[:2] == ["rev-parse", "HEAD"]:
            return CapturedProcessOutcome(0, self.head + "\n", "")
        if all_git_args[:1] == ["add"]:
            return CapturedProcessOutcome(0, "", "")
        if all_git_args[:1] == ["commit"]:
            self.commit_count += 1
            if self.fail_on_commit_index == self.commit_count:
                return CapturedProcessOutcome(1, "", "boom")
            self.head = f"sha{self.commit_count}"
            return CapturedProcessOutcome(0, "", "")
        if all_git_args[:1] == ["checkout"]:
            self.head = all_git_args[-1]
            return CapturedProcessOutcome(0, "", "")
        if all_git_args[:1] in (["restore"], ["clean"]):
            return CapturedProcessOutcome(0, "", "")
        return CapturedProcessOutcome(1, "", f"unexpected {all_command}")


def test_materialize_plan_locally_commits_in_layer_order(tmp_path: Path) -> None:
    plan = {
        "schema_version": 1,
        "source_commit": "sha0",
        "all_changed_paths": ["a.py", "b.md"],
        "all_slices": [
            {
                "id": "02-docs",
                "title": "docs: b",
                "layer": "docs",
                "all_paths": ["b.md"],
            },
            {
                "id": "01-backend",
                "title": "feat: a",
                "layer": "backend",
                "all_paths": ["a.py"],
            },
        ],
    }
    runner = _SequenceRunner()
    all_commit_records = materialize_plan_locally(tmp_path, plan, run=runner)
    assert [each["commit_sha"] for each in all_commit_records] == ["sha1", "sha2"]
    assert all_commit_records[0]["all_paths"] == ["a.py"]
    assert all_commit_records[1]["all_paths"] == ["b.md"]


def test_materialize_plan_locally_restores_source_on_failure(tmp_path: Path) -> None:
    plan = {
        "schema_version": 1,
        "source_commit": "sha0",
        "all_changed_paths": ["a.py", "b.py"],
        "all_slices": [
            {
                "id": "01",
                "title": "feat: a",
                "layer": "backend",
                "all_paths": ["a.py"],
            },
            {
                "id": "02",
                "title": "feat: b",
                "layer": "backend",
                "all_paths": ["b.py"],
            },
        ],
    }
    runner = _SequenceRunner()
    runner.fail_on_commit_index = 2
    with pytest.raises(RuntimeError, match="boom"):
        materialize_plan_locally(tmp_path, plan, run=runner)
    assert runner.head == "sha0"
