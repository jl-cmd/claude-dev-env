"""Validate one skill protocol task-run record."""

from __future__ import annotations

import json
import hashlib
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from config.constants import (
    ALL_ALLOWED_RECORD_FIELDS,
    ALL_RECORD_FIELDS,
    ALL_REPAIR_FIELDS,
    ALL_REPAIR_TEXT_FIELDS,
    ALL_REVIEW_FIELDS,
    ALL_REVIEW_TEXT_FIELDS,
    ALL_TOP_LEVEL_TEXT_FIELDS,
    ALL_SUPPORTED_SCHEMA_TYPES,
    ALL_VERIFICATION_FIELDS,
    ALLOWED_REVIEW_MODEL,
    ALLOWED_WORKER_EFFORT,
    ALLOWED_WORKER_ROLE,
    ARGUMENT_COUNT_REQUIRED,
    ARGUMENT_COUNT_WITH_WORKTREE,
    COMMIT_HASH_ERROR_TEMPLATE,
    COMMIT_HASH_PATTERN,
    EXIT_CODE_INVALID_RECORD,
    EXIT_CODE_VALID_RECORD,
    JSON_ENCODING,
    MISSING_FIELD_SEPARATOR,
    MAXIMUM_COMMIT_HASH_LENGTH,
    MINIMUM_COMMIT_HASH_LENGTH,
    PROTOCOL_VALIDATION_PASSED,
    RECORD_SCHEMA_FILENAME,
    DOCS_PLANS_PATH_PATTERN,
    FINDING_STATUS_CONFIRMED,
    FINDING_STATUS_DISMISSED,
    NATIVE_REVIEW_COMMAND,
    PASSED_EVIDENCE_PREFIX,
    REPAIR_STATUS_COMPLETE,
    REPAIR_STATUS_NOT_REQUIRED,
    SURFACE_HASH_PATTERN,
    PATH_SEPARATOR_PATTERN,
    SHA256_ALGORITHM,
)


class ProtocolValidationError(ValueError):
    """Identify a task-run record contract violation."""


def _load_schema_object(schema_path: Path) -> Mapping[str, object]:
    """Load one JSON schema object."""
    try:
        parsed_schema = json.loads(schema_path.read_text(encoding=JSON_ENCODING))
    except json.JSONDecodeError as error:
        raise ProtocolValidationError("record schema is invalid JSON") from error
    except OSError as error:
        raise ProtocolValidationError(f"cannot read record schema: {error}") from error
    if not isinstance(parsed_schema, dict):
        raise ProtocolValidationError("record schema must be a JSON object")
    return parsed_schema


def _resolve_schema_reference(
    all_schema_node: Mapping[str, object], all_schema_root: Mapping[str, object]
) -> Mapping[str, object]:
    """Resolve a local `$defs` schema reference."""
    schema_reference = all_schema_node.get("$ref")
    if schema_reference is None:
        return all_schema_node
    if not isinstance(schema_reference, str) or not schema_reference.startswith(
        "#/$defs/"
    ):
        raise ProtocolValidationError("record schema has an unsupported reference")
    definitions = all_schema_root.get("$defs")
    if not isinstance(definitions, dict):
        raise ProtocolValidationError("record schema has no definitions")
    definition_name = schema_reference.removeprefix("#/$defs/")
    definition = definitions.get(definition_name)
    if not isinstance(definition, dict):
        raise ProtocolValidationError(
            f"record schema definition is missing: {definition_name}"
        )
    return definition


def _validate_schema_node(
    candidate: object,
    all_schema_node: Mapping[str, object],
    all_schema_root: Mapping[str, object],
    field_path: str,
) -> None:
    """Validate one record value against the supported schema keywords."""
    resolved_schema = _resolve_schema_reference(all_schema_node, all_schema_root)
    if "const" in resolved_schema and candidate != resolved_schema["const"]:
        raise ProtocolValidationError(
            f"{field_path} does not match its schema constant"
        )
    schema_type = resolved_schema.get("type")
    if schema_type == "object":
        _validate_schema_object(candidate, resolved_schema, all_schema_root, field_path)
        return
    if schema_type == "array":
        _validate_schema_array(candidate, resolved_schema, all_schema_root, field_path)
        return
    if schema_type == "string":
        _validate_schema_string(candidate, resolved_schema, field_path)
        return
    if schema_type == "boolean" and not isinstance(candidate, bool):
        raise ProtocolValidationError(f"{field_path} must be a boolean")
    if schema_type not in (*ALL_SUPPORTED_SCHEMA_TYPES, None):
        raise ProtocolValidationError(f"{field_path} has an unsupported schema type")


