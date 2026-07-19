"""Constants for the write_goal_pair CLI.

Groups: run-directory and output-file naming, template file locations, the
packet JSON schema keys (top level, ``context``, and ``tasks``), template
substitution placeholders for both rendered documents, bullet and table row
formatting, the stdout path-print contract, exit codes, and every
one-line error message the CLI can print to stderr.
"""

from __future__ import annotations

ENCODING_UTF8 = "utf-8"
NEWLINE_JOIN_SEPARATOR = "\n"

# Run directory and output file naming
TEMP_ROOT_SUBDIRECTORY_NAME = "build-goal"
GOAL_CMD_OUTPUT_FILENAME = "goal-cmd-prompt.md"
HUMAN_BRIEF_OUTPUT_FILENAME = "goal-cmd-human.md"
ATOMIC_WRITE_TEMP_SUFFIX = ".tmp"
RUN_ID_TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S"
RUN_ID_RANDOM_SUFFIX_BYTE_LENGTH = 3
RUN_ID_SEPARATOR = "-"

# Template file locations
TEMPLATES_DIRECTORY_NAME = "templates"
GOAL_CMD_TEMPLATE_FILENAME = "goal-cmd-template.md"
HUMAN_BRIEF_TEMPLATE_FILENAME = "human-brief-template.md"

# Packet schema: top-level keys
PACKET_KEY_OBJECTIVE = "objective"
PACKET_KEY_DONE_WHEN = "done_when"
PACKET_KEY_IN_SCOPE = "in_scope"
PACKET_KEY_OUT_OF_SCOPE = "out_of_scope"
PACKET_KEY_TASKS = "tasks"
PACKET_KEY_CONTEXT = "context"
PACKET_KEY_EXECUTION_NOTES = "execution_notes"

# Packet schema: context sub-keys
CONTEXT_KEY_REPO = "repo"
CONTEXT_KEY_BRANCH = "branch"
CONTEXT_KEY_PR = "pr"
CONTEXT_KEY_PATHS = "paths"
CONTEXT_KEY_CONSTRAINTS = "constraints"

# Packet schema: task sub-keys and status values
TASK_KEY_ID = "id"
TASK_KEY_STATUS = "status"
TASK_KEY_SUBJECT = "subject"
TASK_STATUS_PENDING = "pending"
TASK_STATUS_IN_PROGRESS = "in_progress"
TASK_STATUS_COMPLETED = "completed"
ALL_VALID_TASK_STATUSES = (
    TASK_STATUS_PENDING,
    TASK_STATUS_IN_PROGRESS,
    TASK_STATUS_COMPLETED,
)
TASK_CHECKED_MARK = "[x]"
TASK_UNCHECKED_MARK = "[ ]"

# Context bullet rendering
CONTEXT_REPO_LABEL = "repo: "
CONTEXT_BRANCH_LABEL = "branch: "
CONTEXT_PR_LABEL = "PR: "
CONTEXT_PATHS_LABEL = "paths: "
CONTEXT_PATHS_JOIN_SEPARATOR = ", "

# goal-cmd-template.md substitution placeholders
GOAL_CMD_PLACEHOLDER_OBJECTIVE = "{{GOAL}}"
GOAL_CMD_PLACEHOLDER_DONE_WHEN = "{{DONE_WHEN_BULLETS}}"
GOAL_CMD_PLACEHOLDER_IN_SCOPE = "{{IN_SCOPE_BULLETS}}"
GOAL_CMD_PLACEHOLDER_OUT_OF_SCOPE = "{{OUT_OF_SCOPE_BULLETS}}"
GOAL_CMD_PLACEHOLDER_TASKS = "{{TASKS_BULLETS}}"
GOAL_CMD_PLACEHOLDER_CONTEXT = "{{CONTEXT_BULLETS}}"
GOAL_CMD_PLACEHOLDER_EXECUTION_NOTES = "{{EXECUTION_NOTES_BULLETS}}"

