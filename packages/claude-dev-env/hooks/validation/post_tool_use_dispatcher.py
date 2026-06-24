#!/usr/bin/env python3
"""PostToolUse dispatcher that hosts the after-write Write/Edit hooks.

Reads the tool payload from stdin once, runs each hosted hook in-process via
runpy in the fixed order declared in the constants module, aggregates the
results, and emits one PostToolUse block decision when any hook blocked
(carrying every blocking reason) or exits zero to allow.

The hosted hooks keep every side effect they have today: the formatter writes
the reformatted file to disk, and the doc publisher uploads the gist. Running
them in-process preserves those side effects while collapsing three processes
into one. The dispatcher itself performs no file write; it runs the hooks in a
fixed order that reproduces the prior registration order. One hosted hook (the
formatter) does rewrite the edited file mid-sequence, so a later hook reads the
file as the formatter left it — the same order the prior separate entries ran.
"""

from __future__ import annotations

import io
import json
import runpy
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from hooks_constants.post_tool_use_dispatcher_constants import (  # noqa: E402
    ALL_POST_HOSTED_HOOK_ENTRIES,
    BLOCK_DECISION,
    BLOCKING_CRASH_DENY_REASON,
    DECISION_KEY,
    EMPTY_REASON_BLOCK_FALLBACK,
    HOOK_EVENT_NAME,
    PLUGIN_ROOT_PLACEHOLDER,
    REASON_KEY,
    PostHostedHookEntry,
)
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)


@dataclass
class PostHostedHookResult:
    """Outcome of running one hosted PostToolUse hook inside the dispatcher process.

    Attributes:
        captured_stdout: The text the hook wrote to stdout during its run.
        did_crash: True when the hook raised a non-SystemExit exception.
        is_blocking: True when this hook's crash surfaces a blocking signal.
    """

    captured_stdout: str
    did_crash: bool = field(default=False)
    is_blocking: bool = field(default=False)


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
    all_hook_arguments: list[str],
    payload_text: str,
    is_blocking: bool,
) -> PostHostedHookResult:
    """Run one hosted PostToolUse hook in-process and return its outcome.

    Sets stdin to a fresh stream over payload_text, sets argv to the hook's
    script path plus its argument tail so a hook reading sys.argv resolves the
    same arguments the live entry passes, captures stdout into a buffer, runs
    the hook via runpy under __main__, catches SystemExit to absorb the hook's
    exit without ending the dispatcher, and catches a non-SystemExit exception
    to log the crash and classify it. Always restores stdin, stdout, and argv
    in the finally block.

    Args:
        hook_script_path: Absolute path of the hook script to run.
        all_hook_arguments: Resolved command-line arguments the hook reads after
            its script path.
        payload_text: The raw payload text to replay as the hook's stdin.
        is_blocking: Whether a crash from this hook surfaces a blocking signal.

    Returns:
        A PostHostedHookResult carrying the captured stdout, crash flag, and
        blocking classification.
    """
    original_stdin = sys.stdin
    original_stdout = sys.stdout
    original_argv = sys.argv
    captured_output = io.StringIO()
    hook_did_crash = False

    try:
        sys.stdin = io.StringIO(payload_text)
        sys.stdout = captured_output
        sys.argv = [hook_script_path, *all_hook_arguments]
        runpy.run_path(hook_script_path, run_name="__main__")
    except SystemExit:
        pass
    except Exception as error:
        _log_hook_crash(hook_script_path, error)
        hook_did_crash = True
    finally:
        sys.stdin = original_stdin
        sys.stdout = original_stdout
        sys.argv = original_argv

    return PostHostedHookResult(
        captured_stdout=captured_output.getvalue(),
        did_crash=hook_did_crash,
        is_blocking=is_blocking,
    )


def _parse_block_from_hook_output(hook_output_text: str) -> tuple[bool, str]:
    """Parse one hook's stdout for a PostToolUse block decision.

    Args:
        hook_output_text: The text the hook wrote to stdout.

    Returns:
        A (is_block, block_reason) pair. is_block is True when the hook output
        carries a decision of block. block_reason is the reason text when
        is_block is True.
    """
    stripped_text = hook_output_text.strip()
    if not stripped_text:
        return False, ""
    try:
        parsed_output = json.loads(stripped_text)
    except json.JSONDecodeError:
        return False, ""
    if not isinstance(parsed_output, dict):
        return False, ""
    is_block = parsed_output.get(DECISION_KEY) == BLOCK_DECISION
    block_reason = parsed_output.get(REASON_KEY, "")
    if not isinstance(block_reason, str):
        block_reason = ""
    return is_block, block_reason


@dataclass
class PostDispatcherDecision:
    """The aggregated decision across all hosted PostToolUse hook results.

    Attributes:
        should_block: True when at least one hosted hook blocked.
        all_block_reasons: All block reasons from blocking hooks, in run order.
        all_non_block_stdout: Stdout from hooks that did not emit a block
            decision, concatenated in run order. Preserved so informational
            output (such as the doc-gist htmlpreview URL) reaches the harness
            on both the allow and block paths.
    """

    should_block: bool
    all_block_reasons: list[str]
    all_non_block_stdout: list[str]


