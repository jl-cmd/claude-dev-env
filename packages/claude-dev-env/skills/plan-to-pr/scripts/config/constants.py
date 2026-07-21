"""Named values for deterministic skill protocol validation."""

import re

ALLOWED_WORKER_ROLE: str = "implementation worker"
ALLOWED_WORKER_EFFORT: str = "low"
ALLOWED_REVIEW_MODEL: str = "Luna"
NATIVE_REVIEW_COMMAND: str = "/e-code-review low"
PASSED_EVIDENCE_PREFIX: str = "passed:"
SURFACE_HASH_PATTERN: re.Pattern[str] = re.compile(r"^[0-9a-f]{64}$")
PATH_SEPARATOR_PATTERN: re.Pattern[str] = re.compile(r"[/\\]+")
DOCS_PLANS_PATH_PATTERN: re.Pattern[str] = re.compile(r"^docs/plans(?:/|$)")
SLUG_PATTERN: re.Pattern[str] = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")
SOURCE_LOCATOR_PATTERN: re.Pattern[str] = re.compile(
    r"^(?:line|lines|section)\s+\S(?:.*\S)?$", re.IGNORECASE
)
PATH_TRAVERSAL_TOKEN: str = ".."
REPRODUCIBILITY_BLOCK_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:date|random|uuidgen|pwsh\s+-c)\b", re.IGNORECASE
)
UNRESOLVED_TEXT_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:todo|tbd|fixme|placeholder|open questions|to be decided|fill this in)\b|\{\{[^}]+\}\}|<[A-Za-z][^>]*>",
    re.IGNORECASE,
)
COMMIT_RANGE_SEPARATOR: str = ".."
EXIT_CODE_USAGE_ERROR: int = 2
PACKET_CREATION_ERROR_EXIT_CODE: int = 2
PACKET_VALIDATION_ERROR_EXIT_CODE: int = 2
EXIT_CODE_VALID_SET: int = 0
EXIT_CODE_INVALID_SET: int = 2
VALIDATION_PASSED: str = "run validation passed"
SET_VALIDATION_PASSED: str = "run set validation passed"
WORKTREE_OPTION: str = "--worktree"
BASE_HEAD_OPTION: str = "--base-head"
COMMIT_SET_OPTION: str = "--commits"
FINDING_STATUS_CONFIRMED: str = "confirmed"
FINDING_STATUS_DISMISSED: str = "dismissed"
REPAIR_STATUS_COMPLETE: str = "complete"
REPAIR_STATUS_NOT_REQUIRED: str = "not-required"
REVIEW_STATUS_CLEAN: str = "clean"
GIT_COMMAND: str = "git"
GIT_DIFF_FORMAT: str = "--format="
GIT_DIFF_SEPARATOR: str = "\n"
SHA256_ALGORITHM: str = "sha256"
ALL_REQUIRED_PACKET_FILES: tuple[str, ...] = (
    "packet.json",
    "context.md",
    "plan.md",
    "tasks.md",
    "handoff.md",
)
ALL_SOURCE_FIELDS: tuple[str, ...] = ("path", "locator", "fact")
ALL_TASK_FIELDS: tuple[str, ...] = (
    "deliverable",
    "acceptance_command",
    "test_command",
    "verification_command",
)
ALL_TASK_COMMAND_FIELDS: tuple[str, ...] = (
    "acceptance_command",
    "test_command",
    "verification_command",
)
HANDOFF_APPROVAL_LINE: str = "Approval: approved"
HANDOFF_TASK_ORDER_PREFIX: str = "Task Order: "
HANDOFF_PACKET_PREFIX: str = "Packet: "
HANDOFF_ALLOWED_FILES_PREFIX: str = "Allowed files: "
HANDOFF_ACCEPTANCE_PREFIX: str = "Acceptance command: "
HANDOFF_TEST_PREFIX: str = "Test command: "
HANDOFF_VERIFICATION_PREFIX: str = "Verification command: "
TASK_LINE_PREFIX: str = "Task "
HANDOFF_TASK_LINE_PATTERN: re.Pattern[str] = re.compile(r"^Task (task-[0-9]+):")
LINE_SEPARATOR: str = "\n"
COMMAND_SEPARATOR: str = ", "
MARKDOWN_FIELD_SEPARATOR: str = ";"
MARKDOWN_HEADING_PATTERN: re.Pattern[str] = re.compile(
    r"^#+\s+\S.*\s*$", re.MULTILINE | re.IGNORECASE
)
MARKDOWN_HEADING_TEMPLATE: str = r"^#+\s+{}\s*$"
PACKET_DIRECTORY_MINIMUM_PARTS: int = 3
PACKET_JSON_INDENT_LEVEL: int = 2
DOCS_DIRECTORY_NAME: str = "docs"
NEWLINE_SEPARATOR: str = "\n"
PACKET_PARENT_PARTS_SLICE_START: int = -3
PACKET_SLUG_PARTS_SLICE_END: int = -1
ALL_PACKET_FIELDS: tuple[str, ...] = (
    "schema_version",
    "slug",
    "status",
    "request",
    "allowed_files",
    "sources",
    "decisions",
    "open_questions",
    "tasks",
    "validation",
)
ALL_PACKET_REQUIRED_FIELDS: tuple[str, ...] = ALL_PACKET_FIELDS
ALL_VALIDATION_FIELDS: tuple[str, ...] = (
    "schema_valid",
    "boundary_valid",
    "markdown_matches",
    "validated_by",
)
ALL_TASK_CONTRACT_FIELDS: tuple[str, ...] = (
    "id",
    "deliverable",
    "allowed_files",
    "acceptance_command",
    "test_command",
    "verification_command",
    "commit",
    "dependencies",
)

ARGUMENT_COUNT_REQUIRED: int = 2
ARGUMENT_COUNT_WITH_WORKTREE: int = 4
RUN_ARGUMENT_COUNT_REQUIRED: int = 4
RUN_ARGUMENT_COUNT_WITH_WORKTREE: int = 5
OPTION_ARGUMENT_INDEX: int = 2
COMMIT_RANGE_ARGUMENT_INDEX: int = 3
WORKTREE_OPTION_ARGUMENT_INDEX: int = 4
WORKTREE_PATH_ARGUMENT_INDEX: int = 5
COMMIT_HASH_PATTERN: re.Pattern[str] = re.compile(r"^[0-9a-f]{7,40}$")
COMMIT_HASH_ERROR_TEMPLATE: str = (
    "record.commit must be a %d-%d character lowercase commit hash"
)
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
ALL_ALLOWED_RECORD_FIELDS: tuple[str, ...] = ALL_RECORD_FIELDS + ("worktree",)
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
