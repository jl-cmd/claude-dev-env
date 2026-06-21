#!/usr/bin/env python3
"""PreToolUse hook: enforce formal bugteam Skill at Step 5 BUGTEAM ticks.

The pr-converge loop's Step 5 BUGTEAM contract requires the formal
``Skill({skill: "bugteam", args: "<PR URL>"})`` invocation per tick.
Substituting an ad-hoc ``Agent({subagent_type: "clean-coder", ...})`` audit
call returns a "converged" verdict without writing the artifact that
``check_convergence.py``'s ``bugteam_clean_at`` gate reads, so the loop later
hits ``gh pr ready`` and fails structurally with no formal review on the PR.

The companion tracker hook
(``pr_converge_bugteam_skill_tracker.py``) records every formal Skill
invocation. This enforcer reads the recorded HEAD and tick and denies any
clean-coder audit-shaped Agent call that has not first been preceded by the
formal Skill at the same HEAD and tick.

``qbug`` is NOT an accepted substitute; only the ``bugteam`` skill records
the gate artifact, and the tracker deliberately ignores ``qbug`` invocations.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.pr_converge_bugteam_enforcer_constants import (  # noqa: E402
    AGENT_TOOL_NAME,
    ALL_AUDIT_PROMPT_SUBSTRINGS,
    BUGTEAM_PHASE,
    CLEAN_CODER_SUBAGENT_TYPE,
    ENFORCER_CORRECTIVE_MESSAGE,
    STATE_FIELD_BUGTEAM_SKILL_INVOKED_AT_HEAD,
    STATE_FIELD_BUGTEAM_SKILL_INVOKED_AT_TICK,
    STATE_FIELD_CURRENT_HEAD,
    STATE_FIELD_PHASE,
    STATE_FIELD_TICK_COUNT,
)
from hooks_constants.pr_converge_bugteam_enforcer_state import (  # noqa: E402
    load_state_dictionary,
    resolve_state_path,
)
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)


def _prompt_is_audit_shaped(agent_prompt: str) -> bool:
    """Return True when the Agent prompt looks like an audit substitute.

    Args:
        agent_prompt: The ``prompt`` field of the Agent tool_input.

    Returns:
        True when any audit-shaped substring appears in the prompt
        (case-insensitive); False for fix-only or unrelated prompts.
    """
    lowercased_prompt = agent_prompt.lower()
    return any(
        each_substring in lowercased_prompt for each_substring in ALL_AUDIT_PROMPT_SUBSTRINGS
    )


def _has_formal_skill_fired_this_tick(state_by_field: dict[str, object]) -> bool:
    """Return True when the bugteam Skill registered at current HEAD and tick.

    Args:
        state_by_field: Parsed pr-converge state.json mapping each field name
            to its recorded value.

    Returns:
        True when both ``bugteam_skill_invoked_at_head`` matches
        ``current_head`` and ``bugteam_skill_invoked_at_tick`` matches
        ``tick_count``; False when either is missing, stale, or carries a
        type that violates state-schema.md (head must be ``str``, tick must
        be a non-bool ``int``) — type-invalid values fail closed so the
        enforcer rejects corrupted state.
    """
    invoked_head = state_by_field.get(STATE_FIELD_BUGTEAM_SKILL_INVOKED_AT_HEAD)
    current_head = state_by_field.get(STATE_FIELD_CURRENT_HEAD)
    invoked_tick = state_by_field.get(STATE_FIELD_BUGTEAM_SKILL_INVOKED_AT_TICK)
    current_tick = state_by_field.get(STATE_FIELD_TICK_COUNT)
    if not isinstance(invoked_head, str) or not isinstance(current_head, str):
        return False
    if invoked_head != current_head:
        return False
    if isinstance(invoked_tick, bool) or isinstance(current_tick, bool):
        return False
    if not isinstance(invoked_tick, int) or not isinstance(current_tick, int):
        return False
    return invoked_tick == current_tick


def _should_block(payload_by_field: dict[str, object]) -> bool:
    """Return True when the Agent call is a BUGTEAM-phase Skill substitution.

    Args:
        payload_by_field: The full PreToolUse hook payload (already JSON-parsed),
            keyed by top-level field name.

    Returns:
        True when every gating condition holds: tool is Agent, subagent_type
        is clean-coder, prompt is audit-shaped, pr-converge state.json exists
        with phase BUGTEAM, and the formal bugteam Skill has NOT been
        recorded at the current HEAD and tick. False otherwise.
    """
    if payload_by_field.get("tool_name", "") != AGENT_TOOL_NAME:
        return False
    tool_input = payload_by_field.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return False
    if tool_input.get("subagent_type", "") != CLEAN_CODER_SUBAGENT_TYPE:
        return False
    agent_prompt = tool_input.get("prompt", "")
    if not isinstance(agent_prompt, str):
        return False
    if not _prompt_is_audit_shaped(agent_prompt):
        return False
    state_path = resolve_state_path()
    if state_path is None:
        return False
    parsed_state = load_state_dictionary(state_path)
    if parsed_state is None:
        return False
    if parsed_state.get(STATE_FIELD_PHASE) != BUGTEAM_PHASE:
        return False
    return not _has_formal_skill_fired_this_tick(parsed_state)


def _emit_deny_payload(output_stream: TextIO) -> None:
    """Write the PreToolUse deny payload to the provided stream.

    Args:
        output_stream: Writable text stream — production code passes
            ``sys.stdout``; tests pass a ``StringIO`` to capture the JSON.
    """
    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": ENFORCER_CORRECTIVE_MESSAGE,
        }
    }
    output_stream.write(json.dumps(deny_payload) + "\n")
    output_stream.flush()


def main() -> None:
    hook_payload = read_hook_input_dictionary_from_stdin()
    if hook_payload is None:
        sys.exit(0)
    if not _should_block(hook_payload):
        sys.exit(0)
    _emit_deny_payload(sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