def aggregate_post_hosted_hook_results(
    all_results: list[PostHostedHookResult],
) -> PostDispatcherDecision:
    """Aggregate all hosted PostToolUse hook results into one dispatcher decision.

    Parses each result's stdout for a block decision. A block decision signals a
    block regardless of its reason text; an empty-reason block draws
    EMPTY_REASON_BLOCK_FALLBACK so the block is never downgraded to allow. A
    non-SystemExit crash in a blocking hook also signals block. Block wins over
    allow: when any result blocks, the aggregate blocks carrying every blocking
    reason. A side-effect hook that exits cleanly contributes no block. Non-block
    stdout from every hook is preserved so informational output reaches the
    harness on both the allow and block paths.

    Args:
        all_results: Outcomes from running each hosted hook.

    Returns:
        A PostDispatcherDecision with the aggregated allow-or-block signal,
        all block reasons, and all non-block stdout.
    """
    all_block_reasons: list[str] = []
    all_non_block_stdout: list[str] = []

    for each_result in all_results:
        is_block, block_reason = _parse_block_from_hook_output(each_result.captured_stdout)
        if is_block:
            all_block_reasons.append(block_reason if block_reason else EMPTY_REASON_BLOCK_FALLBACK)
        elif each_result.did_crash and each_result.is_blocking:
            all_block_reasons.append(BLOCKING_CRASH_DENY_REASON)
        else:
            non_block_text = each_result.captured_stdout.strip()
            if non_block_text:
                all_non_block_stdout.append(non_block_text)

    return PostDispatcherDecision(
        should_block=bool(all_block_reasons),
        all_block_reasons=all_block_reasons,
        all_non_block_stdout=all_non_block_stdout,
    )


def _emit_non_block_stdout(all_non_block_stdout: list[str], output_stream: TextIO) -> None:
    """Write each non-block hook's stdout to the given stream so the harness sees it.

    Args:
        all_non_block_stdout: The informational stdout lines from non-blocking
            hooks, in run order.
        output_stream: The stream to write the informational lines to.
    """
    for each_line in all_non_block_stdout:
        output_stream.write(each_line + "\n")
    if all_non_block_stdout:
        output_stream.flush()


def _emit_block_decision(decision: PostDispatcherDecision) -> None:
    """Write one PostToolUse block JSON object as the only stdout content.

    Routes any non-block hook stdout to stderr so the harness can parse the whole
    stdout stream as one JSON block object — informational text from a side-effect
    hook never precedes the block JSON on stdout.

    Args:
        decision: The aggregated dispatcher decision with block reasons and
            non-block stdout from side-effect hooks.
    """
    _emit_non_block_stdout(decision.all_non_block_stdout, sys.stderr)
    combined_reason = " | ".join(decision.all_block_reasons)
    block_payload: dict[str, object] = {
        DECISION_KEY: BLOCK_DECISION,
        REASON_KEY: combined_reason,
        "hookSpecificOutput": {"hookEventName": HOOK_EVENT_NAME},
    }
    sys.stdout.write(json.dumps(block_payload) + "\n")
    sys.stdout.flush()


def _resolve_hook_script_path(relative_path: str) -> str:
    """Resolve a hook relative path to an absolute path.

    Args:
        relative_path: Hook path relative to the hooks/ directory.

    Returns:
        The absolute path of the hook script.
    """
    return str(Path(__file__).resolve().parent.parent / relative_path)


def _resolve_argument_tail(each_entry: PostHostedHookEntry, plugin_root: str) -> list[str]:
    """Resolve a hook entry's relative argument paths into absolute argv values.

    Args:
        each_entry: The hosted hook entry whose extra arguments to resolve.
        plugin_root: The plugin root absolute path the dispatcher received.

    Returns:
        The resolved argument list the hook reads after its script path. The
        plugin-root placeholder resolves to plugin_root; every other entry
        resolves relative to it.
    """
    resolved_arguments: list[str] = []
    for each_relative_path in each_entry.extra_argument_relative_paths:
        if each_relative_path == PLUGIN_ROOT_PLACEHOLDER:
            resolved_arguments.append(plugin_root)
        else:
            resolved_arguments.append(str(Path(plugin_root) / each_relative_path))
    return resolved_arguments


def dispatch(payload_text: str, plugin_root: str) -> None:
    """Run all hosted PostToolUse hooks and emit one aggregated decision.

    Runs each hosted hook in-process via run_hosted_hook in the fixed order,
    aggregates the results, and emits a block JSON object when any hook blocked.
    A clean run with no block emits nothing and the caller exits zero to allow.

    Args:
        payload_text: The raw JSON payload text to replay to each hook.
        plugin_root: The plugin root absolute path used to resolve hook
            arguments.
    """
    all_results: list[PostHostedHookResult] = []
    for each_entry in ALL_POST_HOSTED_HOOK_ENTRIES:
        script_path = _resolve_hook_script_path(each_entry.script_relative_path)
        argument_tail = _resolve_argument_tail(each_entry, plugin_root)
        hook_result = run_hosted_hook(
            script_path, argument_tail, payload_text, each_entry.is_blocking
        )
        all_results.append(hook_result)

    aggregated_decision = aggregate_post_hosted_hook_results(all_results)
    if aggregated_decision.should_block:
        _emit_block_decision(aggregated_decision)
    else:
        _emit_non_block_stdout(aggregated_decision.all_non_block_stdout, sys.stdout)


def _resolve_plugin_root() -> str:
    """Return the plugin root from argv, or the dispatcher's own location.

    Returns:
        The plugin root absolute path. The live entry passes the plugin root as
        the first argument; when no argument is present the dispatcher derives
        it from its own path (the hooks directory's parent).
    """
    if len(sys.argv) > 1 and sys.argv[1]:
        return sys.argv[1]
    return str(Path(__file__).resolve().parent.parent.parent)


def main() -> None:
    """Read stdin once and dispatch to all hosted PostToolUse hooks."""
    payload_dict = read_hook_input_dictionary_from_stdin()
    if payload_dict is None:
        sys.exit(0)

    payload_text = json.dumps(payload_dict)
    dispatch(payload_text, _resolve_plugin_root())
    sys.exit(0)


if __name__ == "__main__":
    main()