def _validate_schema_object(
    candidate: object,
    all_schema_node: Mapping[str, object],
    all_schema_root: Mapping[str, object],
    field_path: str,
) -> None:
    """Validate an object schema node."""
    if not isinstance(candidate, dict):
        raise ProtocolValidationError(f"{field_path} must be an object")
    required_fields = all_schema_node.get("required", [])
    if not isinstance(required_fields, list):
        raise ProtocolValidationError(f"{field_path} has invalid required fields")
    for each_field_name in required_fields:
        if isinstance(each_field_name, str) and each_field_name not in candidate:
            raise ProtocolValidationError(f"{field_path} missing: {each_field_name}")
    properties = all_schema_node.get("properties", {})
    if not isinstance(properties, dict):
        raise ProtocolValidationError(f"{field_path} has invalid properties")
    if all_schema_node.get("additionalProperties") is False:
        additional_fields = sorted(
            each_field_name
            for each_field_name in candidate
            if each_field_name not in properties
        )
        if additional_fields:
            raise ProtocolValidationError(
                f"{field_path} has additional fields: "
                f"{MISSING_FIELD_SEPARATOR.join(additional_fields)}"
            )
    for each_field_name, each_schema_node in properties.items():
        if each_field_name in candidate and isinstance(each_schema_node, dict):
            _validate_schema_node(
                candidate[each_field_name],
                each_schema_node,
                all_schema_root,
                f"{field_path}.{each_field_name}",
            )


def _validate_schema_array(
    candidate: object,
    all_schema_node: Mapping[str, object],
    all_schema_root: Mapping[str, object],
    field_path: str,
) -> None:
    """Validate an array schema node."""
    if not isinstance(candidate, list):
        raise ProtocolValidationError(f"{field_path} must be an array")
    minimum_array_entries = all_schema_node.get("minItems", 0)
    if (
        isinstance(minimum_array_entries, int)
        and len(candidate) < minimum_array_entries
    ):
        raise ProtocolValidationError(
            f"{field_path} must contain at least {minimum_array_entries} items"
        )
    array_entry_schema = all_schema_node.get("items")
    if isinstance(array_entry_schema, dict):
        for each_index, each_candidate in enumerate(candidate):
            _validate_schema_node(
                each_candidate,
                array_entry_schema,
                all_schema_root,
                f"{field_path}[{each_index}]",
            )


def _validate_schema_string(
    candidate: object, all_schema_node: Mapping[str, object], field_path: str
) -> None:
    """Validate a string schema node."""
    if not isinstance(candidate, str):
        raise ProtocolValidationError(f"{field_path} must be a string")
    minimum_length = all_schema_node.get("minLength", 0)
    if isinstance(minimum_length, int) and len(candidate) < minimum_length:
        raise ProtocolValidationError(f"{field_path} must not be empty")
    pattern = all_schema_node.get("pattern")
    if isinstance(pattern, str) and re.search(pattern, candidate) is None:
        raise ProtocolValidationError(f"{field_path} does not match its schema pattern")


def _load_json_object(task_run_path: Path) -> Mapping[str, object]:
    """Load one task-run object from JSON.

    Args:
        task_run_path: JSON file containing one task-run record.

    Returns:
        The decoded task-run mapping.

    Raises:
        ProtocolValidationError: If the file cannot be read or decoded as an object.
    """
    try:
        parsed_task_run = json.loads(task_run_path.read_text(encoding=JSON_ENCODING))
    except json.JSONDecodeError as error:
        raise ProtocolValidationError("invalid JSON") from error
    except UnicodeDecodeError as error:
        raise ProtocolValidationError("invalid UTF-8") from error
    except OSError as error:
        raise ProtocolValidationError(
            f"cannot read task-run record: {error}"
        ) from error
    if not isinstance(parsed_task_run, dict):
        raise ProtocolValidationError("task-run record must be a JSON object")
    return parsed_task_run


def _require_fields(
    all_task_run_record: Mapping[str, object],
    all_required_field_names: Sequence[str],
    record_name: str,
) -> None:
    """Require named fields in a task-run mapping.

    Args:
        all_task_run_record: Mapping to inspect.
        all_required_field_names: Field names that must be present.
        record_name: Display name used in validation errors.

    Returns:
        None.

    Raises:
        ProtocolValidationError: If a required field is absent.
    """
    missing_field_names = [
        each_field_name
        for each_field_name in all_required_field_names
        if each_field_name not in all_task_run_record
    ]
    if missing_field_names:
        raise ProtocolValidationError(
            f"{record_name} missing: "
            f"{MISSING_FIELD_SEPARATOR.join(missing_field_names)}"
        )


