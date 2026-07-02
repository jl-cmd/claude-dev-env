#!/usr/bin/env python3
"""PreToolUse dispatcher that hosts Write, Edit, and MultiEdit blocking hooks.

Reads the tool payload from stdin once, selects the hosted hooks applicable to
the payload's tool name, runs each hook in-process via runpy in the fixed order
declared in the constants module, aggregates the results, and emits one deny
decision when any hook denied (carrying every denying reason) or exits zero to
allow.

The per-hook coverage matrix:
- Write  -> Group A (11 hooks) + Group B (8 hooks) = 19 hooks
- Edit   -> Group A (11 hooks) + Group B (8 hooks) + the Edit-only hook = 20 hooks
- MultiEdit -> Group B only (8 hooks)
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

from plain_language_blocker import (  # noqa: E402
    build_deny_payload as build_plain_language_deny_payload,
)
from plain_language_blocker import evaluate as evaluate_plain_language  # noqa: E402
from state_description_blocker import (  # noqa: E402
    build_deny_payload as build_state_description_deny_payload,
)
from state_description_blocker import evaluate as evaluate_state_description  # noqa: E402

from hooks_constants.pre_tool_use_dispatcher_constants import (  # noqa: E402
    ALL_HOSTED_HOOK_ENTRIES,
    ALLOW_DECISION,
    BLOCKING_CRASH_DENY_REASON,
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
DenyPayloadBuilder = Callable[[str], dict[str, object]]


@dataclass(frozen=True)
class NativeHook:
    """A nativized hook's evaluator paired with its full deny-payload builder.

    Attributes:
        evaluate: The hook's evaluate function returning a deny-reason or None.
        build_deny_payload: The hook's builder that turns a deny-reason into the
            full deny payload the standalone hook writes (carrying systemMessage,
            additionalContext, and suppressOutput).
    """

    evaluate: NativeEvaluator
    build_deny_payload: DenyPayloadBuilder


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

    Sets stdin to a fresh stream over payload_text, sets argv to the hook's own
    script path so a hook that branches on sys.argv (such as code_rules_enforcer's
    --check pre-check mode) reads the same argv it would standalone rather than
    the dispatcher's, captures stdout into a buffer, runs the hook via runpy
    under __main__, catches SystemExit to read the exit code without ending the
    dispatcher, and catches a non-SystemExit exception to log the crash and
    classify it. Always restores stdin, stdout, and argv in the finally block.

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
    original_argv = sys.argv
    captured_output = io.StringIO()
    hook_exit_code = 0
    hook_did_crash = False

    try:
        sys.stdin = io.StringIO(payload_text)
        sys.stdout = captured_output
        sys.argv = [hook_script_path]
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
        sys.argv = original_argv

    return HostedHookResult(
        exit_code=hook_exit_code,
        captured_stdout=captured_output.getvalue(),
        did_crash=hook_did_crash,
        is_blocking=is_blocking,
    )


def run_native_hook(
    native_hook: NativeHook,
    payload_by_key: dict[str, object],
    is_blocking: bool,
) -> HostedHookResult:
    """Run one hosted hook's native evaluator in-process and return its outcome.

    Calls the evaluator directly with the payload dict, builds the full deny JSON
    via the hook's own deny-payload builder so the captured stdout matches the
    standalone hook's deny shape (carrying systemMessage, additionalContext, and
    suppressOutput), and catches a non-SystemExit crash to log and classify it.

    Args:
        native_hook: The hook's evaluator paired with its deny-payload builder.
        payload_by_key: The parsed payload dict to pass to the evaluator.
        is_blocking: Whether a crash from this hook surfaces a blocking signal.

    Returns:
        A HostedHookResult carrying the captured deny JSON (empty when allowed),
        the crash flag, and the blocking classification.
    """
    try:
        deny_reason = native_hook.evaluate(payload_by_key)
    except Exception as error:
        _log_hook_crash(native_hook.evaluate.__module__, error)
        return HostedHookResult(
            exit_code=BLOCKING_CRASH_EXIT_CODE if is_blocking else 0,
            captured_stdout="",
            did_crash=True,
            is_blocking=is_blocking,
        )

    captured_stdout = (
        json.dumps(native_hook.build_deny_payload(deny_reason)) if deny_reason is not None else ""
    )
    return HostedHookResult(
        exit_code=0,
        captured_stdout=captured_stdout,
        did_crash=False,
        is_blocking=is_blocking,
    )


@dataclass
class ParsedHookOutput:
    """The fields parsed from one hook's stdout.

    Attributes:
        is_deny: True when the hook output carries a permissionDecision of deny.
        is_allow: True when the hook output carries a permissionDecision of allow.
        deny_reason: The permissionDecisionReason text when is_deny is True.
        system_message: The hook's top-level systemMessage, or non-JSON stdout
            text when the output is not a deny-shaped JSON object.
        additional_context: The hook's hookSpecificOutput.additionalContext text.
        suppress_output: True when the hook set a top-level suppressOutput flag.
    """

    is_deny: bool
    is_allow: bool
    deny_reason: str
    system_message: str
    additional_context: str
    suppress_output: bool


def _empty_parsed_hook_output(system_message: str) -> ParsedHookOutput:
    """Build a non-deciding ParsedHookOutput carrying only a system message.

    Used for stdout that is empty or not deny-shaped JSON, where the only field
    worth keeping is the raw stdout text surfaced as the system message.

    Args:
        system_message: The raw stdout text to surface as the system message.

    Returns:
        A ParsedHookOutput that neither denies nor allows.
    """
    return ParsedHookOutput(
        is_deny=False,
        is_allow=False,
        deny_reason="",
        system_message=system_message,
        additional_context="",
        suppress_output=False,
    )


def _parse_deny_from_hook_output(hook_output_text: str) -> ParsedHookOutput:
    """Parse one hook's stdout for its permission decision and user-facing fields.

    Captures the deny signal and the explicit allow signal, plus every
    supplementary field a hook emits on a deny — the top-level systemMessage and
    suppressOutput, and the hookSpecificOutput.additionalContext — so the
    dispatcher reproduces the standalone hook's full deny shape and re-emits an
    explicit allow when a hook auto-approves the write.

    Args:
        hook_output_text: The text the hook wrote to stdout.

    Returns:
        A ParsedHookOutput carrying the deny signal, the allow signal, deny
        reason, systemMessage, additionalContext, and suppressOutput flag. When
        the output is not deny-shaped JSON, system_message carries the raw stdout
        text.
    """
    stripped_text = hook_output_text.strip()
    if not stripped_text:
        return _empty_parsed_hook_output("")
    try:
        parsed_output = json.loads(stripped_text)
    except json.JSONDecodeError:
        return _empty_parsed_hook_output(stripped_text)
    if not isinstance(parsed_output, dict):
        return _empty_parsed_hook_output(stripped_text)
    hook_specific = parsed_output.get("hookSpecificOutput", {})
    if not isinstance(hook_specific, dict):
        return _empty_parsed_hook_output(stripped_text)
    permission_decision = hook_specific.get("permissionDecision")
    is_deny = permission_decision == DENY_DECISION
    is_allow = permission_decision == ALLOW_DECISION
    deny_reason = hook_specific.get("permissionDecisionReason", "")
    if not isinstance(deny_reason, str):
        deny_reason = ""
    raw_system_message = parsed_output.get("systemMessage", "")
    system_message = raw_system_message if isinstance(raw_system_message, str) else ""
    raw_additional_context = hook_specific.get("additionalContext", "")
    additional_context = raw_additional_context if isinstance(raw_additional_context, str) else ""
    suppress_output = parsed_output.get("suppressOutput") is True
    return ParsedHookOutput(
        is_deny=is_deny,
        is_allow=is_allow,
        deny_reason=deny_reason,
        system_message=system_message,
        additional_context=additional_context,
        suppress_output=suppress_output,
    )


@dataclass
class DispatcherDecision:
    """The aggregated decision across all hosted hook results.

    Attributes:
        should_deny: True when at least one hosted hook denied.
        should_allow: True when at least one hosted hook emitted an explicit
            allow decision and no hook denied, so the dispatcher re-emits an
            explicit allow matching the standalone hook's auto-approval.
        all_deny_reasons: All deny reasons from denying hooks, in run order.
        all_system_messages: Every hook's top-level systemMessage, in run order,
            joined into the deny payload's systemMessage.
        all_additional_context: Every hook's hookSpecificOutput.additionalContext,
            in run order, joined into the deny payload's additionalContext.
        should_suppress_output: True when any hook set a suppressOutput flag, so
            the deny payload suppresses output as the standalone hook would.
    """

    should_deny: bool
    should_allow: bool
    all_deny_reasons: list[str]
    all_system_messages: list[str]
    all_additional_context: list[str]
    should_suppress_output: bool


def aggregate_hosted_hook_results(
    all_results: list[HostedHookResult],
) -> DispatcherDecision:
    """Aggregate all hosted hook results into one dispatcher decision.

    Parses each result's stdout for a deny decision and an explicit allow
    decision. A clean BLOCKING_CRASH_EXIT_CODE from a blocking hook also signals
    deny. Deny wins over allow: when any result denies, the aggregate denies
    carrying every denying reason. When a deny carries no reason text,
    EXIT_CODE_TWO_DENY_REASON supplies a fallback. When no result denies and at
    least one result carried an explicit allow decision, the aggregate signals an
    explicit allow so the dispatcher re-emits it, matching the standalone hook's
    auto-approval. Collects every systemMessage and additionalContext message
    from every hook, and the suppressOutput flag, whether or not it denied, so
    the emitted deny reproduces each standalone hook's full deny shape.

    Args:
        all_results: Outcomes from running each applicable hosted hook.

    Returns:
        A DispatcherDecision with the aggregated deny signal, the explicit allow
        signal, all deny reasons, all systemMessage and additionalContext
        messages, and the suppressOutput flag.
    """
    all_deny_reasons: list[str] = []
    all_system_messages: list[str] = []
    all_additional_context: list[str] = []
    should_suppress_output = False
    saw_explicit_allow = False

    for each_result in all_results:
        parsed_output = _parse_deny_from_hook_output(each_result.captured_stdout)
        if parsed_output.is_deny:
            all_deny_reasons.append(
                parsed_output.deny_reason if parsed_output.deny_reason else EXIT_CODE_TWO_DENY_REASON
            )
        elif each_result.did_crash and each_result.is_blocking:
            all_deny_reasons.append(BLOCKING_CRASH_DENY_REASON)
        elif each_result.exit_code == BLOCKING_CRASH_EXIT_CODE and each_result.is_blocking:
            all_deny_reasons.append(EXIT_CODE_TWO_DENY_REASON)
        if parsed_output.is_allow:
            saw_explicit_allow = True
        if parsed_output.system_message:
            all_system_messages.append(parsed_output.system_message)
        if parsed_output.additional_context:
            all_additional_context.append(parsed_output.additional_context)
        if parsed_output.suppress_output:
            should_suppress_output = True

    should_deny = bool(all_deny_reasons)
    return DispatcherDecision(
        should_deny=should_deny,
        should_allow=saw_explicit_allow and not should_deny,
        all_deny_reasons=all_deny_reasons,
        all_system_messages=all_system_messages,
        all_additional_context=all_additional_context,
        should_suppress_output=should_suppress_output,
    )


def _emit_deny_decision(decision: DispatcherDecision) -> None:
    """Write one deny JSON object to stdout carrying all deny reasons and context.

    Carries every hook's systemMessage and additionalContext and the
    suppressOutput flag so the dispatched deny matches the standalone hooks'
    full deny shape.

    Args:
        decision: The aggregated dispatcher decision with deny reasons, context,
            and the suppressOutput flag.
    """
    combined_reason = " | ".join(decision.all_deny_reasons)
    hook_specific: dict[str, object] = {
        "hookEventName": HOOK_EVENT_NAME,
        "permissionDecision": DENY_DECISION,
        "permissionDecisionReason": combined_reason,
    }
    if decision.all_additional_context:
        hook_specific["additionalContext"] = "\n".join(decision.all_additional_context)
    deny_payload: dict[str, object] = {"hookSpecificOutput": hook_specific}
    if decision.all_system_messages:
        deny_payload["systemMessage"] = "\n".join(decision.all_system_messages)
    if decision.should_suppress_output:
        deny_payload["suppressOutput"] = True
    sys.stdout.write(json.dumps(deny_payload) + "\n")
    sys.stdout.flush()


def _emit_allow_decision() -> None:
    """Write one explicit allow JSON object to stdout.

    Matches the shape a standalone hosted hook emits when it auto-approves the
    write, so a write a hosted hook allows explicitly is auto-approved under the
    dispatcher rather than falling back to the default permission flow.
    """
    allow_payload: dict[str, object] = {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "permissionDecision": ALLOW_DECISION,
        }
    }
    sys.stdout.write(json.dumps(allow_payload) + "\n")
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
        native_hook_by_module_name: dict[str, NativeHook] = {
            STATE_DESCRIPTION_BLOCKER_MODULE_NAME: NativeHook(
                evaluate=evaluate_state_description,
                build_deny_payload=build_state_description_deny_payload,
            ),
            PLAIN_LANGUAGE_BLOCKER_MODULE_NAME: NativeHook(
                evaluate=evaluate_plain_language,
                build_deny_payload=build_plain_language_deny_payload,
            ),
        }
        native_hook = native_hook_by_module_name[each_entry.native_module_name]
        return run_native_hook(native_hook, payload_by_key, each_entry.is_blocking)
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
    aggregates the results, and emits a deny JSON object when any hook denied, an
    explicit allow JSON object when a hook allowed explicitly and none denied, or
    exits zero with no output when no hook decided.

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
        return
    if aggregated_decision.should_allow:
        _emit_allow_decision()


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
