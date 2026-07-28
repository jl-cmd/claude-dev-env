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
    (python -m pytest tests) | tee run.log      flag: subshell feeds a pipe
    bash -c 'pytest | tee run.log'              flag: pipeline inside a wrapper
    time pytest tests | tee run.log             flag: launcher wrapper
    pytest tests \\<newline>| tee run.log       flag: one continued line
    pytest tests > run.log 2>&1                 ok:   redirection keeps the code
    pytest tests                                ok:   pytest alone
    git status | head                           ok:   segment carries no pytest
    cat ids.txt | pytest --stdin                ok:   the pipe feeds into pytest
    pytest tests -q<newline>git status | head   ok:   the pipe sits on a later line

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
    ALL_STRING_EXEC_COMMAND_FLAGS,
    ALL_STRING_EXECUTING_SHELL_BASENAMES,
    ALL_SUPPORTED_TOOL_NAMES,
    CALLING_HOOK_NAME,
    COMMAND_LINE_SPLIT_PATTERN,
    CORRECTIVE_MESSAGE,
    DENY_DECISION,
    HOOK_EVENT_NAME,
    LINE_CONTINUATION_JOIN,
    LINE_CONTINUATION_PATTERN,
    MODULE_RUN_FLAG,
    NO_FOLLOWING_OPERATOR,
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


def _glued_module_name(token: str) -> str | None:
    """Return the module name glued onto a ``-m`` flag, or None for any other token.

    ::

        -mpytest   pytest
        -mmypy     mypy
        -m         None   (the module name is the next token)
        --maxfail  None
    """
    unquoted_token = _unquoted(token)
    if not unquoted_token.startswith(MODULE_RUN_FLAG):
        return None
    return unquoted_token[len(MODULE_RUN_FLAG) :] or None


def _runs_pytest_as_a_module(all_segment_tokens: list[str]) -> bool:
    """Return True when the segment carries ``-m pytest`` or ``-mpytest``."""
    for each_index, each_token in enumerate(all_segment_tokens):
        glued_module_name = _glued_module_name(each_token)
        if glued_module_name is not None:
            return glued_module_name == PYTEST_MODULE_NAME
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
        ['python', '-mpytest']                      flag
        ['time', 'pytest', 'tests']                 flag
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


def _string_exec_inner_command(all_segment_tokens: list[str]) -> str | None:
    """Return the command string a shell wrapper runs, or None for any other segment.

    ::

        bash -c 'pytest | tee run.log'      pytest | tee run.log
        pwsh -Command 'pytest'              pytest
        bash script.sh                      None
        pytest tests                        None
    """
    leading_program = effective_leading_program(all_segment_tokens)
    if leading_program is None:
        return None
    if token_basename(_unquoted(leading_program)) not in ALL_STRING_EXECUTING_SHELL_BASENAMES:
        return None
    leading_index = all_segment_tokens.index(leading_program)
    all_argument_tokens = all_segment_tokens[leading_index + 1 :]
    for each_index, each_token in enumerate(all_argument_tokens):
        if each_token.lower() not in ALL_STRING_EXEC_COMMAND_FLAGS:
            continue
        inner_index = each_index + 1
        if inner_index >= len(all_argument_tokens):
            return None
        return all_argument_tokens[inner_index]
    return None


def _all_segments_with_following_operator(
    all_command_tokens: list[str],
) -> list[tuple[list[str], str]]:
    """Pair each simple-command segment with the control operator that ends it.

    A redirection token stays inside its segment, so ``pytest 2>&1 | tee x``
    keeps the pytest evidence the pipe check reads. A close paren stays inside
    too, so a subshell's pytest survives to the pipe that follows it.
    """
    all_segments: list[tuple[list[str], str]] = []
    current_segment: list[str] = []
    for each_token in all_command_tokens:
        if each_token in ALL_PIPE_OPERATOR_TOKENS or each_token in ALL_SEGMENT_RESET_OPERATOR_TOKENS:
            all_segments.append((current_segment, each_token))
            current_segment = []
            continue
        current_segment.append(each_token)
    all_segments.append((current_segment, NO_FOLLOWING_OPERATOR))
    return all_segments


def _tokenization_pipes_pytest(all_command_tokens: list[str]) -> bool:
    """Return True when a pytest segment feeds a pipe, at this level or inside a wrapper."""
    for each_segment, each_operator in _all_segments_with_following_operator(all_command_tokens):
        if each_operator in ALL_PIPE_OPERATOR_TOKENS and segment_runs_pytest(each_segment):
            return True
        inner_command = _string_exec_inner_command(each_segment)
        if inner_command is None:
            continue
        if find_piped_pytest_violation(inner_command) is not None:
            return True
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

    Joins each backslash-newline continuation into one logical line, splits the
    result on the newline and carriage-return terminators, then tokenizes each
    line so shell operators stand alone and quoted text stays whole. A pipe operator tests the segment that feeds it; a command separator
    starts a fresh segment; a redirection and a close paren stay inside the
    segment they belong to. A shell wrapper running a quoted string re-enters
    this check on that string.

    Args:
        command: The raw Bash command string from the tool input.

    Returns:
        The corrective deny message when a pytest segment feeds a pipe, else
        None.
    """
    joined_command = LINE_CONTINUATION_PATTERN.sub(LINE_CONTINUATION_JOIN, command)
    for each_command_line in COMMAND_LINE_SPLIT_PATTERN.split(joined_command):
        for each_tokenization in _all_operator_aware_tokenizations(each_command_line):
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
