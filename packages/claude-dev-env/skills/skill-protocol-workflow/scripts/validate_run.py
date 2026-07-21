"""Validate a complete task-record set against an explicit Git commit set."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from config.constants import (
    COMMIT_RANGE_SEPARATOR,
    EXIT_CODE_INVALID_SET,
    EXIT_CODE_VALID_SET,
    JSON_ENCODING,
    RUN_ARGUMENT_COUNT_REQUIRED,
    RUN_ARGUMENT_COUNT_WITH_WORKTREE,
    SET_VALIDATION_PASSED,
)
from validate_protocol import ProtocolValidationError, validate_record


def _load_record_list(record_path: Path) -> list[Mapping[str, object]]:
    try:
        parsed_records = json.loads(record_path.read_text(encoding=JSON_ENCODING))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolValidationError("task-record set is not valid JSON") from error
    if not isinstance(parsed_records, list) or any(
        not isinstance(each_record, dict) for each_record in parsed_records
    ):
        raise ProtocolValidationError("task-record set must be a JSON list of objects")
    return parsed_records


def _git_commits(worktree: Path, commit_range: str) -> set[str]:
    try:
        completed = subprocess.run(
            ["git", "rev-list", "--reverse", commit_range],
            cwd=worktree,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ProtocolValidationError("cannot read the requested commit set") from error
    return {each_commit for each_commit in completed.stdout.splitlines() if each_commit}


def validate_run(
    all_task_records: Sequence[Mapping[str, object]],
    all_commit_hashes: set[str],
    schema_path: Path,
    all_explicit_mapping: Mapping[str, str],
) -> None:
    """Validate task identity uniqueness and one-to-one commit coverage.

    Args:
        all_task_records: Task records to validate.
        all_commit_hashes: Commits that the record set must cover.
        schema_path: Path to the task-record schema JSON file.
        all_explicit_mapping: Task-to-commit mapping; an empty mapping means
            records must match commits by count and commit field.

    Returns:
        None.

    Raises:
        ProtocolValidationError: If task identity, commit coverage, or record
            schema validation fails.
    """
    task_ids = [each_record.get("task_identity") for each_record in all_task_records]
    commits = [each_record.get("commit") for each_record in all_task_records]
    if any(not isinstance(each_task_id, str) for each_task_id in task_ids):
        raise ProtocolValidationError("every task record needs a task_identity")
    if len(task_ids) != len(set(task_ids)):
        raise ProtocolValidationError("task identities must be unique")
    if any(not isinstance(each_commit, str) for each_commit in commits):
        raise ProtocolValidationError("every task record needs a commit")
    if not all_explicit_mapping and len(all_task_records) != len(all_commit_hashes):
        raise ProtocolValidationError("task and commit counts differ without an explicit mapping")
    if all_explicit_mapping and len(all_explicit_mapping) != len(set(all_explicit_mapping.values())):
        raise ProtocolValidationError("explicit task mappings must reference unique commits")
    if all_explicit_mapping and set(all_explicit_mapping) != set(task_ids):
        raise ProtocolValidationError("explicit task mappings must reference every task identity")
    if all_explicit_mapping and any(
        all_explicit_mapping[each_task_id] != each_commit
        for each_task_id, each_commit in zip(task_ids, commits)
    ):
        raise ProtocolValidationError("explicit task mappings must match record commits")
    mapped_commits = set(all_explicit_mapping.values()) if all_explicit_mapping else set(commits)
    if mapped_commits != all_commit_hashes:
        raise ProtocolValidationError("task records must reference every and only requested commit")
    for each_record in all_task_records:
        validate_record(each_record, schema_path)


def main(all_cli_arguments: Sequence[str]) -> int:
    """Validate a record list against a requested commit set.

    Args:
        all_cli_arguments: Program name followed by record and commit-set
            arguments, with an optional worktree path.

    Returns:
        Exit code `0` for a valid set or `2` for invalid input.

    Raises:
        No exceptions: validation failures are reported and converted to an
            invalid-set exit code.
    """
    if len(all_cli_arguments) not in {
        RUN_ARGUMENT_COUNT_REQUIRED,
        RUN_ARGUMENT_COUNT_WITH_WORKTREE,
    }:
        print("usage: validate_run.py <records.json> --base-head <BASE..HEAD> [--worktree PATH]", file=sys.stderr)
        return EXIT_CODE_INVALID_SET
    record_path = Path(all_cli_arguments[1])
    option = all_cli_arguments[2]
    commit_range = all_cli_arguments[3]
    worktree = (
        Path(all_cli_arguments[4])
        if len(all_cli_arguments) == RUN_ARGUMENT_COUNT_WITH_WORKTREE
        else Path.cwd()
    )
    try:
        all_task_records = _load_record_list(record_path)
        if len(all_cli_arguments) == RUN_ARGUMENT_COUNT_WITH_WORKTREE:
            for each_record in all_task_records:
                each_record["worktree"] = str(worktree)
        if option == "--base-head":
            if COMMIT_RANGE_SEPARATOR not in commit_range:
                raise ProtocolValidationError("base-head must be BASE..HEAD")
            all_commit_hashes = _git_commits(worktree, commit_range)
        elif option == "--commits":
            all_commit_hashes = {
                each_commit for each_commit in commit_range.split(",") if each_commit
            }
        else:
            raise ProtocolValidationError("unknown commit-set option")
        validate_run(
            all_task_records,
            all_commit_hashes,
            Path(__file__).parent.parent / "reference" / "run-record.schema.json",
            {},
        )
    except ProtocolValidationError as error:
        print(f"run validation failed: {error}", file=sys.stderr)
        return EXIT_CODE_INVALID_SET
    print(SET_VALIDATION_PASSED)
    return EXIT_CODE_VALID_SET


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
