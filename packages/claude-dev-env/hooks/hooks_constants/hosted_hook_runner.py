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
"""

from __future__ import annotations

import io
import runpy
import sys
import traceback
from dataclasses import dataclass


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
