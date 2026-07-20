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
JSONL_CAPTURE_NEWLINE = ""
UTF8_ENCODING = "utf-8"
VERSION_PROBE_PATTERN = r"codex(?:-cli)?\s+(\d+\.\d+\.\d+)"
OUTCOME_CLASS_CODEX_DOWN = "codex_down"
OUTCOME_CLASS_COMPLETED = "completed"
MISSING_BINARY_EXIT_CODE = 127
TIMEOUT_EXIT_CODE = 124
SUBPROCESS_DECODE_EXIT_CODE = 70
CWD_KEYWORD = "cwd"
CAPTURE_STREAMS_KEYWORD = "capture_output"
TEXT_MODE_KEYWORD = "text"
ENCODING_KEYWORD = "encoding"
CHECK_KEYWORD = "check"
TIMEOUT_KEYWORD = "timeout"
ENVIRONMENT_KEYWORD = "env"
PROCESS_TREE_KILL_TIMEOUT_SECONDS = 10
SHAPE_FLAG_TOKEN_TAIL_PATTERN = r"(?![\w-])"
JSONL_EVENT_TYPE_KEY = "type"
JSONL_ENTRY_KEY = "item"
JSONL_ENTRY_COMPLETED_TYPE = "item.completed"
JSONL_AGENT_MESSAGE_TYPE = "agent_message"
JSONL_AGENT_MESSAGE_TEXT_KEY = "text"
CUSTOM_INSTRUCTIONS_PROMPT = (
    "Write a one-line review summary, then the heading Review comment:, then "
    "zero or more finding bullets. Each bullet must use the form "
    "- [P1] <title> — <path>:<start>-<end> "
    "followed by an explanation paragraph. Use the same [P#] priority tags. "
    "When there are no findings, omit finding bullets after the summary."
)
ALL_SHAPE_PROBE_REQUIRED_FLAGS = (
    BASE_TARGET_FLAG,
    UNCOMMITTED_TARGET_FLAG,
    COMMIT_TARGET_FLAG,
    JSON_FLAG,
)
