"""Outcome vocabulary and fixed settings the hook harness runs one hook with.

Every name here follows the external hooks reference (source lock W1): the
exit codes a client reads, the events whose stdout the client keeps, and the
payload field each event matches its matcher against.
"""

from __future__ import annotations

import re
from typing import Literal

Outcome = Literal["block", "ask", "rewrite", "advise", "silent", "harness_failure"]

PLUGIN_ROOT_PLACEHOLDER = "${CLAUDE_PLUGIN_ROOT}"
PLUGIN_ROOT_ENVIRONMENT_NAME = "CLAUDE_PLUGIN_ROOT"
EXIT_CODE_SUCCESS = 0
EXIT_CODE_BLOCKING = 2
SECONDS_PER_DAY = 86400
MILLISECONDS_PER_SECOND = 1000
DEFAULT_HOOK_TIMEOUT_SECONDS = 600
ALL_EVENTS_EXIT_TWO_BLOCKS = frozenset({"PreToolUse", "UserPromptSubmit"})
ALL_EVENTS_EXIT_TWO_FEEDS_MODEL = frozenset({"PostToolUse"})
ALL_EVENTS_PLAIN_STDOUT_IS_CONTEXT = frozenset({"SessionStart", "UserPromptSubmit"})
ALL_EVENTS_STDOUT_DISCARDED = frozenset({"SessionEnd", "InstructionsLoaded"})
ALL_EVENTS_CARRYING_PERMISSION_MODE = ("PreToolUse", "PostToolUse", "UserPromptSubmit")
ALL_EVENTS_CARRYING_TOOL_USE_ID = ("PreToolUse", "PostToolUse")
ALL_MATCHER_FIELDS_BY_EVENT = {
    "PreToolUse": "tool_name",
    "PostToolUse": "tool_name",
    "SessionStart": "source",
    "SessionEnd": "reason",
    "InstructionsLoaded": "load_reason",
}
ALL_MATCH_EVERY_PAYLOAD_MATCHERS = ("", "*")
ALL_HOME_ENVIRONMENT_NAMES = ("HOME", "USERPROFILE")
ALL_SCRATCH_ENVIRONMENT_NAMES = ("TEMP", "TMP", "TMPDIR")
EXACT_MATCHER_PATTERN = re.compile(r"^[A-Za-z0-9_\- ,|]*$")
MATCHER_ALTERNATIVE_PATTERN = re.compile(r"[|,]")
ALL_OUTCOMES_BY_SEVERITY: tuple[Outcome, ...] = (
    "harness_failure",
    "block",
    "ask",
    "rewrite",
    "advise",
    "silent",
)
