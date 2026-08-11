"""Classify whether a parsed simple-command segment runs pytest.

Takes operator-stripped segment tokens and reports whether that segment invokes
pytest — as a bare program, through a Python interpreter ``-m``, through a
pass-through wrapper, or through a shell string-exec command.

::

    segment_runs_pytest(["pytest", "tests"])                 True
    segment_runs_pytest(["python", "-m", "pytest"])          True
    segment_runs_pytest(["uv", "run", "pytest", "tests"])    True
    segment_runs_pytest(["python", "myscript.py", "-m", "pytest"])  False
    segment_runs_pytest(["uv", "run", "--with", "pytest", "mypy", "."])  False

Shell parsing (tokenization, heredoc drop, segment pairing) lives in
``shell_command_pipeline``. Pipeline deny decisions stay with the blocker.
This module only answers "does this segment run pytest?"
"""

from __future__ import annotations

from hooks_constants.piped_pytest_blocker_constants import (
    ALL_CLUSTERED_STRING_EXEC_OPTION_LETTERS,
    ALL_FLAG_TAKING_WRAPPER_COMMANDS,
    ALL_PYTEST_PROGRAM_BASENAMES,
    ALL_QUOTE_CHARACTERS,
    ALL_RUN_SUBCOMMAND_WRAPPER_COMMANDS,
    ALL_SHORT_OPTION_CLUSTERING_SHELL_BASENAMES,
    ALL_STRING_EXEC_COMMAND_FLAGS,
    ALL_STRING_EXECUTING_SHELL_BASENAMES,
    ALL_VALUE_TAKING_INTERPRETER_OPTION_FLAGS,
    ALL_VALUE_TAKING_SHELL_OPTION_FLAGS,
    ALL_VALUE_TAKING_WRAPPER_OPTION_FLAGS,
    COMMAND_OPTION_TOKEN_PATTERN,
    END_OF_OPTIONS_TOKEN,
    MODULE_RUN_FLAG,
    PYTEST_MODULE_NAME,
    PYTHON_INTERPRETER_BASENAME_PATTERN,
    RUN_SUBCOMMAND_NAME,
    SHORT_OPTION_CLUSTER_PATTERN,
    SHORT_OPTION_PREFIX,
    TOOL_SUBCOMMAND_NAME,
    WRAPPED_COMMAND_TOKEN_JOIN,
)
from hooks_constants.shell_command_pipeline import (
    all_operator_aware_tokenizations,
    segments_with_following_operator,
)
from hooks_constants.shell_command_segments import (
    effective_leading_program,
    token_basename,
)

__all__ = [
    "segment_reports_a_pytest_exit_code",
    "segment_runs_pytest",
    "string_exec_inner_command",
    "unquoted_token",
]


def unquoted_token(token: str) -> str:
    """Return a token with its surrounding shell quotes removed.

    Args:
        token: One shell token, possibly quoted.

    Returns:
        The same token with leading and trailing quote characters stripped.
    """
    return token.strip(ALL_QUOTE_CHARACTERS)


def _glued_module_name(token: str) -> str | None:
    """Return the module name glued onto a ``-m`` flag, or None for any other token.

    ::

        -mpytest   pytest
        -mmypy     mypy
        -m         None
    """
    stripped_token = unquoted_token(token)
    if not stripped_token.startswith(MODULE_RUN_FLAG):
        return None
    return stripped_token[len(MODULE_RUN_FLAG) :] or None


def _some_module_run_flag_names_pytest(all_tokens: list[str]) -> bool:
    """Return True when any ``-m`` among the tokens names pytest."""
    for each_index, each_token in enumerate(all_tokens):
        if _glued_module_name(each_token) == PYTEST_MODULE_NAME:
            return True
        if each_token != MODULE_RUN_FLAG:
            continue
        module_index = each_index + 1
        if module_index >= len(all_tokens):
            continue
        if unquoted_token(all_tokens[module_index]) == PYTEST_MODULE_NAME:
            return True
    return False


def _clustered_option_value_token_count(
    stripped_token: str, all_value_taking_flags: frozenset[str]
) -> int:
    """Return how many tokens a short-option cluster takes as its last flag value."""
    all_cluster_letters = stripped_token[len(SHORT_OPTION_PREFIX) :]
    last_letter_position = len(all_cluster_letters) - 1
    for each_position, each_letter in enumerate(all_cluster_letters):
        if SHORT_OPTION_PREFIX + each_letter not in all_value_taking_flags:
            continue
        return int(each_position == last_letter_position)
    return 0


def _option_value_token_count(
    stripped_token: str, all_value_taking_flags: frozenset[str]
) -> int:
    """Return how many tokens after an option token are that option's value."""
    if stripped_token in all_value_taking_flags:
        return 1
    if SHORT_OPTION_CLUSTER_PATTERN.fullmatch(stripped_token) is None:
        return 0
    return _clustered_option_value_token_count(stripped_token, all_value_taking_flags)


