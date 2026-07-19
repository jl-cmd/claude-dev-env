#!/usr/bin/env python3
"""PreToolUse hook: blocks an agent-definition Write/Edit that pins a concrete model.

An agent `.md` file under `packages/claude-dev-env/agents/` (or the installed
`~/.claude/agents/`) opens with YAML frontmatter. The `model` key either is
absent or reads `inherit` — the caller supplies a concrete model on every spawn,
so a definition never pins one::

    ok:   model: inherit
    ok:   <no model key at all>
    flag: model: opus       <- pinned concrete model, caller cannot override

`frontmatter_pins_concrete_model` is the shared pin detector: the hook calls it
to decide a write, and the agent frontmatter test suite imports the same function
so the two surfaces cannot drift.
"""

from __future__ import annotations

import json
import re
import sys

import _path_setup  # noqa: F401
import yaml

from hooks_constants.agent_model_pin_blocker_constants import (
    ALL_PIN_GATED_TOOL_NAMES,
    CALLING_HOOK_NAME,
    DENY_ADDITIONAL_CONTEXT,
    DENY_SYSTEM_MESSAGE,
    EDIT_TEXT_JOIN_SEPARATOR,
    FRONTMATTER_FENCE,
    FRONTMATTER_SEGMENT_COUNT,
    INHERIT_MODEL_VALUE,
    INSTALLED_AGENTS_PATH_FRAGMENT,
    MARKDOWN_EXTENSION,
    MODEL_FRONTMATTER_KEY,
    PACKAGE_AGENTS_PATH_FRAGMENT,
    TOP_LEVEL_MODEL_LINE_PATTERN,
)
from hooks_constants.hook_block_logger import log_hook_block
from hooks_constants.pre_tool_use_dispatcher_constants import (
    DENY_DECISION,
    HOOK_EVENT_NAME,
)
from hooks_constants.pre_tool_use_stdin import (
    read_hook_input_dictionary_from_stdin,
)


def frontmatter_pins_concrete_model(frontmatter_block: str) -> bool:
    """Return whether a frontmatter block pins a concrete model.

    Isolates the top-level ``model:`` lines by a column-zero line scan, so a
    ``description`` carrying colon-laden example prose never confuses the read,
    then parses the last line (last-wins) with ``yaml.safe_load`` for the value::

        ok:   model: inherit   -> False
        ok:   model:           -> False (None, not a pin)
        flag: model: opus      -> True

    The comparison against ``inherit`` strips whitespace and ignores case. An
    unterminated quote raises ``yaml.YAMLError``.
    """
    all_model_lines = re.findall(
        TOP_LEVEL_MODEL_LINE_PATTERN, frontmatter_block, re.MULTILINE
    )
    if not all_model_lines:
        return False
    parsed_model_line = yaml.safe_load(all_model_lines[-1])
    declared_model = (
        parsed_model_line.get(MODEL_FRONTMATTER_KEY)
        if isinstance(parsed_model_line, dict)
        else None
    )
    if declared_model is None:
        return False
    return str(declared_model).strip().lower() != INHERIT_MODEL_VALUE


def is_agent_definition_path(file_path: str) -> bool:
    """Return whether a path is an agent-definition `.md` under an agents directory.

    Matches the package shape ``packages/claude-dev-env/agents/<name>.md`` and the
    installed shape ``~/.claude/agents/<name>.md``, across both slash directions.
    """
    normalized_path = file_path.replace("\\", "/")
    if not normalized_path.endswith(MARKDOWN_EXTENSION):
        return False
    return (
        PACKAGE_AGENTS_PATH_FRAGMENT in normalized_path
        or INSTALLED_AGENTS_PATH_FRAGMENT in normalized_path
    )


def _frontmatter_block(file_content: str) -> str | None:
    """Return the frontmatter block from file content, or None when there is none.

    Content that does not open with the fence carries no frontmatter, so a
    mid-edit fragment without an opening fence yields None.
    """
    if not file_content.lstrip().startswith(FRONTMATTER_FENCE):
        return None
    fence_segments = file_content.split(FRONTMATTER_FENCE, FRONTMATTER_SEGMENT_COUNT - 1)
    if len(fence_segments) < FRONTMATTER_SEGMENT_COUNT:
        return None
    return fence_segments[1]


def _string_value(raw_value: object) -> str:
    """Return the value when it is a string, else an empty string."""
    return raw_value if isinstance(raw_value, str) else ""


def _candidate_content(tool_name: str, all_tool_input_fields: dict[str, object]) -> str:
    """Return the text a Write/Edit/MultiEdit payload would place in the file.

    A Write carries the whole file in ``content``, an Edit the replacement in
    ``new_string``, and a MultiEdit the ``new_string`` of each edit joined.
    """
    if tool_name == "Write":
        return _string_value(all_tool_input_fields.get("content"))
    if tool_name == "Edit":
        return _string_value(all_tool_input_fields.get("new_string"))
    raw_edits = all_tool_input_fields.get("edits", [])
    if not isinstance(raw_edits, list):
        return ""
    all_new_strings = [
        _string_value(each_edit.get("new_string"))
        for each_edit in raw_edits
        if isinstance(each_edit, dict)
    ]
    return EDIT_TEXT_JOIN_SEPARATOR.join(all_new_strings)


def _deny_reason(file_path: str) -> str:
    """Return the deny-reason text for an agent file that pins a model."""
    return (
        f"{file_path} pins a concrete model in frontmatter. An agent definition "
        "omits the model key or sets model: inherit, so the caller supplies the "
        "model on every spawn."
    )


def evaluate(payload_by_key: dict[str, object]) -> str | None:
    """Decide whether a Write/Edit/MultiEdit pins a concrete model in an agent file.

    Gates on the tool name and the agent-definition path shape, then checks the
    candidate frontmatter block. A malformed block raises ``yaml.YAMLError``,
    which the hook catches to allow the write — a malformed block loads no agent
    and a mid-edit fragment must not be blocked.
    """
    tool_name = _string_value(payload_by_key.get("tool_name"))
    if tool_name not in ALL_PIN_GATED_TOOL_NAMES:
        return None
    raw_tool_input = payload_by_key.get("tool_input", {})
    tool_input = raw_tool_input if isinstance(raw_tool_input, dict) else {}
    file_path = _string_value(tool_input.get("file_path"))
    if not file_path or not is_agent_definition_path(file_path):
        return None
    frontmatter_block = _frontmatter_block(_candidate_content(tool_name, tool_input))
    if frontmatter_block is None:
        return None
    try:
        pins_model = frontmatter_pins_concrete_model(frontmatter_block)
    except yaml.YAMLError:
        return None
    return _deny_reason(file_path) if pins_model else None


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
