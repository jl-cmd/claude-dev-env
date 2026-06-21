#!/usr/bin/env python3
"""PreToolUse dispatcher that hosts Write, Edit, and MultiEdit blocking hooks.

Reads the tool payload from stdin once, selects the hosted hooks applicable to
the payload's tool name, runs each hook in-process via runpy in the fixed order
declared in the constants module, aggregates the results, and emits one deny
decision when any hook denied (carrying every denying reason) or exits zero to
allow.

The per-hook coverage matrix:
- Write  -> Group A (10 hooks) + Group B (5 hooks) = 15 hooks
- Edit   -> Group A (10 hooks) + Group B (5 hooks) = 15 hooks
- MultiEdit -> Group B only (5 hooks)
"""

from __future__ import annotations

import io
import json
import runpy
import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from plain_language_blocker import evaluate as evaluate_plain_language  # noqa: E402
from state_description_blocker import evaluate as evaluate_state_description  # noqa: E402

from hooks_constants.pre_tool_use_dispatcher_constants import (  # noqa: E402
    ALL_HOSTED_HOOK_ENTRIES,
    BLOCKING_CRASH_EXIT_CODE,
    DENY_DECISION,
    EXIT_CODE_TWO_DENY_REASON,
    HOOK_EVENT_NAME,
    PLAIN_LANGUAGE_BLOCKER_MODULE_NAME,
    STATE_DESCRIPTION_BLOCKER_MODULE_NAME,
    HostedHookEntry,
)
from hooks_constants.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin  # noqa: E402

NativeEvaluator = Callable[[dict[str, object]], str | None]


@dataclass
class HostedHookResult:
    """Outcome of running one hosted hook inside the dispatcher process.

    Attributes:
        exit_code: The exit code the hook raised via SystemExit, or 0 when the
            hook returned without raising.
        captured_stdout: The text the hook wrote to stdout during its run.
        did_crash: True when the hook raised a non-SystemExit exception.
        is_blocking: True when this hook's crash surfaces a blocking signal.
    """

    exit_code: int
    captured_stdout: str
    did_crash: bool = field(default=False)
    is_blocking: bool = field(default=True)


def _log_hook_crash(hook_script_path: str, error: Exception) -> None:
    """Write a one-line crash summary to stderr.

    Args:
        hook_script_path: The absolute path of the hook that crashed.
        error: The exception the hook raised.
    """
    formatted_traceback = traceback.format_exc().strip()
    last_line = formatted_traceback.splitlines()[-1] if formatted_traceback else str(error)
    error_type_name = type(error).__name__
    sys.stderr.write(
        f"[dispatcher] crash in {hook_script_path}: {error_type_name}: {error} | {last_line}\n"
    )
    sys.stderr.flush()


def run_hosted_hook(
    hook_script_path: str,
    payload_text: str,
    is_blocking: bool,
) -> HostedHookResult:
    """Run one hosted hook in-process and return its outcome.

    Sets stdin to a fresh stream over payload_text, captures stdout into a
    buffer, runs the hook via runpy under __main__, catches SystemExit to read
    the exit code without ending the dispatcher, and catches a non-SystemExit
    exception to log the crash and classify it. Always restores stdin and
    stdout in the finally block.

    Args:
        hook_script_path: Absolute path of the hook script to run.
        payload_text: The raw payload text to replay as the hook's stdin.
        is_blocking: Whether a crash from this hook surfaces a blocking signal.

    Returns:
        A HostedHookResult carrying the exit code, captured stdout, crash flag,
        and blocking classification.
    """
    original_stdin = sys.stdin
    original_stdout = sys.stdout
    captured_output = io.StringIO()
    hook_exit_code = 0
    hook_did_crash = False

    try:
        sys.stdin = io.StringIO(payload_text)
        sys.stdout = captured_output
        runpy.run_path(hook_script_path, run_name="__main__")
    except SystemExit as exit_signal:
        raw_code = exit_signal.code
        hook_exit_code = raw_code if isinstance(raw_code, int) else 0
    except Exception as error:
        _log_hook_crash(hook_script_path, error)
        hook_did_crash = True
        hook_exit_code = BLOCKING_CRASH_EXIT_CODE if is_blocking else 0
    finally:
        sys.stdin = original_stdin
        sys.stdout = original_stdout

    return HostedHookResult(
        exit_code=hook_exit_code,
        captured_stdout=captured_output.getvalue(),
        did_crash=hook_did_crash,
        is_blocking=is_blocking,
    )