def _all_tokens_from_the_interpreter_module_flag(
    all_interpreter_argument_tokens: list[str],
) -> list[str] | None:
    """Return tokens from the interpreter's own ``-m`` on, or None when it has none."""
    scan_index = 0
    while scan_index < len(all_interpreter_argument_tokens):
        each_token = all_interpreter_argument_tokens[scan_index]
        stripped_token = unquoted_token(each_token)
        if stripped_token == MODULE_RUN_FLAG or _glued_module_name(each_token) is not None:
            return all_interpreter_argument_tokens[scan_index:]
        if COMMAND_OPTION_TOKEN_PATTERN.match(stripped_token) is None:
            return None
        scan_index += 1 + _option_value_token_count(
            stripped_token, ALL_VALUE_TAKING_INTERPRETER_OPTION_FLAGS
        )
    return None


def _runs_pytest_as_a_module(all_interpreter_argument_tokens: list[str]) -> bool:
    """Return True when the interpreter's own ``-m`` reaches a pytest run."""
    all_module_tokens = _all_tokens_from_the_interpreter_module_flag(
        all_interpreter_argument_tokens
    )
    if all_module_tokens is None:
        return False
    return _some_module_run_flag_names_pytest(all_module_tokens)


def _all_tokens_from_the_first_operand(all_tokens: list[str]) -> list[str]:
    """Return the tokens from the first non-option one on, dropping option flags."""
    all_remaining_tokens = all_tokens
    while all_remaining_tokens:
        stripped_token = unquoted_token(all_remaining_tokens[0])
        if stripped_token == END_OF_OPTIONS_TOKEN:
            return all_remaining_tokens[1:]
        if COMMAND_OPTION_TOKEN_PATTERN.match(stripped_token) is None:
            return all_remaining_tokens
        flag_value_token_count = _option_value_token_count(
            stripped_token, ALL_VALUE_TAKING_WRAPPER_OPTION_FLAGS
        )
        all_remaining_tokens = all_remaining_tokens[1 + flag_value_token_count :]
    return []


def _all_tokens_after_one_wrapper(all_segment_tokens: list[str]) -> list[str] | None:
    """Return the tokens a single leading pass-through wrapper runs, else None."""
    leading_program = effective_leading_program(all_segment_tokens)
    if leading_program is None:
        return None
    program_basename = token_basename(unquoted_token(leading_program))
    leading_index = all_segment_tokens.index(leading_program)
    all_argument_tokens = _all_tokens_from_the_first_operand(
        all_segment_tokens[leading_index + 1 :]
    )
    if program_basename in ALL_FLAG_TAKING_WRAPPER_COMMANDS:
        return all_argument_tokens
    if program_basename not in ALL_RUN_SUBCOMMAND_WRAPPER_COMMANDS:
        return None
    if all_argument_tokens and unquoted_token(all_argument_tokens[0]) == TOOL_SUBCOMMAND_NAME:
        all_argument_tokens = _all_tokens_from_the_first_operand(all_argument_tokens[1:])
    if not all_argument_tokens or unquoted_token(all_argument_tokens[0]) != RUN_SUBCOMMAND_NAME:
        return None
    return _all_tokens_from_the_first_operand(all_argument_tokens[1:])


def _all_tokens_after_wrappers(all_segment_tokens: list[str]) -> list[str]:
    """Return the segment tokens with every leading pass-through wrapper stepped over."""
    all_remaining_tokens = all_segment_tokens
    while True:
        all_stepped_tokens = _all_tokens_after_one_wrapper(all_remaining_tokens)
        if all_stepped_tokens is None:
            return all_remaining_tokens
        all_remaining_tokens = all_stepped_tokens


def segment_runs_pytest(all_segment_tokens: list[str]) -> bool:
    """Return True when a simple-command segment invokes pytest.

    ::

        ['pytest', 'tests']                         True
        ['python', '-m', 'pytest']                  True
        ['python', '-mpytest']                      True
        ['time', 'pytest', 'tests']                 True
        ['sudo', 'pytest', 'tests']                 True
        ['uv', 'run', 'pytest', 'tests']            True
        ['C:\\\\Python313\\\\python.exe', '-m', 'pytest']  True
        ['python', '-m', 'mypy']                    False
        ['git', 'status']                           False
        ['python', 'myscript.py', '-m', 'pytest']   False
        ['uv', 'run', '--with', 'pytest', 'mypy']   False
        []                                          False

    Args:
        all_segment_tokens: Tokens of one simple command, operators removed.

    Returns:
        True when the segment's program is pytest or a Python interpreter
        running the pytest module, including through pass-through wrappers.
    """
    all_unwrapped_tokens = _all_tokens_after_wrappers(all_segment_tokens)
    leading_program = effective_leading_program(all_unwrapped_tokens)
    if leading_program is None:
        return False
    program_basename = token_basename(unquoted_token(leading_program))
    if program_basename in ALL_PYTEST_PROGRAM_BASENAMES:
        return True
    if not PYTHON_INTERPRETER_BASENAME_PATTERN.fullmatch(program_basename):
        return False
    interpreter_index = all_unwrapped_tokens.index(leading_program)
    return _runs_pytest_as_a_module(all_unwrapped_tokens[interpreter_index + 1 :])