def _reject_additional_fields(
    all_task_run_record: Mapping[str, object],
    all_allowed_field_names: Sequence[str],
    record_name: str,
) -> None:
    """Reject fields that are not named by the record schema.

    Args:
        all_task_run_record: Mapping to inspect.
        all_allowed_field_names: Field names accepted by the schema.
        record_name: Display name used in validation errors.

    Returns:
        None.

    Raises:
        ProtocolValidationError: If an unknown field is present.
    """
    allowed_field_names = set(all_allowed_field_names)
    additional_field_names = sorted(
        each_field_name
        for each_field_name in all_task_run_record
        if each_field_name not in allowed_field_names
    )
    if additional_field_names:
        raise ProtocolValidationError(
            f"{record_name} has additional fields: "
            f"{MISSING_FIELD_SEPARATOR.join(additional_field_names)}"
        )


def _require_text(
    all_task_run_record: Mapping[str, object], field_name: str, record_name: str
) -> None:
    """Require a non-empty text field in a task-run mapping.

    Args:
        all_task_run_record: Mapping containing the field.
        field_name: Name of the field to validate.
        record_name: Display name used in validation errors.

    Returns:
        None.

    Raises:
        ProtocolValidationError: If the field is absent, non-text, or empty.
    """
    field_text = all_task_run_record[field_name]
    if not isinstance(field_text, str) or not field_text:
        raise ProtocolValidationError(
            f"{record_name}.{field_name} must be a non-empty string"
        )


def _require_string_list(
    all_task_run_record: Mapping[str, object], field_name: str, record_name: str
) -> None:
    """Require a list containing only non-empty strings.

    Args:
        all_task_run_record: Mapping containing the field.
        field_name: Name of the field to validate.
        record_name: Display name used in validation errors.

    Returns:
        None.

    Raises:
        ProtocolValidationError: If the field is not a string list.
    """
    all_field_entries = all_task_run_record[field_name]
    if not isinstance(all_field_entries, list) or any(
        not isinstance(each_entry, str) or not each_entry
        for each_entry in all_field_entries
    ):
        raise ProtocolValidationError(
            f"{record_name}.{field_name} must be a string list"
        )


def _require_non_empty_string_list(
    all_task_run_record: Mapping[str, object], field_name: str, record_name: str
) -> None:
    """Require a non-empty list containing only non-empty strings.

    Args:
        all_task_run_record: Mapping containing the field.
        field_name: Name of the field to validate.
        record_name: Display name used in validation errors.

    Returns:
        None.

    Raises:
        ProtocolValidationError: If the field is not a non-empty string list.
    """
    _require_string_list(all_task_run_record, field_name, record_name)
    all_field_entries = all_task_run_record[field_name]
    if not all_field_entries:
        raise ProtocolValidationError(f"{record_name}.{field_name} must not be empty")


def _require_record(
    all_task_run_record: Mapping[str, object], field_name: str
) -> Mapping[str, object]:
    """Return a nested task-run mapping.

    Args:
        all_task_run_record: Mapping containing the nested record.
        field_name: Name of the nested record field.

    Returns:
        The nested task-run mapping.

    Raises:
        ProtocolValidationError: If the nested field is not an object.
    """
    nested_task_run_record = all_task_run_record[field_name]
    if not isinstance(nested_task_run_record, dict):
        raise ProtocolValidationError(f"record.{field_name} must be an object")
    return nested_task_run_record


def _validate_review_record(all_review_record: Mapping[str, object]) -> None:
    """Validate the findings-only review section.

    Args:
        all_review_record: Review mapping from the task-run record.

    Returns:
        None.

    Raises:
        ProtocolValidationError: If the review section violates its contract.
    """
    _reject_additional_fields(all_review_record, ALL_REVIEW_FIELDS, "review_record")
    _require_fields(all_review_record, ALL_REVIEW_FIELDS, "review_record")
    for each_field_name in ALL_REVIEW_TEXT_FIELDS:
        _require_text(all_review_record, each_field_name, "review_record")
    findings = all_review_record["findings"]
    if not isinstance(findings, list) or any(
        not isinstance(each_finding, dict)
        or not isinstance(each_finding.get("finding"), str)
        or each_finding.get("disposition") not in {
            FINDING_STATUS_CONFIRMED,
            FINDING_STATUS_DISMISSED,
        }
        for each_finding in findings
    ):
        raise ProtocolValidationError("review_record.findings must be classified")
    if all_review_record["findings_only"] is not True:
        raise ProtocolValidationError("review_record.findings_only must be true")
    if all_review_record["has_repair_flag"] is not False:
        raise ProtocolValidationError("review_record.has_repair_flag must be false")


