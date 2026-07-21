"""Named values for deterministic skill protocol validation."""

import re

ARGUMENT_COUNT_REQUIRED: int = 2
COMMIT_HASH_PATTERN: re.Pattern[str] = re.compile(r"^[0-9a-f]{7,40}$")
COMMIT_HASH_ERROR_TEMPLATE: str = "record.commit must be a %d-%d character lowercase commit hash"
EXIT_CODE_INVALID_RECORD: int = 2
EXIT_CODE_VALID_RECORD: int = 0
JSON_ENCODING: str = "utf-8"
MAXIMUM_COMMIT_HASH_LENGTH: int = 40
MINIMUM_COMMIT_HASH_LENGTH: int = 7
MISSING_FIELD_SEPARATOR: str = ", "
PROTOCOL_VALIDATION_PASSED: str = "protocol validation passed"
RECORD_SCHEMA_FILENAME: str = "run-record.schema.json"
ALL_SUPPORTED_SCHEMA_TYPES: tuple[str, ...] = ("object", "array", "string", "boolean")
ALL_RECORD_FIELDS: tuple[str, ...] = (
    "task_identity",
    "deliverable",
    "allowed_files",
    "acceptance_check",
    "baseline",
    "worker_route",
    "commit",
    "review_record",
    "repair_record",
    "reverification_record",
    "verification_record",
)
ALL_TOP_LEVEL_TEXT_FIELDS: tuple[str, ...] = (
    "task_identity",
    "deliverable",
    "acceptance_check",
    "baseline",
    "worker_route",
)
ALL_REVIEW_FIELDS: tuple[str, ...] = (
    "resolved_model",
    "effort",
    "command",
    "findings",
    "repair_status",
    "surface_hash",
    "findings_only",
    "has_repair_flag",
)
ALL_REPAIR_FIELDS: tuple[str, ...] = (
    "resolved_model",
    "effort",
    "confirmed_findings",
    "repair_status",
    "surface_hash",
)
ALL_VERIFICATION_FIELDS: tuple[str, ...] = (
    "acceptance_output",
    "verifier_output",
    "verified_commit_gate",
    "surface_hash",
)
ALL_REVIEW_TEXT_FIELDS: tuple[str, ...] = (
    "resolved_model",
    "effort",
    "command",
    "repair_status",
    "surface_hash",
)
ALL_REPAIR_TEXT_FIELDS: tuple[str, ...] = (
    "resolved_model",
    "effort",
    "repair_status",
    "surface_hash",
)
