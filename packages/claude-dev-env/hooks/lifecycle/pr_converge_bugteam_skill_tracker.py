#!/usr/bin/env python3
"""PreToolUse hook: record formal bugteam Skill invocations into pr-converge state.

Companion to ``pr_converge_bugteam_enforcer``. On every
``Skill({skill: "bugteam"})`` invocation, this hook stamps
``$CLAUDE_JOB_DIR/pr-converge-state.json`` with
``bugteam_skill_invoked_at_head = current_head`` and
``bugteam_skill_invoked_at_tick = tick_count`` so the enforcer can confirm
the formal Skill fired this tick at the current HEAD before allowing any
follow-on clean-coder audit-shaped Agent spawn.

``qbug`` invocations are deliberately ignored — qbug is not an accepted
substitute for the formal bugteam Skill at Step 5.

The hook never blocks: it returns exit 0 in every branch so the Skill call
proceeds unchanged.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.pr_converge_bugteam_enforcer_constants import (  # noqa: E402
    BUGTEAM_SKILL_NAME,
    SKILL_TOOL_NAME,
    STATE_FIELD_BUGTEAM_SKILL_INVOKED_AT_HEAD,
    STATE_FIELD_BUGTEAM_SKILL_INVOKED_AT_TICK,
    STATE_FIELD_CURRENT_HEAD,
    STATE_FIELD_TICK_COUNT,
    STATE_FILE_ATOMIC_WRITE_SUFFIX,
    STATE_FILE_JSON_INDENT_SPACES,
)
from hooks_constants.pr_converge_bugteam_enforcer_state import (  # noqa: E402
    load_state_dictionary,
    resolve_state_path,
)


def _atomic_write_state(state_path: Path, state_by_field: dict[str, object]) -> None:
    """Serialize state to disk atomically via tempfile + rename.

    Args:
        state_path: Destination ``pr-converge-state.json`` path.
        state_by_field: Updated state mapping each field name to its value.
    """
    parent_directory = state_path.parent
    parent_directory.mkdir(parents=True, exist_ok=True)
    encoded_text = json.dumps(state_by_field, indent=STATE_FILE_JSON_INDENT_SPACES, sort_keys=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(parent_directory),
        delete=False,
        suffix=STATE_FILE_ATOMIC_WRITE_SUFFIX,
    ) as temporary_handle:
        temporary_handle.write(encoded_text)
        temporary_path = Path(temporary_handle.name)
    try:
        os.replace(str(temporary_path), str(state_path))
    except OSError:
        Path(temporary_path).unlink(missing_ok=True)
        raise


def _emit_missing_state_warning(output_stream: TextIO) -> None:
    """Write the missing-state warning to the provided stream.

    Args:
        output_stream: Writable text stream — production code passes
            ``sys.stderr``; tests pass a ``StringIO`` to capture the message.
    """
    output_stream.write(
        "pr_converge_bugteam_skill_tracker: state file lacks current_head or "
        "tick_count; bugteam invocation NOT recorded\n"
    )
    output_stream.flush()


def _record_bugteam_skill_invocation(
    state_by_field: dict[str, object],
) -> dict[str, object] | None:
    """Return a copy of state with bugteam-Skill invocation fields stamped, or None on no-op.

    The two stamp fields are owned exclusively by this tracker. Concurrent
    writes from the orchestrator never touch them, so the read-modify-write
    window cannot lose an orchestrator update on these specific keys.

    When ``current_head`` (str) or ``tick_count`` (int) is missing or wrong-typed,
    the function emits a stderr warning via ``_emit_missing_state_warning`` and
    returns ``None`` so the caller skips the disk write entirely. Skipping the
    no-op write narrows the read-modify-write window against the orchestrator —
    concurrent updates to non-stamp fields (``phase``, ``tick_count``, etc.)
    cannot be silently lost by a tracker rewrite that changes nothing.

    Args:
        state_by_field: Existing pr-converge state mapping each field name to
            its value.

    Returns:
        New dictionary identical to ``state_by_field`` plus
        ``bugteam_skill_invoked_at_head`` set to ``current_head`` and
        ``bugteam_skill_invoked_at_tick`` set to ``tick_count`` when both
        source fields are present and well-typed; ``None`` when either source
        field is missing or wrong-typed, signaling the caller to skip the
        atomic write.
    """
    current_head = state_by_field.get(STATE_FIELD_CURRENT_HEAD)
    current_tick = state_by_field.get(STATE_FIELD_TICK_COUNT)
    if not isinstance(current_head, str) or not isinstance(current_tick, int):
        _emit_missing_state_warning(sys.stderr)
        return None
    updated_state: dict[str, object] = dict(state_by_field)
    updated_state[STATE_FIELD_BUGTEAM_SKILL_INVOKED_AT_HEAD] = current_head
    updated_state[STATE_FIELD_BUGTEAM_SKILL_INVOKED_AT_TICK] = current_tick
    return updated_state


def _is_formal_bugteam_skill_invocation(payload_by_field: dict[str, object]) -> bool:
    """Return True when this hook invocation matches the formal bugteam Skill.

    Args:
        payload_by_field: The full PreToolUse hook payload (already JSON-parsed),
            keyed by top-level field name.

    Returns:
        True when ``tool_name == "Skill"`` and ``tool_input["skill"]
        == "bugteam"``. Returns False for qbug and every other skill.
    """
    if payload_by_field.get("tool_name", "") != SKILL_TOOL_NAME:
        return False
    tool_input = payload_by_field.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return False
    return tool_input.get("skill", "") == BUGTEAM_SKILL_NAME


def _emit_state_write_error(state_write_error: OSError, output_stream: TextIO) -> None:
    """Write the state-write failure message to the provided stream.

    Args:
        state_write_error: The OSError raised by ``_atomic_write_state``.
        output_stream: Writable text stream — production code passes
            ``sys.stderr``; tests pass a ``StringIO`` to capture the message.
    """
    output_stream.write(
        f"pr_converge_bugteam_skill_tracker: state write failed; "
        f"stamp not recorded: {state_write_error}\n"
    )
    output_stream.flush()


def main() -> None:
    """Tracker entry point for the PreToolUse:Skill hook.

    Reads the PreToolUse payload from stdin, records a formal
    ``Skill({skill: "bugteam"})`` invocation in the pr-converge state file,
    and always returns 0 — including on a state-write failure, since a
    non-zero PreToolUse exit would block the very Skill invocation this
    hook exists to record. State-write failures are surfaced via
    ``_emit_state_write_error`` to stderr so the operator still sees the
    protocol-corruption signal.
    """
    try:
        hook_payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    if not isinstance(hook_payload, dict):
        return
    if not _is_formal_bugteam_skill_invocation(hook_payload):
        return
    state_path = resolve_state_path()
    if state_path is None:
        return
    parsed_state = load_state_dictionary(state_path)
    if parsed_state is None:
        return
    updated_state = _record_bugteam_skill_invocation(parsed_state)
    if updated_state is None:
        return
    try:
        _atomic_write_state(state_path, updated_state)
    except OSError as state_write_error:
        _emit_state_write_error(state_write_error, sys.stderr)
        return
    return


if __name__ == "__main__":
    main()