def _validate_repair_record(all_repair_record: Mapping[str, object]) -> None:
    """Validate the confirmed-findings repair section.

    Args:
        all_repair_record: Repair mapping from the task-run record.

    Returns:
        None.

    Raises:
        ProtocolValidationError: If the repair section violates its contract.
    """
    _reject_additional_fields(all_repair_record, ALL_REPAIR_FIELDS, "repair_record")
    _require_fields(all_repair_record, ALL_REPAIR_FIELDS, "repair_record")
    for each_field_name in ALL_REPAIR_TEXT_FIELDS:
        _require_text(all_repair_record, each_field_name, "repair_record")
    _require_string_list(all_repair_record, "confirmed_findings", "repair_record")


def _validate_verification_record(
    all_verification_record: Mapping[str, object], record_name: str
) -> None:
    """Validate one verification evidence section.

    Args:
        all_verification_record: Verification mapping from the task-run record.
        record_name: Display name used in validation errors.

    Returns:
        None.

    Raises:
        ProtocolValidationError: If required evidence is missing or empty.
    """
    _reject_additional_fields(
        all_verification_record, ALL_VERIFICATION_FIELDS, record_name
    )
    _require_fields(all_verification_record, ALL_VERIFICATION_FIELDS, record_name)
    for each_field_name in ALL_VERIFICATION_FIELDS:
        _require_text(all_verification_record, each_field_name, record_name)
        if each_field_name != "surface_hash" and not all_verification_record[
            each_field_name
        ].lower().startswith(PASSED_EVIDENCE_PREFIX):
            raise ProtocolValidationError(
                f"{record_name}.{each_field_name} must be explicit passed evidence"
            )


def _normalize_allowed_path(raw_path: str) -> str:
    normalized_path = PATH_SEPARATOR_PATTERN.sub("/", raw_path.strip())
    normalized_path = normalized_path.removeprefix("./")
    if not normalized_path or normalized_path.startswith("../") or "/../" in normalized_path:
        raise ProtocolValidationError("allowed_files contains an unsafe path")
    if normalized_path.startswith("/") or (
        normalized_path[1:].startswith(":/")
    ):
        raise ProtocolValidationError("allowed_files contains an absolute path")
    if DOCS_PLANS_PATH_PATTERN.match(normalized_path.lower()):
        raise ProtocolValidationError("allowed_files cannot contain docs/plans paths")
    return normalized_path


def _validate_semantics(all_task_run_record: Mapping[str, object]) -> None:
    worker_route = all_task_run_record["worker_route"]
    if worker_route != f"{ALLOWED_WORKER_ROLE}; effort={ALLOWED_WORKER_EFFORT}":
        raise ProtocolValidationError("worker_route must be the fast low-effort Luna contract")
    all_allowed_files = all_task_run_record["allowed_files"]
    assert isinstance(all_allowed_files, list)
    normalized_files = [_normalize_allowed_path(each_path) for each_path in all_allowed_files if isinstance(each_path, str)]
    if len(normalized_files) != len(set(normalized_files)):
        raise ProtocolValidationError("allowed_files contains duplicate paths")
    review_record = _require_record(all_task_run_record, "review_record")
    if review_record["resolved_model"] != ALLOWED_REVIEW_MODEL or review_record["effort"] != ALLOWED_WORKER_EFFORT:
        raise ProtocolValidationError("review_record must use fast low-effort Luna")
    command = review_record["command"]
    if command != NATIVE_REVIEW_COMMAND or "--fix" in command:
        raise ProtocolValidationError("review_record.command must be exactly /e-code-review low")
    findings = review_record["findings"]
    assert isinstance(findings, list)
    confirmed_findings = [each_finding["finding"] for each_finding in findings if each_finding["disposition"] == FINDING_STATUS_CONFIRMED]
    repair_record = _require_record(all_task_run_record, "repair_record")
    if repair_record["confirmed_findings"] != confirmed_findings:
        raise ProtocolValidationError("repair_record must list exactly the confirmed findings")
    if confirmed_findings and repair_record["repair_status"] != REPAIR_STATUS_COMPLETE:
        raise ProtocolValidationError("confirmed findings require a completed repair")
    if not confirmed_findings and repair_record["repair_status"] != REPAIR_STATUS_NOT_REQUIRED:
        raise ProtocolValidationError("repair is permitted only when no findings are confirmed")
    hashes = [
        review_record["surface_hash"], repair_record["surface_hash"],
        _require_record(all_task_run_record, "reverification_record")["surface_hash"],
        _require_record(all_task_run_record, "verification_record")["surface_hash"],
    ]
    if any(not isinstance(each_hash, str) or SURFACE_HASH_PATTERN.fullmatch(each_hash) is None for each_hash in hashes) or len(set(hashes)) != 1:
        raise ProtocolValidationError("review and verification surface hashes must match")


