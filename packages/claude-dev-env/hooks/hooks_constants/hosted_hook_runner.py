"""Shared in-process runner for dispatcher-hosted hooks.

Runs one hook script via runpy under __main__ with stdin, stdout, and argv
swapped to mimic a standalone invocation, captures what the hook writes to
stdout, and reports whether the hook raised. The runner carries no allow or deny
policy: the caller reads captured_stdout to learn the hook's decision and
applies its own aggregation, so a hook that raises contributes no decision,
matching a standalone hook whose uncaught exception exits nonzero without
blocking the tool call.

::

    run = run_hook_capturing_output("/hooks/blocking/gate.py", '{"tool_name": "Bash"}')
    ok:   run.captured_stdout carries the gate's deny JSON, run.did_crash is False
    flag: run.did_crash is True when the gate raised, run.captured_stdout is ""

``run_dispatcher_main`` holds the entry-point shell a hosted-hook dispatcher's
own ``main`` needs: read one stdin payload, resolve its tool_name, and hand
both to the dispatcher's own ``dispatch`` callback. Every dispatcher's
``main`` reduces to one call into this shared shell, so the read-resolve-exit
boilerplate lives in one place rather than once per dispatcher.
"""

from __future__ import annotations

import io
import json
import runpy
import sys
from pathlib import Path
import traceback
from collections.abc import Callable
from dataclasses import dataclass

from hooks_constants.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin


@dataclass
class HostedHookRun:
    """Outcome of running one hosted hook in-process.

    Attributes:
        captured_stdout: The text the hook wrote to stdout during its run.
        did_crash: True when the hook raised a non-SystemExit exception.
    """

    captured_stdout: str
    did_crash: bool


def log_hosted_hook_crash(hook_script_path: str, error: Exception) -> None:
    """Write a one-line crash summary for a hosted hook to stderr."""
    formatted_traceback = traceback.format_exc().strip()
    last_line = formatted_traceback.splitlines()[-1] if formatted_traceback else str(error)
    error_type_name = type(error).__name__
    sys.stderr.write(
        f"[dispatcher] crash in {hook_script_path}: {error_type_name}: {error} | {last_line}\n"
    )
    sys.stderr.flush()


def run_hook_capturing_output(hook_script_path: str, payload_text: str) -> HostedHookRun:
    """Run a hook in-process, returning its captured stdout and crash flag.

    Swaps stdin/stdout/argv to mimic a standalone run, executes via runpy under
    __main__, catches SystemExit and any other exception (logged as a crash), and
    always restores the swapped streams and argv.
    """
    original_stdin, original_stdout, original_argv = sys.stdin, sys.stdout, sys.argv
    captured_output = io.StringIO()
    did_crash = False
    try:
        sys.stdin = io.StringIO(payload_text)
        sys.stdout = captured_output
        sys.argv = [hook_script_path]
        runpy.run_path(hook_script_path, run_name="__main__")
    except SystemExit:
        pass
    except Exception as error:
        log_hosted_hook_crash(hook_script_path, error)
        did_crash = True
    finally:
        sys.stdin, sys.stdout, sys.argv = original_stdin, original_stdout, original_argv
    return HostedHookRun(captured_stdout=captured_output.getvalue(), did_crash=did_crash)


def resolved_hook_script_path(relative_path: str) -> str:
    """Resolve a hooks/-relative path to the absolute script path to run.

    ::

        "observability/test_failure_recorder.py" -> <hooks>/observability/...

    The root comes from this module's own location, so every dispatcher
    resolves against the same directory however deep it sits.

    Args:
        relative_path: A path relative to the hooks directory.

    Returns:
        The absolute path of that script.
    """
    hooks_root = Path(__file__).resolve().parent.parent
    return str(hooks_root / relative_path)


def run_dispatcher_main(dispatch: Callable[[str, str], None]) -> None:
    """Read one stdin payload and hand its JSON text and tool_name to dispatch.

    Every hosted-hook dispatcher's own ``main`` reduces to this one call.
    Exits 0 before ever calling dispatch when stdin is empty, malformed, or
    names no tool_name string; always exits 0 afterward, since a dispatcher
    signals its own outcome, if any, through what dispatch itself writes.

    Args:
        dispatch: The dispatcher's own ``dispatch(payload_text, tool_name)``.
    """
    payload_dictionary = read_hook_input_dictionary_from_stdin()
    if payload_dictionary is None:
        sys.exit(0)
    payload_text = json.dumps(payload_dictionary)
    tool_name = payload_dictionary.get("tool_name", "")
    if not isinstance(tool_name, str) or not tool_name:
        sys.exit(0)
    dispatch(payload_text, tool_name)
    sys.exit(0)
