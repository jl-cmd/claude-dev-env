#!/usr/bin/env python3
"""PreToolUse hook: blocks an agent-definition write that pins a concrete model.

An agent `.md` file under `packages/claude-dev-env/agents/` (or the installed
`~/.claude/agents/`) opens with YAML frontmatter. The `model` key either is
absent or reads `inherit` — the caller supplies a concrete model on every spawn,
so a definition never pins one::

    ok:   model: inherit
    ok:   <no model key at all>
    flag: model: opus       <- pinned concrete model, caller cannot override

The pin question is read by the shared `hooks_constants.agent_model_pin_detection`
helpers, which the agent frontmatter test suite imports too, so the two surfaces
cannot drift. Those helpers carry no YAML runtime dependency, so hosting this hook
natively on the dispatcher leaves the dispatcher loadable on a stdlib-only Python.
For an Edit or MultiEdit the hook reconstructs the post-edit file content before
reading the frontmatter, so an edit that flips `model: inherit` to `model: opus`
still blocks even when the payload fragment alone would hide it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import _path_setup  # noqa: F401

from hooks_constants.agent_model_pin_blocker_constants import (
    ALL_PIN_GATED_TOOL_NAMES,
    CALLING_HOOK_NAME,
    DENY_ADDITIONAL_CONTEXT,
    DENY_SYSTEM_MESSAGE,
)
from hooks_constants.agent_model_pin_detection import (
    extract_frontmatter_block,
    is_agent_definition_path,
    pinned_model_value,
)
from hooks_constants.hook_block_logger import log_hook_block
from hooks_constants.multi_edit_reconstruction import apply_edits, edits_for_tool
from hooks_constants.pre_tool_use_dispatcher_constants import (
    DENY_DECISION,
    HOOK_EVENT_NAME,
    WRITE_TOOL_NAME,
)
from hooks_constants.pre_tool_use_stdin import (
    read_hook_input_dictionary_from_stdin,
)


def _string_value(raw_value: object) -> str:
    """Return the value when it is a string, else an empty string."""
    return raw_value if isinstance(raw_value, str) else ""


def _read_existing_file(file_path: str) -> str:
    """Return the current on-disk text of a file, or empty when it cannot be read.

    An unreadable path (missing, permission-denied) and a non-UTF-8 file both
    yield empty text, so the reconstruction never raises out of the hook.
    """
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _candidate_content(
    tool_name: str, all_tool_input_fields: dict[str, object], file_path: str
) -> str:
    """Return the text a Write/Edit/MultiEdit payload would leave on disk.

    A Write carries the whole file in ``content``. An Edit or MultiEdit replays
    its ``old_string`` -> ``new_string`` replacements over the current file, so
    the frontmatter check reads the post-edit content rather than the fragment.
    """
    if tool_name == WRITE_TOOL_NAME:
        return _string_value(all_tool_input_fields.get("content"))
    existing_content = _read_existing_file(file_path)
    all_edits = edits_for_tool(tool_name, all_tool_input_fields)
    return apply_edits(existing_content, all_edits)


def _pin_deny_reason(file_path: str, pinned_model: str) -> str:
    """Return the deny-reason text for an agent file that pins a concrete model."""
    return (
        f"{file_path} pins a concrete model ({pinned_model}) in frontmatter. An "
        "agent definition omits the model key or sets model: inherit, so the "
        "caller supplies the model on every spawn."
    )


def evaluate(payload_by_key: dict[str, object]) -> str | None:
    """Decide whether a Write/Edit/MultiEdit pins a concrete model in an agent file.

    Gates on the tool name and the agent-definition path shape, reconstructs the
    post-edit content, reads its frontmatter, and denies when the last model line
    names a concrete model — quoting that value in the reason.
    """
    tool_name = _string_value(payload_by_key.get("tool_name"))
    if tool_name not in ALL_PIN_GATED_TOOL_NAMES:
        return None
    raw_tool_input = payload_by_key.get("tool_input", {})
    tool_input = raw_tool_input if isinstance(raw_tool_input, dict) else {}
    file_path = _string_value(tool_input.get("file_path"))
    if not file_path or not is_agent_definition_path(file_path):
        return None
    frontmatter_block = extract_frontmatter_block(
        _candidate_content(tool_name, tool_input, file_path)
    )
    if frontmatter_block is None:
        return None
    pinned_model = pinned_model_value(frontmatter_block)
    return _pin_deny_reason(file_path, pinned_model) if pinned_model is not None else None


def build_deny_payload(deny_reason: str) -> dict[str, object]:
    """Build the full deny payload for a deny-reason string.

    Args:
        deny_reason: The permissionDecisionReason text for the denial.

    Returns:
        The deny payload dictionary the hook serializes to stdout.
    """
    log_hook_block(
        calling_hook_name=CALLING_HOOK_NAME,
        hook_event=HOOK_EVENT_NAME,
        block_reason=deny_reason,
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "permissionDecision": DENY_DECISION,
            "permissionDecisionReason": deny_reason,
            "additionalContext": DENY_ADDITIONAL_CONTEXT,
        },
        "systemMessage": DENY_SYSTEM_MESSAGE,
        "suppressOutput": True,
    }


def main() -> None:
    """Read stdin once and deny a Write/Edit/MultiEdit that pins a model."""
    payload_dictionary = read_hook_input_dictionary_from_stdin()
    deny_reason = evaluate(payload_dictionary) if payload_dictionary is not None else None
    if deny_reason is not None:
        sys.stdout.write(json.dumps(build_deny_payload(deny_reason)) + "\n")
        sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