def _committed_surface_hash(worktree: Path, commit_hash: str, all_allowed_files: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["git", "diff", f"{commit_hash}^", commit_hash, "--", *all_allowed_files],
            cwd=worktree, check=True, capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ProtocolValidationError("cannot compute committed task surface") from error
    return hashlib.new(SHA256_ALGORITHM, completed.stdout).hexdigest()


def validate_record(
    all_task_run_record: Mapping[str, object], schema_path: Path
) -> None:
    """Validate a complete task-run record against its JSON schema file.

    Args:
        all_task_run_record: Task-run mapping to validate.
        schema_path: Path to the task-run schema JSON file.

    Returns:
        None.

    Raises:
        ProtocolValidationError: If the schema or task-run record is invalid.
    """
    schema_object = _load_schema_object(schema_path)
    _validate_schema_node(all_task_run_record, schema_object, schema_object, "record")
    _reject_additional_fields(all_task_run_record, ALL_ALLOWED_RECORD_FIELDS, "record")
    _require_fields(all_task_run_record, ALL_RECORD_FIELDS, "record")
    for each_field_name in ALL_TOP_LEVEL_TEXT_FIELDS:
        _require_text(all_task_run_record, each_field_name, "record")
    _require_non_empty_string_list(all_task_run_record, "allowed_files", "record")
    commit_hash = all_task_run_record["commit"]
    if (
        not isinstance(commit_hash, str)
        or not MINIMUM_COMMIT_HASH_LENGTH
        <= len(commit_hash)
        <= MAXIMUM_COMMIT_HASH_LENGTH
        or COMMIT_HASH_PATTERN.fullmatch(commit_hash) is None
    ):
        raise ProtocolValidationError(
            COMMIT_HASH_ERROR_TEMPLATE
            % (MINIMUM_COMMIT_HASH_LENGTH, MAXIMUM_COMMIT_HASH_LENGTH)
        )
    _validate_review_record(_require_record(all_task_run_record, "review_record"))
    _validate_repair_record(_require_record(all_task_run_record, "repair_record"))
    _validate_verification_record(
        _require_record(all_task_run_record, "reverification_record"),
        "reverification_record",
    )
    _validate_verification_record(
        _require_record(all_task_run_record, "verification_record"),
        "verification_record",
    )
    _validate_semantics(all_task_run_record)
    worktree = all_task_run_record.get("worktree")
    if isinstance(worktree, str):
        all_allowed_files = [_normalize_allowed_path(each_path) for each_path in all_task_run_record["allowed_files"] if isinstance(each_path, str)]
        committed_hash = _committed_surface_hash(Path(worktree), str(all_task_run_record["commit"]), all_allowed_files)
        recorded_hash = _require_record(all_task_run_record, "verification_record")["surface_hash"]
        if committed_hash != recorded_hash:
            raise ProtocolValidationError("verification surface hash does not match the committed diff")


def main(all_cli_arguments: Sequence[str]) -> int:
    """Validate a task-run record from command-line arguments.

    Args:
        all_cli_arguments: Program name followed by one record path.

    Returns:
        Exit code `0` for a valid record or `2` for invalid input.
    """
    if len(all_cli_arguments) not in {
        ARGUMENT_COUNT_REQUIRED,
        ARGUMENT_COUNT_WITH_WORKTREE,
    } or (
        len(all_cli_arguments) == ARGUMENT_COUNT_WITH_WORKTREE
        and all_cli_arguments[2] != "--worktree"
    ):
        print("usage: validate_protocol.py <record.json> [--worktree PATH]", file=sys.stderr)
        return EXIT_CODE_INVALID_RECORD
    schema_path = Path(__file__).parent.parent / "reference" / RECORD_SCHEMA_FILENAME
    try:
        record = _load_json_object(Path(all_cli_arguments[1]))
        if len(all_cli_arguments) == ARGUMENT_COUNT_WITH_WORKTREE:
            record["worktree"] = all_cli_arguments[3]
        validate_record(record, schema_path)
    except ProtocolValidationError as error:
        print(f"protocol validation failed: {error}", file=sys.stderr)
        return EXIT_CODE_INVALID_RECORD
    print(PROTOCOL_VALIDATION_PASSED)
    return EXIT_CODE_VALID_RECORD


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