# human-brief-template.md substitution placeholders
HUMAN_BRIEF_PLACEHOLDER_OBJECTIVE = "{{GOAL}}"
HUMAN_BRIEF_PLACEHOLDER_DONE_WHEN_ROWS = "{{DONE_WHEN_TABLE_ROWS}}"
HUMAN_BRIEF_PLACEHOLDER_TASKS_ROWS = "{{TASKS_TABLE_ROWS}}"
HUMAN_BRIEF_PLACEHOLDER_CONSTRAINTS_ROWS = "{{CONSTRAINTS_TABLE_ROWS}}"
HUMAN_BRIEF_PLACEHOLDER_IN_SCOPE = "{{IN_SCOPE_BULLETS}}"
HUMAN_BRIEF_PLACEHOLDER_OUT_OF_SCOPE = "{{OUT_OF_SCOPE_BULLETS}}"
HUMAN_BRIEF_PLACEHOLDER_CONTEXT = "{{CONTEXT_BULLETS}}"
HUMAN_BRIEF_PLACEHOLDER_EXECUTION_NOTES = "{{EXECUTION_NOTES_BULLETS}}"

# Bullet and table row formatting
BULLET_LINE_PREFIX = "- "
NUMBERED_TABLE_ROW_FORMAT = "| {index} | {text} |"
TASKS_TABLE_ROW_FORMAT = "| {mark} | {task_id} | {subject} |"
TASKS_BULLET_LINE_FORMAT = f"{BULLET_LINE_PREFIX}{{mark}} {{task_id}}: {{subject}}"

# Blank-line normalization after placeholder substitution
BLANK_LINE_COLLAPSE_PATTERN = r"\n{3,}"
BLANK_LINE_COLLAPSE_REPLACEMENT = "\n\n"

# stdout path-print contract
STDOUT_GOAL_CMD_PATH_PREFIX = "GOAL_CMD_PATH: "
STDOUT_HUMAN_BRIEF_PATH_PREFIX = "HUMAN_BRIEF_PATH: "

# Exit codes
EXIT_CODE_SUCCESS = 0
EXIT_CODE_WRITE_FAILED = 1
EXIT_CODE_INVALID_PACKET = 2

# Error messages
ERROR_PACKET_PATH_ARGUMENT_REQUIRED = "usage: write_goal_pair.py <packet-json-path>"
ERROR_PACKET_FILE_UNREADABLE = "cannot read packet file: %s"
ERROR_PACKET_JSON_INVALID = "packet file is not valid JSON: %s"
ERROR_PACKET_ROOT_NOT_OBJECT = "packet file must contain a JSON object"
ERROR_OBJECTIVE_REQUIRED = "packet is missing a non-empty 'objective'"
ERROR_DONE_WHEN_REQUIRED = "packet is missing a non-empty 'done_when' list"
ERROR_DONE_WHEN_ENTRY_INVALID = "packet 'done_when' entries must be non-empty strings"
ERROR_IN_SCOPE_ENTRY_INVALID = "packet 'in_scope' entries must be non-empty strings"
ERROR_OUT_OF_SCOPE_ENTRY_INVALID = (
    "packet 'out_of_scope' entries must be non-empty strings"
)
ERROR_EXECUTION_NOTES_ENTRY_INVALID = (
    "packet 'execution_notes' entries must be non-empty strings"
)
ERROR_TASKS_NOT_LIST = "packet 'tasks' must be a list"
ERROR_TASK_ENTRY_INVALID = (
    "packet task entries need string 'id', 'status', and 'subject'"
)
ERROR_TASK_STATUS_INVALID = (
    "packet task 'status' must be one of pending, in_progress, completed"
)
ERROR_CONTEXT_NOT_OBJECT = "packet 'context' must be a JSON object"
ERROR_CONTEXT_PATHS_NOT_LIST = "packet 'context.paths' must be a list of strings"
ERROR_CONTEXT_CONSTRAINTS_NOT_LIST = (
    "packet 'context.constraints' must be a list of strings"
)
ERROR_CONTEXT_SCALAR_FIELD_INVALID = "packet 'context.repo', 'context.branch', and 'context.pr' must be non-empty strings when present"