def _build_native_deny_stdout(deny_reason: str) -> str:
    """Build the deny JSON a hosted hook would write for a deny-reason string.

    Produces the same hookSpecificOutput deny shape the standalone hook script
    writes, so the aggregator parses a native result identically to a runpy
    result.

    Args:
        deny_reason: The permissionDecisionReason text from the native evaluator.

    Returns:
        The JSON text a hosted hook would write to stdout for this denial.
    """
    deny_payload: dict[str, object] = {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "permissionDecision": DENY_DECISION,
            "permissionDecisionReason": deny_reason,
        }
    }
    return json.dumps(deny_payload)


def run_native_hook(
    native_evaluator: NativeEvaluator,
    payload_by_key: dict[str, object],
    is_blocking: bool,
) -> HostedHookResult:
    """Run one hosted hook's native evaluator in-process and return its outcome.

    Calls the evaluator directly with the payload dict, builds the deny JSON for
    a deny-reason return so the aggregator treats it identically to a runpy
    result, and catches a non-SystemExit crash to log and classify it.

    Args:
        native_evaluator: The hook's evaluate function taking the payload dict
            and returning a deny-reason string or None.
        payload_by_key: The parsed payload dict to pass to the evaluator.
        is_blocking: Whether a crash from this hook surfaces a blocking signal.

    Returns:
        A HostedHookResult carrying the captured deny JSON (empty when allowed),
        the crash flag, and the blocking classification.
    """
    try:
        deny_reason = native_evaluator(payload_by_key)
    except Exception as error:
        _log_hook_crash(native_evaluator.__module__, error)
        return HostedHookResult(
            exit_code=BLOCKING_CRASH_EXIT_CODE if is_blocking else 0,
            captured_stdout="",
            did_crash=True,
            is_blocking=is_blocking,
        )

    captured_stdout = _build_native_deny_stdout(deny_reason) if deny_reason is not None else ""
    return HostedHookResult(
        exit_code=0,
        captured_stdout=captured_stdout,
        did_crash=False,
        is_blocking=is_blocking,
    )


def _parse_deny_from_hook_output(hook_output_text: str) -> tuple[bool, str, str]:
    """Parse one hook's stdout for a deny decision.

    Args:
        hook_output_text: The text the hook wrote to stdout.

    Returns:
        A (is_deny, deny_reason, additional_context) triple. is_deny is True
        when the hook output carries a permissionDecision of deny.
        deny_reason is the permissionDecisionReason text when is_deny is True.
        additional_context is any systemMessage or other hook output text that
        is not the deny signal itself.
    """
    stripped_text = hook_output_text.strip()
    if not stripped_text:
        return False, "", ""
    try:
        parsed_output = json.loads(stripped_text)
    except json.JSONDecodeError:
        return False, "", stripped_text
    if not isinstance(parsed_output, dict):
        return False, "", stripped_text
    hook_specific = parsed_output.get("hookSpecificOutput", {})
    if not isinstance(hook_specific, dict):
        return False, "", stripped_text
    is_deny = hook_specific.get("permissionDecision") == DENY_DECISION
    deny_reason = hook_specific.get("permissionDecisionReason", "")
    if not isinstance(deny_reason, str):
        deny_reason = ""
    system_message = parsed_output.get("systemMessage", "")
    additional_context = system_message if isinstance(system_message, str) else ""
    return is_deny, deny_reason, additional_context


@dataclass
class DispatcherDecision:
    """The aggregated decision across all hosted hook results.

    Attributes:
        should_deny: True when at least one hosted hook denied.
        all_deny_reasons: All deny reasons from denying hooks, in run order.
        all_additional_context: All additional-context messages from all hooks.
    """

    should_deny: bool
    all_deny_reasons: list[str]
    all_additional_context: list[str]


def aggregate_hosted_hook_results(
    all_results: list[HostedHookResult],
) -> DispatcherDecision:
    """Aggregate all hosted hook results into one dispatcher decision.

    Parses each result's stdout for a deny decision. A clean
    BLOCKING_CRASH_EXIT_CODE from a blocking hook also signals deny. Deny wins
    over allow: when any result
    denies, the aggregate denies carrying every denying reason. When a deny
    carries no reason text, EXIT_CODE_TWO_DENY_REASON supplies a fallback.
    Collects every additional-context message from every hook, whether or not
    it denied.

    Args:
        all_results: Outcomes from running each applicable hosted hook.

    Returns:
        A DispatcherDecision with the aggregated allow-or-deny signal, all
        deny reasons, and all additional-context messages.
    """
    all_deny_reasons: list[str] = []
    all_additional_context: list[str] = []

    for each_result in all_results:
        is_deny, deny_reason, additional_context = _parse_deny_from_hook_output(
            each_result.captured_stdout
        )
        if is_deny:
            all_deny_reasons.append(deny_reason if deny_reason else EXIT_CODE_TWO_DENY_REASON)
        elif each_result.did_crash and each_result.is_blocking:
            all_deny_reasons.append(
                "[dispatcher] hook crash in blocking hook — write blocked for safety"
            )
        elif each_result.exit_code == BLOCKING_CRASH_EXIT_CODE and each_result.is_blocking:
            all_deny_reasons.append(EXIT_CODE_TWO_DENY_REASON)
        if additional_context:
            all_additional_context.append(additional_context)

    return DispatcherDecision(
        should_deny=bool(all_deny_reasons),
        all_deny_reasons=all_deny_reasons,
        all_additional_context=all_additional_context,
    )


