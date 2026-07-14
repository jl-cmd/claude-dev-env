"""Named constants for the codex-review headless wrapper."""

from __future__ import annotations

CODEX_BINARY_NAME = "codex"
EXEC_SUBCOMMAND = "exec"
REVIEW_SUBCOMMAND = "review"
HELP_FLAG = "--help"
VERSION_FLAG = "--version"
JSON_FLAG = "--json"
BASE_TARGET_FLAG = "--base"
UNCOMMITTED_TARGET_FLAG = "--uncommitted"
COMMIT_TARGET_FLAG = "--commit"
MODEL_FLAG = "-m"
CODEX_MODEL_PIN = ""
CODEX_HOME_ENV_VAR = "CODEX_HOME"
DEFAULT_TIMEOUT_SECONDS = 600
JSONL_CAPTURE_FILENAME = "codex-review.jsonl"
UTF8_ENCODING = "utf-8"
SUBPROCESS_TEXT_ERRORS = "replace"
VERSION_PROBE_PATTERN = r"codex(?:-cli)?\s+(\d+\.\d+\.\d+)"
OUTCOME_CLASS_CODEX_DOWN = "codex_down"
OUTCOME_CLASS_COMPLETED = "completed"
MISSING_BINARY_EXIT_CODE = 127
TIMEOUT_EXIT_CODE = 124
DECODE_ERROR_EXIT_CODE = 126
JSONL_EVENT_TYPE_KEY = "type"
JSONL_ENTRY_KEY = "item"
JSONL_ENTRY_COMPLETED_TYPE = "item.completed"
JSONL_AGENT_MESSAGE_TYPE = "agent_message"
JSONL_AGENT_MESSAGE_TEXT_KEY = "text"
CUSTOM_INSTRUCTIONS_PROMPT = (
    "Return findings inside one fenced JSON code block. "
    "The block body must be a JSON array. "
    "Each element is an object with keys title, priority, file, line_range, and body. "
    "When there are no findings, return an empty JSON array in that fenced block."
)
ALL_SHAPE_PROBE_REQUIRED_FLAGS = (
    BASE_TARGET_FLAG,
    UNCOMMITTED_TARGET_FLAG,
    COMMIT_TARGET_FLAG,
)
