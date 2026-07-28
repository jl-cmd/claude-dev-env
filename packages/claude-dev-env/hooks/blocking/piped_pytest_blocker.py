#!/usr/bin/env python3
"""PreToolUse hook: deny a Bash command that pipes a pytest run into another command.

A pipeline reports the exit code of its last command, so a red pytest run piped
anywhere reads as green. Each pytest spelling denies when its output feeds a
pipe: bare ``pytest``, ``python -m pytest``, and an interpreter path such as
``C:\\Python313\\python.exe -m pytest``.

::

    pytest | tee run.log                        flag: output feeds a pipe
    python -m pytest tests | head -50           flag: module spelling
    C:\\Python313\\python.exe -m pytest | cat   flag: interpreter path
    pytest tests > run.log 2>&1                 ok:   redirection keeps the code
    pytest tests                                ok:   pytest alone
    git status | head                           ok:   segment carries no pytest
    cat ids.txt | pytest --stdin                ok:   the pipe feeds into pytest

Tokenizing is local to this module. ``shell_command_segments.split_into_segments``
cuts a token on an operator character the token carries, so ``pytest -k "a|b"``
reads there as two segments; the lexer here keeps that quoted text whole.
"""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.piped_pytest_blocker_constants import (  # noqa: E402
    ALL_PIPE_OPERATOR_TOKENS,
    ALL_PYTEST_PROGRAM_BASENAMES,
    ALL_QUOTE_CHARACTERS,
    ALL_SEGMENT_RESET_OPERATOR_TOKENS,
    ALL_SUPPORTED_TOOL_NAMES,
    CALLING_HOOK_NAME,
    CORRECTIVE_MESSAGE,
    DENY_DECISION,
    HOOK_EVENT_NAME,
    MODULE_RUN_FLAG,
    PYTEST_MODULE_NAME,
    PYTHON_INTERPRETER_BASENAME_PATTERN,
)
from hooks_constants.shell_command_segments import (  # noqa: E402
    effective_leading_program,
    token_basename,
)


def _unquoted(token: str) -> str:
    """Return a token with its surrounding shell quotes removed."""
    return token.strip(ALL_QUOTE_CHARACTERS)


def _all_operator_aware_tokenizations(command: str) -> list[list[str]]:
    """Return quote-aware tokenizations that carry operators as their own tokens.

    POSIX mode resolves quoting the way Git Bash does; raw mode keeps a Windows
    interpreter path such as ``C:\\Python313\\python.exe`` whole, since POSIX
    mode reads its backslashes as escapes. Both are returned so a violation in
    either spelling is visible.
    """
    all_tokenizations: list[list[str]] = []
    for each_posix_mode in (True, False):
        lexer = shlex.shlex(command, posix=each_posix_mode, punctuation_chars=True)
        lexer.whitespace_split = True
        try:
            all_tokens = list(lexer)
        except ValueError:
            continue
        if all_tokens:
            all_tokenizations.append(all_tokens)
    return all_tokenizations


def _runs_pytest_as_a_module(all_segment_tokens: list[str]) -> bool:
    """Return True when the segment carries a ``-m pytest`` module run."""
    for each_index, each_token in enumerate(all_segment_tokens):
        if each_token != MODULE_RUN_FLAG:
            continue
        module_index = each_index + 1
        if module_index >= len(all_segment_tokens):
            return False
        return _unquoted(all_segment_tokens[module_index]) == PYTEST_MODULE_NAME
    return False


def segment_runs_pytest(all_segment_tokens: list[str]) -> bool:
    """Return True when a simple-command segment invokes pytest.

    ::

        ['pytest', 'tests']                         flag
        ['python', '-m', 'pytest']                  flag
        ['C:\\\\Python313\\\\python.exe', '-m', 'pytest']  flag
        ['python', '-m', 'mypy']                    ok
        ['git', 'status']                           ok
        []                                          ok

    Args:
        all_segment_tokens: The tokens of one simple command, operators removed.

    Returns:
        True when the segment's program is pytest or a python interpreter
        running the pytest module.
    """
    leading_program = effective_leading_program(all_segment_tokens)
    if leading_program is None:
        return False
    program_basename = token_basename(_unquoted(leading_program))
    if program_basename in ALL_PYTEST_PROGRAM_BASENAMES:
        return True
    if not PYTHON_INTERPRETER_BASENAME_PATTERN.fullmatch(program_basename):
        return False
    return _runs_pytest_as_a_module(all_segment_tokens)


def _tokenization_pipes_pytest(all_command_tokens: list[str]) -> bool:
    """Return True when a pytest segment sits on the left of a pipe operator."""
    current_segment: list[str] = []
    for each_token in all_command_tokens:
        if each_token in ALL_PIPE_OPERATOR_TOKENS:
            if segment_runs_pytest(current_segment):
                return True
            current_segment = []
            continue
        if each_token in ALL_SEGMENT_RESET_OPERATOR_TOKENS:
            current_segment = []
            continue
        current_segment.append(each_token)
    return False


def find_piped_pytest_violation(command: str) -> str | None:
    """Return the deny message for a piped pytest run, or None to allow.

    ::

        pytest | tee run.log                   flag
        python -m pytest tests | head -50      flag
        pytest tests 2>&1 | tee run.log        flag
        cd repo && pytest | cat                flag
        pytest tests > run.log 2>&1            ok
        pytest tests                           ok
        pytest && echo done | tee run.log      ok
        git status | head                      ok
        cat ids.txt | pytest --stdin           ok
        pytest -k "a|b"                        ok

    Tokenizes the command so shell operators stand alone and quoted text stays
    whole, then walks the tokens. A pipe operator tests the segment that feeds
    it; a command separator starts a fresh segment; a redirection stays inside
    the segment it belongs to.

    Args:
        command: The raw Bash command string from the tool input.

    Returns:
        The corrective deny message when a pytest segment feeds a pipe, else
        None.
    """
    for each_tokenization in _all_operator_aware_tokenizations(command):
        if _tokenization_pipes_pytest(each_tokenization):
            return CORRECTIVE_MESSAGE
    return None


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    if tool_name not in ALL_SUPPORTED_TOOL_NAMES:
        sys.exit(0)

    command = hook_input.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    deny_reason = find_piped_pytest_violation(command)
    if deny_reason is None:
        sys.exit(0)

    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "permissionDecision": DENY_DECISION,
            "permissionDecisionReason": deny_reason,
        }
    }
    log_hook_block(
        calling_hook_name=CALLING_HOOK_NAME,
        hook_event=HOOK_EVENT_NAME,
        block_reason=deny_reason,
        tool_name=tool_name,
        offending_input_preview=command,
    )
    print(json.dumps(deny_payload))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
