#!/usr/bin/env python3
"""PostToolUse hook: record a failing single pytest run as TDD-gate evidence.

A file-content edit is not the same claim as a test that ran and failed. The
content-hash store in ``tdd_enforcer_parts/content_hash_store.py`` already
tracks whether a candidate test file's content changed; this hook adds a
stronger form of evidence -- a real RED -- by watching every Bash call finish
and, for a genuine failing pytest run, recording the command, its real exit
status, and the test file paths it named into that same store.

::

    pytest test_orders.py                    (exit 1)  -> record test_orders.py
    pytest test_orders.py -k fulfill          (exit 1)  -> record test_orders.py
    pytest test_orders.py::test_fulfill       (exit 1)  -> record test_orders.py
    pytest -q                                 (exit 1)  -> no path named, no record
    cd repo && pytest test_orders.py          (exit 1)  -> chained, no record
    pytest test_orders.py | tee run.log       (blocked by piped_pytest_blocker
                                                first -- this hook never sees it)
    npm test                                  (exit 1)  -> not pytest, no record
    pytest test_orders.py                     (exit 0)  -> passed, no record

What this hook matches, and why
--------------------------------

Only a single, unchained Bash command whose own program is ``pytest`` /
``py.test``, or a Python interpreter running ``-m pytest``. A chained command
(``&&``, ``;``, ``|``, ``||``, a newline) is rejected outright: this repo's own
``piped_pytest_blocker.py`` already tells the caller to "run pytest alone" for
exactly this reason, and a chain's reported exit status may belong to a
command other than pytest, or to none of them if an earlier link short-
circuited before pytest even ran. ``npm test``, ``node --test``, and
``vitest`` are deliberately not matched: ``npm test`` is a script indirection
whose real test runner lives in ``package.json``, not on the command line,
and the other two have no existing, tested classification helper in this
repository the way pytest does. Extending to them would mean inventing new
parsing rather than reusing anything proven, which is the over-reach this
mechanism is built to avoid.

The recognizer here is deliberately its own small, stdlib-only ``shlex``
check rather than a reuse of ``hooks_constants.pytest_invocation`` /
``shell_command_pipeline``. Those solve the harder pipe-and-wrapper problem a
PreToolUse blocker needs, and this repository's own style rule forbids an
import inside a function body, so importing that larger machinery here would
mean paying its full transitive import cost on every single Bash call this
hook sees, pytest or not -- working directly against the point of watching
every Bash call. The narrower, single-unchained-command scope this hook
accepts does not need that machinery.

Where the exit status comes from
---------------------------------

Not from scraping the command's output text for words like "failed" or
"error". The Bash tool's own PostToolUse ``tool_response`` takes two shapes
observed directly in this session's own transcript: a dict with ``stdout``/
``stderr`` keys when the command's reported exit status is 0, and the literal
string ``"Error: Exit code <N>\\n<output>"`` when it is not. This hook reads
that harness-authored ``<N>`` directly; it is a real Bash mechanism doing the
work correctly, not a lookalike that only mimics one.

Where the test paths come from
--------------------------------

The command's own arguments, not its output. A bare ``pytest`` or ``pytest
-q`` names no path and is left unrecorded on purpose: recording it against
every test file pytest might have discovered would satisfy the gate for a
file this run never demonstrably covered, which is the exact bypass the
audit calls out. Only a token that is not an option flag and resolves to a
real file on disk, relative to the command's own ``cwd``, counts.

What stops a bypass
---------------------

Three things, together:

1. ``content_hash_store.record_test_command_failure`` keys each entry
   exactly as the gate looks candidates up, so a failure never satisfies a
   sibling file the same command also happened to run (see
   ``test_content_hash_store.py::test_recorded_failure_does_not_satisfy_a_different_candidate``).
2. The gate consults a recorded failure only while the file's *current*
   content hash still matches what actually failed (see
   ``test_recorded_failure_does_not_apply_once_content_no_longer_matches``).
   Editing the test again clears it as evidence.
3. A record ages out after the same freshness window every other form of
   evidence uses (see ``test_recorded_failure_expires_after_the_freshness_window``).

The hook never blocks a tool call. A non-Bash tool, a malformed payload, a
command that does not mention "pytest", a chained command, a command with no
real path argument, or a failed record each returns quietly.
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

try:
    _hooks_root_directory = str(Path(__file__).resolve().parent.parent)
    _blocking_directory = str(Path(_hooks_root_directory) / "blocking")
    for each_bootstrap_directory in (_hooks_root_directory, _blocking_directory):
        if each_bootstrap_directory not in sys.path:
            sys.path.insert(0, each_bootstrap_directory)
    from hooks_constants.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin
    from hooks_constants.test_failure_recorder_constants import (
        ALL_CHAINING_OPERATOR_SUBSTRINGS,
        ALL_PYTEST_MENTION_SUBSTRINGS,
        ALL_PYTEST_PROGRAM_BASENAMES,
        ALL_REDIRECTION_TOKENS,
        BASH_TOOL_NAME,
        EXIT_CODE_ERROR_PREFIX,
        MODULE_RUN_FLAG,
        NODE_ID_FILE_PATH_SEPARATOR,
        OPTION_TOKEN_PREFIX,
        PYTEST_MODULE_NAME,
        PYTHON_INTERPRETER_BASENAME_PATTERN,
    )
    from tdd_enforcer_parts import content_hash_store
except ImportError as import_error:
    raise ImportError(
        "test_failure_recorder: cannot import its dependencies; "
        "ensure the hooks directory is importable."
    ) from import_error


def _mentions_pytest(command: str) -> bool:
    lowered_command = command.lower()
    return any(
        each_substring in lowered_command for each_substring in ALL_PYTEST_MENTION_SUBSTRINGS
    )


def _harness_reported_exit_status(tool_response: object) -> int | None:
    if not isinstance(tool_response, str) or not tool_response.startswith(EXIT_CODE_ERROR_PREFIX):
        return None
    remainder = tool_response[len(EXIT_CODE_ERROR_PREFIX) :]
    digit_count = 0
    while digit_count < len(remainder) and remainder[digit_count].isdigit():
        digit_count += 1
    return int(remainder[:digit_count]) if digit_count else None


def _is_single_unchained_command(command: str) -> bool:
    return not any(each_operator in command for each_operator in ALL_CHAINING_OPERATOR_SUBSTRINGS)


def _runs_pytest_via_module_flag(all_tokens: list[str]) -> bool:
    if MODULE_RUN_FLAG not in all_tokens:
        return False
    flag_index = all_tokens.index(MODULE_RUN_FLAG)
    return flag_index + 1 < len(all_tokens) and all_tokens[flag_index + 1] == PYTEST_MODULE_NAME


def _command_tokens_run_pytest(all_tokens: list[str]) -> bool:
    if not all_tokens:
        return False
    first_basename = Path(all_tokens[0]).name
    if first_basename in ALL_PYTEST_PROGRAM_BASENAMES:
        return True
    if not PYTHON_INTERPRETER_BASENAME_PATTERN.match(first_basename):
        return False
    return _runs_pytest_via_module_flag(all_tokens)


def _existing_test_file_paths(all_tokens: list[str], cwd: str) -> list[Path]:
    all_paths: list[Path] = []
    for each_token in all_tokens:
        if each_token.startswith(OPTION_TOKEN_PREFIX) or each_token in ALL_REDIRECTION_TOKENS:
            continue
        file_path_text = each_token.split(NODE_ID_FILE_PATH_SEPARATOR, 1)[0]
        candidate_path = Path(cwd, file_path_text) if cwd else Path(file_path_text)
        if candidate_path.is_file():
            all_paths.append(candidate_path)
    return all_paths


def _command_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return []


def _record_pytest_failure(hook_payload: dict, command: str) -> None:
    exit_status = _harness_reported_exit_status(hook_payload.get("tool_response"))
    if exit_status is None or not _is_single_unchained_command(command):
        return
    all_tokens = _command_tokens(command)
    if not _command_tokens_run_pytest(all_tokens):
        return
    cwd = str(hook_payload.get("cwd") or "")
    all_test_file_paths = _existing_test_file_paths(all_tokens, cwd)
    if not all_test_file_paths:
        return
    session_id = str(hook_payload.get("session_id") or "")
    content_hash_store.record_test_command_failure(
        all_test_file_paths, command, exit_status, session_id, cwd
    )


def main() -> None:
    """Record one failing pytest run's evidence from a PostToolUse Bash payload.

    Reads the payload from stdin. Returns quietly on every branch that is not
    a genuine, single, unchained, path-naming pytest failure, so a logging
    problem never surfaces as a blocked or altered tool call.
    """
    hook_payload = read_hook_input_dictionary_from_stdin()
    if hook_payload is None or hook_payload.get("tool_name") != BASH_TOOL_NAME:
        return
    tool_input = hook_payload.get("tool_input")
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not isinstance(command, str) or not _mentions_pytest(command):
        return
    _record_pytest_failure(hook_payload, command)


if __name__ == "__main__":
    main()
