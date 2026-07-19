"""Config constants for orchestrator run-status gate scripts."""

from __future__ import annotations

RUN_STATUS_ACTIVE = "active"
RUN_STATUS_DONE = "done"
ALL_VALID_RUN_STATUSES: frozenset[str] = frozenset(
    {RUN_STATUS_ACTIVE, RUN_STATUS_DONE}
)

STATUS_FIELD_NAME = "status"
UPDATED_AT_FIELD_NAME = "updated_at"
RUN_SLUG_FIELD_NAME = "run_slug"
REARM_PENDING_FIELD_NAME = "rearm_pending"
REASON_FIELD_NAME = "reason"
RESCHEDULE_FIELD_NAME = "reschedule"
STATUS_FILE_FIELD_NAME = "status_file"

STATUS_FILE_ENV_VAR = "ORCHESTRATOR_RUN_STATUS_FILE"
RUN_SLUG_ENV_VAR = "ORCHESTRATOR_RUN_SLUG"
ALL_DEFAULT_STATUS_DIRECTORY_PARTS: tuple[str, ...] = (
    "docs",
    "plans",
)
STATUS_FILE_NAME = ".orchestrator-run-status.json"
STATUS_FILE_TEMPORARY_SUFFIX = ".tmp"

COMMAND_SET = "set"
COMMAND_SHOULD_RESCHEDULE = "should-reschedule"
COMMAND_BEGIN_FIRING = "begin-firing"
COMMAND_CLAIM_REARM = "claim-rearm"
COMMAND_RELEASE_REARM = "release-rearm"
ALL_COMMANDS: tuple[str, ...] = (
    COMMAND_SET,
    COMMAND_SHOULD_RESCHEDULE,
    COMMAND_BEGIN_FIRING,
    COMMAND_CLAIM_REARM,
    COMMAND_RELEASE_REARM,
)

EXIT_CODE_SUCCESS = 0
EXIT_CODE_STOP = 1
EXIT_CODE_USAGE_ERROR = 2

REASON_MISSING_STATUS_FILE = "missing_status_file"
REASON_INVALID_STATUS_FILE = "invalid_status_file"
REASON_STATUS_NOT_ACTIVE = "status_not_active"
REASON_ACTIVE = "active"
REASON_REARM_ALREADY_PENDING = "rearm_already_pending"
REASON_REARM_SLOT_CLAIMED = "rearm_slot_claimed"
REASON_REARM_SLOT_RELEASED = "rearm_slot_released"
REASON_FIRING_STARTED = "firing_started"

JSON_INDENT_SPACES = 2
UTF8_ENCODING = "utf-8"
