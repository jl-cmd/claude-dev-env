"""Configuration constants for the reviewer_spawn_gate PreToolUse hook."""

from __future__ import annotations

import re
from pathlib import Path

BASH_TOOL_NAME: str = "Bash"

GATE_SENTINEL_MARKER: str = "CLAUDE_REVIEWER_GATE=autoconverge"

COPILOT_REVIEWER_TOKEN: str = "copilot"
BUGBOT_REVIEWER_TOKEN: str = "bugbot"

COPILOT_REVIEWER_LABEL: str = "GitHub Copilot"
BUGBOT_REVIEWER_LABEL: str = "Cursor Bugbot"

ALL_COPILOT_TRIGGER_MARKERS: tuple[str, ...] = (
    "requested_reviewers",
    "copilot-pull-request-reviewer[bot]",
)

BUGBOT_TRIGGER_SCRIPT_MARKER: str = "post_fix_reply.py"
BUGBOT_RUN_BODY_PATTERN: re.Pattern[str] = re.compile(
    r'--body\s+["\']bugbot run["\']', re.IGNORECASE
)

AVAILABILITY_SCRIPT_RELATIVE_PATH: Path = (
    Path("_shared") / "pr-loop" / "scripts" / "reviewer_availability.py"
)
AVAILABILITY_SCRIPT_PATH_ENV_VAR_NAME: str = "REVIEWER_SPAWN_GATE_AVAILABILITY_SCRIPT_PATH"
AVAILABILITY_SCRIPT_TIMEOUT_SECONDS: int = 15
AVAILABILITY_REVIEWER_FLAG: str = "--reviewer"
AVAILABILITY_AVAILABLE_EXIT_CODE: int = 0

DENY_REASON_TEMPLATE: str = (
    "BLOCKED [reviewer-spawn-gate]: {reviewer_label} is down or out of quota "
    "this run. Skip requesting {reviewer_label} on this trigger — "
    "autoconverge requests it again once the availability check reports it "
    "back.\n\nAvailability check output: {availability_detail}"
)
