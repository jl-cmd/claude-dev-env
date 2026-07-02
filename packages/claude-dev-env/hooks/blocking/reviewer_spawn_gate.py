#!/usr/bin/env python3
"""PreToolUse hook: block a reviewer-spawn trigger when that reviewer is down.

autoconverge already skips a reviewer step when its own pre-check reports
that reviewer unavailable. That skip only protects the trigger commands the
workflow generates and inspects itself. This hook is the backstop: it reads
the Bash command a tool call is about to run and blocks it when the matched
reviewer reports unavailable.

The gate only inspects a command carrying the literal sentinel marker
`CLAUDE_REVIEWER_GATE=autoconverge`. autoconverge prepends this marker to its
own trigger commands. A command without the marker is never inspected, so a
manual or unrelated `gh` call always passes through untouched.

A Copilot trigger is a command containing both `requested_reviewers` and
`copilot-pull-request-reviewer[bot]`. A Bugbot trigger is a command
containing `post_fix_reply.py` and a `--body "bugbot run"` argument.

For the matched reviewer, the gate runs
`reviewer_availability.py --reviewer copilot|bugbot` and denies the call when
that script exits non-zero. The deny reason names the reviewer and carries
the script's output. The script path resolves relative to this hook's
install location by default, or from the
`REVIEWER_SPAWN_GATE_AVAILABILITY_SCRIPT_PATH` environment variable when set.
A missing script, a timeout, or a failure to launch it allows the call
(fail open), so a broken availability check never blocks a legitimate run.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.reviewer_spawn_gate_constants import (  # noqa: E402
    ALL_COPILOT_TRIGGER_MARKERS,
    AVAILABILITY_AVAILABLE_EXIT_CODE,
    AVAILABILITY_REVIEWER_FLAG,
    AVAILABILITY_SCRIPT_PATH_ENV_VAR_NAME,
    AVAILABILITY_SCRIPT_RELATIVE_PATH,
    AVAILABILITY_SCRIPT_TIMEOUT_SECONDS,
    BASH_TOOL_NAME,
    BUGBOT_REVIEWER_LABEL,
    BUGBOT_REVIEWER_TOKEN,
    BUGBOT_RUN_BODY_PATTERN,
    BUGBOT_TRIGGER_SCRIPT_MARKER,
    COPILOT_REVIEWER_LABEL,
    COPILOT_REVIEWER_TOKEN,
    DENY_REASON_TEMPLATE,
    GATE_SENTINEL_MARKER,
)


def _matches_copilot_trigger(command: str) -> bool:
    return all(each_marker in command for each_marker in ALL_COPILOT_TRIGGER_MARKERS)


def _matches_bugbot_trigger(command: str) -> bool:
    return BUGBOT_TRIGGER_SCRIPT_MARKER in command and bool(
        BUGBOT_RUN_BODY_PATTERN.search(command)
    )


def _reviewer_trigger(command: str) -> tuple[str, str] | None:
    """Return the reviewer token and label a scoped command triggers.

    Args:
        command: The Bash command text carrying the gate's sentinel marker.

    Returns:
        The matched reviewer's CLI token paired with its display label, or
        None when the command matches neither the Copilot review-request
        shape nor the Bugbot rerun-comment shape.
    """
    if _matches_copilot_trigger(command):
        return COPILOT_REVIEWER_TOKEN, COPILOT_REVIEWER_LABEL
    if _matches_bugbot_trigger(command):
        return BUGBOT_REVIEWER_TOKEN, BUGBOT_REVIEWER_LABEL
    return None


def _resolve_availability_script_path() -> Path:
    override_path = os.environ.get(AVAILABILITY_SCRIPT_PATH_ENV_VAR_NAME, "")
    if override_path:
        return Path(override_path)
    plugin_root = Path(__file__).resolve().parents[2]
    return plugin_root / AVAILABILITY_SCRIPT_RELATIVE_PATH


def _probe_reviewer_availability(reviewer_token: str) -> tuple[bool, str]:
    """Run the shared availability script for a reviewer and report the outcome.

    Args:
        reviewer_token: The reviewer's CLI token (copilot or bugbot) passed to
            the availability script's --reviewer flag.

    Returns:
        A pair of (is_available, detail_text). is_available is True when the
        script reports the reviewer available. detail_text carries the script's combined stdout and
        stderr for the deny message. A missing script, a timeout, or an
        OS-level failure to launch the script reports available (fail open)
        with a detail explaining why the check could not run.
    """
    script_path = _resolve_availability_script_path()
    if not script_path.is_file():
        return True, f"availability script not found at {script_path}"
    try:
        completed_process = subprocess.run(
            [sys.executable, str(script_path), AVAILABILITY_REVIEWER_FLAG, reviewer_token],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=AVAILABILITY_SCRIPT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as availability_error:
        return True, f"availability script failed to run: {availability_error}"
    availability_detail_text = (completed_process.stdout + completed_process.stderr).strip()
    return completed_process.returncode == AVAILABILITY_AVAILABLE_EXIT_CODE, availability_detail_text


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    if not isinstance(hook_input, dict):
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    if tool_name != BASH_TOOL_NAME:
        sys.exit(0)

    tool_input = hook_input.get("tool_input", {})
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not command or GATE_SENTINEL_MARKER not in command:
        sys.exit(0)

    reviewer_trigger = _reviewer_trigger(command)
    if reviewer_trigger is None:
        sys.exit(0)
    reviewer_token, reviewer_label = reviewer_trigger

    is_available, availability_detail = _probe_reviewer_availability(reviewer_token)
    if is_available:
        sys.exit(0)

    deny_reason = DENY_REASON_TEMPLATE.format(
        reviewer_label=reviewer_label, availability_detail=availability_detail
    )
    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason,
        }
    }
    log_hook_block(
        calling_hook_name="reviewer_spawn_gate.py",
        hook_event="PreToolUse",
        block_reason=deny_reason,
        tool_name=tool_name,
        offending_input_preview=command,
    )
    print(json.dumps(deny_payload))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
