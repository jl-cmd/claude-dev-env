"""Regression tests for set-level task validation."""

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from test_validate_protocol import SCHEMA_PATH, valid_record
from validate_protocol import ProtocolValidationError
from validate_run import main, validate_run


def test_validate_run_accepts_one_record_per_commit() -> None:
    task_record = valid_record()
    validate_run([task_record], {"a1b2c3d"}, SCHEMA_PATH, {})


def test_validate_run_accepts_matching_explicit_mapping() -> None:
    task_record = valid_record()
    validate_run(
        [task_record],
        {"a1b2c3d"},
        SCHEMA_PATH,
        {"task-3": "a1b2c3d"},
    )


@pytest.mark.parametrize(
    "explicit_mapping",
    [
        {"wrong-task": "a1b2c3d"},
        {"task-3": "deadbeef"},
    ],
)
def test_validate_run_rejects_mismatched_explicit_mapping(
    explicit_mapping: dict[str, str],
) -> None:
    with pytest.raises(ProtocolValidationError, match="explicit task mappings"):
        validate_run([valid_record()], {"a1b2c3d"}, SCHEMA_PATH, explicit_mapping)


def test_validate_run_rejects_duplicate_commits_in_explicit_mapping() -> None:
    first_record = valid_record()
    second_record = valid_record()
    second_record["task_identity"] = "task-4"
    second_record["commit"] = "deadbeef"
    with pytest.raises(ProtocolValidationError, match="unique commits"):
        validate_run(
            [first_record, second_record],
            {"a1b2c3d"},
            SCHEMA_PATH,
            {"task-1": "a1b2c3d", "task-4": "a1b2c3d"},
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda record: record.update(task_identity="task-3"),
        lambda record: record.update(commit="outside"),
    ],
)
def test_validate_run_rejects_invalid_commit_or_identity(
    mutation: Callable[[dict[str, object]], None],
) -> None:
    first_record = valid_record()
    second_record = valid_record()
    second_record["task_identity"] = "task-4"
    mutation(second_record)
    with pytest.raises(ProtocolValidationError):
        validate_run(
            [first_record, second_record], {"a1b2c3d", "deadbeef"}, SCHEMA_PATH, {}
        )


def test_validate_run_rejects_count_mismatch_without_mapping() -> None:
    with pytest.raises(ProtocolValidationError):
        validate_run([valid_record()], {"a1b2c3d", "deadbeef"}, SCHEMA_PATH, {})


def test_main_rejects_surface_mismatch_when_worktree_is_selected(
    tmp_path: Path,
) -> None:
    worktree_path = tmp_path / "worktree"
    worktree_path.mkdir()
    subprocess.run(
        ["git", "init"], cwd=worktree_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=worktree_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Protocol Test"],
        cwd=worktree_path,
        check=True,
    )
    tracked_file = worktree_path / "validator.py"
    tracked_file.write_text("validated\n", encoding="utf-8")
    subprocess.run(["git", "add", "validator.py"], cwd=worktree_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "validated"],
        cwd=worktree_path,
        check=True,
        capture_output=True,
    )
    commit_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=worktree_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    task_record = valid_record()
    task_record["commit"] = commit_hash
    task_record["allowed_files"] = ["validator.py"]
    for each_field_name in (
        "review_record",
        "repair_record",
        "reverification_record",
        "verification_record",
    ):
        nested_record = task_record[each_field_name]
        assert isinstance(nested_record, dict)
        nested_record["surface_hash"] = "0" * 64
    record_path = tmp_path / "records.json"
    record_path.write_text(json.dumps([task_record]), encoding="utf-8")

    exit_code = main(
        [
            "validate_run.py",
            str(record_path),
            "--commits",
            commit_hash,
            str(worktree_path),
        ]
    )

    assert exit_code == 2