def _clustered_string_exec_flag_offset(stripped_token: str) -> int | None:
    """Return how far past a cluster its command string sits, or None when absent."""
    if SHORT_OPTION_CLUSTER_PATTERN.fullmatch(stripped_token) is None:
        return None
    all_cluster_letters = stripped_token[len(SHORT_OPTION_PREFIX) :]
    if not any(
        each_letter in ALL_CLUSTERED_STRING_EXEC_OPTION_LETTERS
        for each_letter in all_cluster_letters
    ):
        return None
    return sum(
        SHORT_OPTION_PREFIX + each_letter.lower() in ALL_VALUE_TAKING_SHELL_OPTION_FLAGS
        for each_letter in all_cluster_letters
    )


def _string_exec_flag_index(
    all_argument_tokens: list[str], *, clusters_short_options: bool
) -> int | None:
    """Return the index of a wrapper's string-exec flag, or None when it takes none."""
    scan_index = 0
    while scan_index < len(all_argument_tokens):
        stripped_token = unquoted_token(all_argument_tokens[scan_index])
        lowercased_token = stripped_token.lower()
        if lowercased_token == END_OF_OPTIONS_TOKEN:
            return None
        if lowercased_token in ALL_STRING_EXEC_COMMAND_FLAGS:
            return scan_index
        if clusters_short_options:
            clustered_flag_offset = _clustered_string_exec_flag_offset(stripped_token)
            if clustered_flag_offset is not None:
                return scan_index + clustered_flag_offset
        if COMMAND_OPTION_TOKEN_PATTERN.match(lowercased_token) is None:
            return None
        scan_index += 1 + _option_value_token_count(
            lowercased_token, ALL_VALUE_TAKING_SHELL_OPTION_FLAGS
        )
    return None


def string_exec_inner_command(all_segment_tokens: list[str]) -> str | None:
    """Return the command string a shell wrapper runs, or None for any other segment.

    ::

        bash -c 'pytest | tee run.log'         pytest | tee run.log
        bash -euc 'pytest | tee run.log'       pytest | tee run.log
        pwsh -Command 'pytest'                 pytest
        cmd /c python -m pytest tests          python -m pytest tests
        bash scripts/ci.sh -c 'pytest tests'   None
        pytest tests                           None

    Args:
        all_segment_tokens: Tokens of one simple command, operators removed.

    Returns:
        The inner command string the shell executes, or None when the segment
        is not a string-executing shell wrapper with a command string.
    """
    all_unwrapped_tokens = _all_tokens_after_wrappers(all_segment_tokens)
    leading_program = effective_leading_program(all_unwrapped_tokens)
    if leading_program is None:
        return None
    shell_basename = token_basename(unquoted_token(leading_program))
    if shell_basename not in ALL_STRING_EXECUTING_SHELL_BASENAMES:
        return None
    leading_index = all_unwrapped_tokens.index(leading_program)
    all_argument_tokens = all_unwrapped_tokens[leading_index + 1 :]
    flag_index = _string_exec_flag_index(
        all_argument_tokens,
        clusters_short_options=shell_basename in ALL_SHORT_OPTION_CLUSTERING_SHELL_BASENAMES,
    )
    if flag_index is None:
        return None
    inner_index = flag_index + 1
    if inner_index >= len(all_argument_tokens):
        return None
    return WRAPPED_COMMAND_TOKEN_JOIN.join(all_argument_tokens[inner_index:])


def _wrapped_command_runs_pytest(inner_command: str) -> bool:
    """Return True when the command string a shell wrapper runs invokes pytest."""
    for each_tokenization in all_operator_aware_tokenizations(inner_command):
        for each_segment, _each_operator in segments_with_following_operator(
            each_tokenization
        ):
            if segment_runs_pytest(each_segment):
                return True
    return False


def segment_reports_a_pytest_exit_code(all_segment_tokens: list[str]) -> bool:
    """Return True when the segment's exit code is pytest's, directly or via a wrapper.

    ::

        ['pytest', 'tests']                  True
        ['bash', '-c', 'pytest tests']       True
        ['bash', 'script.sh']                False
        ['python', '-m', 'pytest']           True

    Args:
        all_segment_tokens: Tokens of one simple command, operators removed.

    Returns:
        True when the segment runs pytest, or a shell wrapper whose command
        string runs pytest (so the shell exits with pytest's code).
    """
    if segment_runs_pytest(all_segment_tokens):
        return True
    inner_command = string_exec_inner_command(all_segment_tokens)
    if inner_command is None:
        return False
    return _wrapped_command_runs_pytest(inner_command)