def _emit_deny_decision(decision: DispatcherDecision) -> None:
    """Write one deny JSON object to stdout carrying all deny reasons.

    Args:
        decision: The aggregated dispatcher decision with deny reasons and context.
    """
    combined_reason = " | ".join(decision.all_deny_reasons)
    deny_payload: dict[str, object] = {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "permissionDecision": DENY_DECISION,
            "permissionDecisionReason": combined_reason,
        }
    }
    if decision.all_additional_context:
        deny_payload["systemMessage"] = "\n".join(decision.all_additional_context)
    sys.stdout.write(json.dumps(deny_payload) + "\n")
    sys.stdout.flush()


def _select_applicable_hooks(tool_name: str) -> list[HostedHookEntry]:
    """Return the ordered hosted hook entries applicable to the given tool name.

    Args:
        tool_name: The tool name from the PreToolUse payload.

    Returns:
        The ordered list of HostedHookEntry objects whose applicable_tool_names
        set includes tool_name.
    """
    return [
        each_entry
        for each_entry in ALL_HOSTED_HOOK_ENTRIES
        if tool_name in each_entry.applicable_tool_names
    ]


def _resolve_hook_script_path(relative_path: str) -> str:
    """Resolve a hook relative path to an absolute path.

    Args:
        relative_path: Hook path relative to the hooks/ directory.

    Returns:
        The absolute path of the hook script.
    """
    return str(Path(__file__).resolve().parent.parent / relative_path)


def _run_one_hosted_hook(
    each_entry: HostedHookEntry,
    payload_text: str,
    payload_by_key: dict[str, object],
) -> HostedHookResult:
    """Run one hosted hook either natively or via runpy and return its outcome.

    Calls the hook's native evaluator in-process when the entry names a native
    module, otherwise runs the hook script via runpy under __main__.

    Args:
        each_entry: The hosted hook entry to run.
        payload_text: The raw JSON payload text to replay to a runpy hook.
        payload_by_key: The parsed payload dict to pass to a native evaluator.

    Returns:
        The HostedHookResult for this hook's run.
    """
    if each_entry.native_module_name is not None:
        native_evaluator_by_module_name: dict[str, NativeEvaluator] = {
            STATE_DESCRIPTION_BLOCKER_MODULE_NAME: evaluate_state_description,
            PLAIN_LANGUAGE_BLOCKER_MODULE_NAME: evaluate_plain_language,
        }
        native_evaluator = native_evaluator_by_module_name[each_entry.native_module_name]
        return run_native_hook(native_evaluator, payload_by_key, each_entry.is_blocking)
    script_path = _resolve_hook_script_path(each_entry.script_relative_path)
    return run_hosted_hook(script_path, payload_text, each_entry.is_blocking)


def dispatch(
    payload_text: str,
    tool_name: str,
    payload_by_key: dict[str, object],
) -> None:
    """Run all applicable hosted hooks and emit one aggregated decision.

    Selects the applicable hosted hooks for tool_name, runs each one in-process
    (natively when the entry names a native module, otherwise via runpy),
    aggregates the results, and either emits a deny JSON object or exits zero to
    allow.

    Args:
        payload_text: The raw JSON payload text to replay to each runpy hook.
        tool_name: The tool name from the PreToolUse payload.
        payload_by_key: The parsed payload dict to pass to native evaluators.
    """
    applicable_entries = _select_applicable_hooks(tool_name)
    all_results: list[HostedHookResult] = []
    for each_entry in applicable_entries:
        hook_result = _run_one_hosted_hook(each_entry, payload_text, payload_by_key)
        all_results.append(hook_result)

    aggregated_decision = aggregate_hosted_hook_results(all_results)
    if aggregated_decision.should_deny:
        _emit_deny_decision(aggregated_decision)


def main() -> None:
    """Read stdin once and dispatch to all applicable hosted hooks."""
    payload_dict = read_hook_input_dictionary_from_stdin()
    if payload_dict is None:
        sys.exit(0)

    payload_text = json.dumps(payload_dict)
    tool_name = payload_dict.get("tool_name", "")
    if not isinstance(tool_name, str):
        sys.exit(0)

    dispatch(payload_text, tool_name, payload_dict)
    sys.exit(0)


if __name__ == "__main__":
    main()
