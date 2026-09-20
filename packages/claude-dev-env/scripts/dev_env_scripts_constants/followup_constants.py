"""Constants for the follow-up ledger command and the instruction-pair gate.

Script-level scalar constants live in dev_env_scripts_constants alongside
timing.py and the other per-script constant modules.
"""

from __future__ import annotations

FILENAME_RULE_ID: str = "instruction-filename"
REGULAR_FILE_RULE_ID: str = "instruction-regular-file"
GIT_MODE_RULE_ID: str = "instruction-git-mode"
MISSING_AGENTS_RULE_ID: str = "instruction-missing-agents"
IMPORT_TEXT_RULE_ID: str = "instruction-import-text"

SEVERITY_BREAKING: str = "breaking"
SEVERITY_SMELL: str = "smell"
SEVERITY_BY_RULE_ID: dict[str, str] = {
    FILENAME_RULE_ID: SEVERITY_SMELL,
    REGULAR_FILE_RULE_ID: SEVERITY_BREAKING,
    GIT_MODE_RULE_ID: SEVERITY_SMELL,
    MISSING_AGENTS_RULE_ID: SEVERITY_BREAKING,
    IMPORT_TEXT_RULE_ID: SEVERITY_BREAKING,
}

GATE_PASSED_EXIT_CODE: int = 0
GATE_FAILED_EXIT_CODE: int = 1
RECORDED_SMELL_TEMPLATE: str = "recorded for follow-up: %s"

LIST_COMMAND_NAME: str = "list"
INGEST_COMMAND_NAME: str = "ingest"
BRIEF_COMMAND_NAME: str = "brief"
CLEAR_COMMAND_NAME: str = "clear"
ALL_COMMAND_NAMES: tuple[str, ...] = (
    LIST_COMMAND_NAME,
    INGEST_COMMAND_NAME,
    BRIEF_COMMAND_NAME,
    CLEAR_COMMAND_NAME,
)

SUCCESS_EXIT_CODE: int = 0
INVALID_INPUT_EXIT_CODE: int = 2

DIAGNOSTICS_KEY: str = "diagnostics"
DIAGNOSTIC_RULE_ID_KEY: str = "rule_id"
DIAGNOSTIC_MESSAGE_KEY: str = "message"
DIAGNOSTIC_LOCATION_KEY: str = "location"
LOCATION_PATH_KEY: str = "path"
ABSENT_LOCATION_PATH: str = ""

LINE_SEPARATOR: str = "\n"
EMPTY_LEDGER_MESSAGE: str = "no follow-ups recorded"
UNREADABLE_REPORT_TEMPLATE: str = "cannot read the lint report: {report_path}"
USAGE_TEXT: str = (
    "Usage: followup_cli.py <list|ingest|brief|clear> [--repository-root PATH]\n"
    "  list              Name every recorded follow-up\n"
    "  ingest REPORT     Record every diagnostic in a policy-lint JSON report\n"
    "  brief             Write the task an agent works the follow-ups from\n"
    "  clear             Empty the ledger"
)

BRIEF_HEADER: str = (
    "Fix every finding below in one change, then open a draft pull request "
    "for it. Each finding is non-breaking, so the change that raised it "
    "already shipped. Keep the fixes mechanical, touch no behavior, and run "
    "the repository's own checks before pushing."
)
BRIEF_FINDING_TEMPLATE: str = "- [{rule_id}] {file_path}: {message}"
BRIEF_FOOTER_TEMPLATE: str = (
    "Once the pull request is open, empty the ledger with "
    "`python {command_path} clear`."
)
LIST_FINDING_TEMPLATE: str = "{rule_id}\t{file_path}\t{message}"
