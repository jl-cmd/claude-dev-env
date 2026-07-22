"""Regression tests for set-level task validation."""

import json
import importlib.util
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

SCRIPT_DIRECTORY = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIRECTORY))
VALIDATE_PROTOCOL_SPEC = importlib.util.spec_from_file_location("validate_protocol", SCRIPT_DIRECTORY / "validate_protocol.py")
assert VALIDATE_PROTOCOL_SPEC is not None
assert VALIDATE_PROTOCOL_SPEC.loader is not None
VALIDATE_PROTOCOL_MODULE = importlib.util.module_from_spec(VALIDATE_PROTOCOL_SPEC)
sys.modules["validate_protocol"] = VALIDATE_PROTOCOL_MODULE
VALIDATE_PROTOCOL_SPEC.loader.exec_module(VALIDATE_PROTOCOL_MODULE)
SCHEMA_PATH = SCRIPT_DIRECTORY.parent / "reference" / "run-record.schema.json"
ProtocolValidationError = VALIDATE_PROTOCOL_MODULE.ProtocolValidationError
TEST_VALIDATE_PROTOCOL_SPEC = importlib.util.spec_from_file_location("test_validate_protocol", SCRIPT_DIRECTORY / "test_validate_protocol.py")
assert TEST_VALIDATE_PROTOCOL_SPEC is not None
assert TEST_VALIDATE_PROTOCOL_SPEC.loader is not None
TEST_VALIDATE_PROTOCOL_MODULE = importlib.util.module_from_spec(TEST_VALIDATE_PROTOCOL_SPEC)
TEST_VALIDATE_PROTOCOL_SPEC.loader.exec_module(TEST_VALIDATE_PROTOCOL_MODULE)
valid_record = TEST_VALIDATE_PROTOCOL_MODULE.valid_record
VALIDATE_RUN_SPEC = importlib.util.spec_from_file_location("validate_run", SCRIPT_DIRECTORY / "validate_run.py")
assert VALIDATE_RUN_SPEC is not None
assert VALIDATE_RUN_SPEC.loader is not None
VALIDATE_RUN_MODULE = importlib.util.module_from_spec(VALIDATE_RUN_SPEC)
VALIDATE_RUN_SPEC.loader.exec_module(VALIDATE_RUN_MODULE)
main = VALIDATE_RUN_MODULE.main
validate_run = VALIDATE_RUN_MODULE.validate_run


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


def create_committed_worktree(worktree_path: Path) -> str:
    worktree_path.mkdir()
    initialize_worktree(worktree_path)
    tracked_file = worktree_path / "validator.py"
    tracked_file.write_text("validated\n", encoding="utf-8")
    commit_file(worktree_path)
    return read_head(worktree_path)


def initialize_worktree(worktree_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=worktree_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=worktree_path, check=True)
    subprocess.run(["git", "config", "user.name", "Protocol Test"], cwd=worktree_path, check=True)


def commit_file(worktree_path: Path) -> None:
    subprocess.run(["git", "add", "validator.py"], cwd=worktree_path, check=True)
    subprocess.run(["git", "commit", "-m", "validated"], cwd=worktree_path, check=True, capture_output=True)


def read_head(worktree_path: Path) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=worktree_path, check=True, capture_output=True, text=True).stdout.strip()


def test_main_rejects_surface_mismatch_when_worktree_is_selected(
    tmp_path: Path,
) -> None:
    worktree_path = tmp_path / "worktree"
    commit_hash = create_committed_worktree(worktree_path)
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
            "--worktree",
            str(worktree_path),
        ]
    )
    assert exit_code == 2
