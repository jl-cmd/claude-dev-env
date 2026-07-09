#!/usr/bin/env python3
"""PreToolUse dispatcher that hosts the Bash and PowerShell blocking hook chains.

Reads the tool payload from stdin once, selects the hosted hooks applicable to
the payload's tool name, runs each hook in-process via the shared hosted-hook
runner, aggregates deny/ask/allow decisions with deny>ask>allow precedence, and
emits one decision (carrying updatedInput when a rewriter allowed a rewrite, and
systemMessage / additionalContext / suppressOutput when hosted hooks set them).

A single hosted hook crash fails open: it contributes no decision and does not
stop the remaining hooks, matching a standalone hook whose uncaught exception
exits nonzero without blocking the tool call.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import _path_setup  # noqa: F401

from hooks_constants.bash_pre_tool_use_dispatcher_constants import (
    ALL_BASH_HOSTED_HOOK_ENTRIES,
    ALLOW_DECISION,
    ASK_DECISION,
    CONTEXT_JOIN_SEPARATOR,
    DENY_DECISION,
    HOOK_EVENT_NAME,
    REASON_JOIN_SEPARATOR,
    BashHostedHookEntry,
)
from hooks_constants.hosted_hook_runner import HostedHookRun, run_hook_capturing_output
from hooks_constants.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin

_PERMISSION_DECISION_KEY = "permissionDecision"
_PERMISSION_REASON_KEY = "permissionDecisionReason"
_HOOK_SPECIFIC_OUTPUT_KEY = "hookSpecificOutput"
_UPDATED_INPUT_KEY = "updatedInput"
_SYSTEM_MESSAGE_KEY = "systemMessage"
_ADDITIONAL_CONTEXT_KEY = "additionalContext"
_SUPPRESS_OUTPUT_KEY = "suppressOutput"


@dataclass
class BashDispatcherDecision:
    """Aggregated outcome across the Bash/PowerShell hosted-hook chain.

    Attributes:
        decision: The winning permission outcome (deny, ask, allow), or empty
            when no hosted hook emitted an outcome.
        reasons: Deny or ask reasons collected from deciding hooks, in run order.
        updated_input: The rewritten tool_input from an allowing rewriter, or
            None when no allow carried an updatedInput.
        all_system_messages: Top-level systemMessage texts from hosted hooks.
        all_additional_context: hookSpecificOutput.additionalContext texts.
        should_suppress_output: True when any hosted hook set suppressOutput.
    """

    decision: str
    reasons: list[str] = field(default_factory=list)
    updated_input: dict[str, object] | None = None
    all_system_messages: list[str] = field(default_factory=list)
    all_additional_context: list[str] = field(default_factory=list)
    should_suppress_output: bool = False


@dataclass
class _ParsedHookDecision:
    """Fields parsed from one hosted hook's stdout."""

    decision: str
    reason: str
    updated_input: dict[str, object] | None
    system_message: str
    additional_context: str
    should_suppress_output: bool


def select_applicable_entries(tool_name: str) -> list[BashHostedHookEntry]:
    """Return the ordered hosted-hook entries that apply to tool_name."""
    return [
        each_entry
        for each_entry in ALL_BASH_HOSTED_HOOK_ENTRIES
        if tool_name in each_entry.applicable_tool_names
    ]


def _empty_parsed_hook_decision() -> _ParsedHookDecision:
    """Return a non-deciding parse result with empty supplementary fields."""
    return _ParsedHookDecision(
        decision="",
        reason="",
        updated_input=None,
        system_message="",
        additional_context="",
        should_suppress_output=False,
    )


def _parse_hook_stdout(stdout_text: str) -> _ParsedHookDecision:
    """Parse one hook's stdout into a decision, reason, rewrite, and context."""
    stripped_text = stdout_text.strip()
    if not stripped_text:
        return _empty_parsed_hook_decision()
    try:
        parsed_output = json.loads(stripped_text)
    except json.JSONDecodeError:
        return _empty_parsed_hook_decision()
    if not isinstance(parsed_output, dict):
        return _empty_parsed_hook_decision()
    hook_specific = parsed_output.get(_HOOK_SPECIFIC_OUTPUT_KEY, {})
    if not isinstance(hook_specific, dict):
        return _empty_parsed_hook_decision()
    raw_decision = hook_specific.get(_PERMISSION_DECISION_KEY, "")
    decision = raw_decision if isinstance(raw_decision, str) else ""
    raw_reason = hook_specific.get(_PERMISSION_REASON_KEY, "")
    reason = raw_reason if isinstance(raw_reason, str) else ""
    raw_updated_input = hook_specific.get(_UPDATED_INPUT_KEY)
    updated_input = raw_updated_input if isinstance(raw_updated_input, dict) else None
    raw_system_message = parsed_output.get(_SYSTEM_MESSAGE_KEY, "")
    system_message = raw_system_message if isinstance(raw_system_message, str) else ""
    raw_additional_context = hook_specific.get(_ADDITIONAL_CONTEXT_KEY, "")
    additional_context = (
        raw_additional_context if isinstance(raw_additional_context, str) else ""
    )
    should_suppress_output = parsed_output.get(_SUPPRESS_OUTPUT_KEY) is True
    return _ParsedHookDecision(
        decision=decision,
        reason=reason,
        updated_input=updated_input,
        system_message=system_message,
        additional_context=additional_context,
        should_suppress_output=should_suppress_output,
    )


