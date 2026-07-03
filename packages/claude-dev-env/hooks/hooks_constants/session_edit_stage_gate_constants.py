"""Constants for the session-edit stage gate hook trio.

Shared by the PostToolUse tracker
(``hooks/observability/session_file_edit_tracker.py``), the PreToolUse gate
(``hooks/blocking/session_edit_stage_gate.py``), and the SessionStart cleanup
(``hooks/session/session_edit_tracker_cleanup.py``): the per-session tracker
filename shape and JSON payload key, the session-id sanitize pattern, the
SessionStart source key and the fresh-startup source value the cleanup keys its
deletion on, the edit-tool name set, the tracker stale-age threshold, the
git-diff command and its output encoding, the commit-flag escapes the gate
honors, and the deny-message template.
"""

from __future__ import annotations

import re

SESSION_EDIT_FILE_PREFIX: str = "claude-session-edits-"
SESSION_EDIT_FILE_SUFFIX: str = ".json"
ALL_EDITED_FILE_PATHS_KEY: str = "all_edited_file_paths"
STATE_FILE_DEFAULT_SESSION_ID: str = "default"
SESSION_ID_UNSAFE_CHARACTERS_PATTERN: re.Pattern[str] = re.compile(r"[^A-Za-z0-9_-]")

SESSION_START_SOURCE_PAYLOAD_KEY: str = "source"
SESSION_START_SOURCE_FRESH_STARTUP: str = "startup"

ALL_TRACKED_EDIT_TOOL_NAMES: tuple[str, ...] = ("Write", "Edit", "MultiEdit")

STATE_FILE_ATOMIC_WRITE_SUFFIX: str = ".tmp"
STATE_FILE_JSON_INDENT_SPACES: int = 2

SESSION_EDIT_FILE_STALE_AGE_SECONDS: int = 1800

GIT_DIFF_TIMEOUT_SECONDS: int = 5
GIT_DIFF_OUTPUT_ENCODING: str = "utf-8"
ALL_TRACKED_UNSTAGED_FILES_COMMAND: tuple[str, ...] = (
    "git",
    "-c",
    "core.quotePath=false",
    "diff",
    "--name-only",
)

PARTIAL_COMMIT_BYPASS_MARKER: str = "# partial-commit"
COMMIT_SUBCOMMAND_TOKEN: str = "commit"
SHORT_FLAG_PREFIX: str = "-"
LONG_FLAG_PREFIX: str = "--"
COMMIT_ALL_SHORT_FLAG_LETTER: str = "a"
ALL_COMMIT_ALL_FLAGS: frozenset[str] = frozenset({"-a", "--all"})
ALL_COMMIT_VALUE_OPTION_TOKENS: frozenset[str] = frozenset(
    {
        "-m",
        "--message",
        "-F",
        "--file",
        "-C",
        "--reuse-message",
        "-c",
        "--reedit-message",
        "--author",
        "--date",
        "--fixup",
        "--squash",
        "--cleanup",
    }
)
ALL_COMMAND_SEPARATOR_TOKENS: frozenset[str] = frozenset({"&&", "||", ";", "|", "&"})

DENY_FILE_BULLET_PREFIX: str = "  - "
SESSION_EDIT_DENY_TEMPLATE: str = (
    "BLOCKED: these files were edited this session and are tracked but left "
    "unstaged, so this commit would drop them:\n{file_list}\n"
    "Stage them with `git add {space_joined_paths}`, or run `git commit -a` to "
    "include every tracked change, or add `{bypass_marker}` to the command to "
    "commit without them on purpose."
)