def aggregate_bash_hook_results(
    all_runs: list[HostedHookRun],
) -> BashDispatcherDecision:
    """Aggregate hosted-hook runs into one deny>ask>allow decision.

    Crashed hooks fail open: they contribute no decision. Reasons are collected
    from deny and ask outputs. When the winning decision is allow, the first
    non-empty updatedInput among allow results is carried through so rewriters
    keep their contract. systemMessage, additionalContext, and suppressOutput
    from every non-crashed hook are preserved so silent deny shapes (for example
    destructive_command_blocker's gh-redirect deny) match standalone emission.
    """
    all_parsed: list[_ParsedHookDecision] = []
    for each_run in all_runs:
        if each_run.did_crash:
            continue
        all_parsed.append(_parse_hook_stdout(each_run.captured_stdout))

    decision_precedence = (DENY_DECISION, ASK_DECISION, ALLOW_DECISION)
    winning_decision = ""
    for each_candidate in decision_precedence:
        if any(each_parsed.decision == each_candidate for each_parsed in all_parsed):
            winning_decision = each_candidate
            break

    if not winning_decision:
        return BashDispatcherDecision(decision="")

    all_reasons = [
        each_parsed.reason
        for each_parsed in all_parsed
        if each_parsed.decision in (DENY_DECISION, ASK_DECISION) and each_parsed.reason
    ]
    updated_input: dict[str, object] | None = None
    if winning_decision == ALLOW_DECISION:
        for each_parsed in all_parsed:
            if each_parsed.decision == ALLOW_DECISION and each_parsed.updated_input is not None:
                updated_input = each_parsed.updated_input
                break

    all_system_messages = [
        each_parsed.system_message for each_parsed in all_parsed if each_parsed.system_message
    ]
    all_additional_context = [
        each_parsed.additional_context
        for each_parsed in all_parsed
        if each_parsed.additional_context
    ]
    should_suppress_output = any(
        each_parsed.should_suppress_output for each_parsed in all_parsed
    )

    return BashDispatcherDecision(
        decision=winning_decision,
        reasons=all_reasons,
        updated_input=updated_input,
        all_system_messages=all_system_messages,
        all_additional_context=all_additional_context,
        should_suppress_output=should_suppress_output,
    )


def _resolve_hook_script_path(relative_path: str) -> str:
    """Resolve a hooks/-relative path to an absolute script path."""
    hooks_root = Path(__file__).resolve().parent.parent
    return str(hooks_root / relative_path)


def _emit_decision(decision: BashDispatcherDecision) -> None:
    """Write one PreToolUse permission payload to stdout when an outcome exists."""
    if not decision.decision:
        return
    hook_specific: dict[str, object] = {
        "hookEventName": HOOK_EVENT_NAME,
        _PERMISSION_DECISION_KEY: decision.decision,
    }
    if decision.reasons:
        hook_specific[_PERMISSION_REASON_KEY] = REASON_JOIN_SEPARATOR.join(decision.reasons)
    if decision.decision == ALLOW_DECISION and decision.updated_input is not None:
        hook_specific[_UPDATED_INPUT_KEY] = decision.updated_input
    if decision.all_additional_context:
        hook_specific[_ADDITIONAL_CONTEXT_KEY] = CONTEXT_JOIN_SEPARATOR.join(
            decision.all_additional_context
        )
    payload: dict[str, object] = {_HOOK_SPECIFIC_OUTPUT_KEY: hook_specific}
    if decision.all_system_messages:
        payload[_SYSTEM_MESSAGE_KEY] = CONTEXT_JOIN_SEPARATOR.join(decision.all_system_messages)
    if decision.should_suppress_output:
        payload[_SUPPRESS_OUTPUT_KEY] = True
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def dispatch(payload_text: str, tool_name: str) -> None:
    """Run every applicable hosted hook and emit the aggregated decision."""
    applicable_entries = select_applicable_entries(tool_name)
    all_runs: list[HostedHookRun] = []
    for each_entry in applicable_entries:
        script_path = _resolve_hook_script_path(each_entry.script_relative_path)
        hook_run = run_hook_capturing_output(script_path, payload_text)
        all_runs.append(hook_run)
    aggregated_decision = aggregate_bash_hook_results(all_runs)
    _emit_decision(aggregated_decision)


def main() -> None:
    """Read stdin once and dispatch the Bash/PowerShell hosted-hook chain."""
    payload_dictionary = read_hook_input_dictionary_from_stdin()
    if payload_dictionary is None:
        sys.exit(0)

    payload_text = json.dumps(payload_dictionary)
    tool_name = payload_dictionary.get("tool_name", "")
    if not isinstance(tool_name, str) or not tool_name:
        sys.exit(0)

    dispatch(payload_text, tool_name)
    sys.exit(0)


if __name__ == "__main__":
    main()
