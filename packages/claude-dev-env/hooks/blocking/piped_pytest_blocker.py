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
    (python -m pytest tests)|tee run.log        flag: no space before the pipe
    (pytest tests)|(tee run.log)                flag: one subshell into another
    (<newline>pytest tests<newline>) | tee x    flag: subshell across lines
    bash -c 'pytest | tee run.log'              flag: pipeline inside a wrapper
    cmd /c "pytest tests | tee run.log"         flag: Windows shell wrapper
    cmd /c python -m pytest tests | tee x       flag: unquoted wrapper argument
    pytest tests#tag | tee run.log              flag: a hash inside a word
    # note <<EOF<newline>pytest | tee x         flag: a heredoc named in a comment
    bash -c 'pytest tests' | tee run.log        flag: wrapper piped from outside
    python -m coverage run -m pytest | cat      flag: a later -m names pytest
    time pytest tests | tee run.log             flag: launcher wrapper
    pytest tests \\<newline>| tee run.log       flag: one continued line
    { pytest tests; } | tee run.log             flag: brace group feeds a pipe
    pytest.bat tests | tee run.log              flag: Windows shim
    sudo pytest tests | tee run.log             flag: sudo passes the run through
    uv run pytest tests | tee run.log           flag: a run subcommand wrapper
    uv run --frozen pytest tests | tee x        flag: a flag before the program
    sudo -u ci pytest tests | tee run.log       flag: -u takes the name after it
    pytest tests > run.log 2>&1                 ok:   redirection keeps the code
    pytest tests  # | tee run.log               ok:   the pipe sits in a comment
    pytest tests                                ok:   pytest alone
    git status | head                           ok:   segment carries no pytest
    cat ids.txt | pytest --stdin                ok:   the pipe feeds into pytest
    pytest tests -q<newline>git status | head   ok:   the pipe sits on a later line
    cp file{a,b}.txt dst | tee log              ok:   a brace expansion, no group
    sudo apt update | tee log                   ok:   sudo runs another program
    bash ci.sh -c 'pytest tests' | tee run.log  ok:   the -c belongs to the script
    bash -- -c 'pytest tests' | tee run.log     ok:   -- makes -c a script name
    uv run --with pytest mypy . | tee log       ok:   --with takes the name after
    cat > run.sh <<'EOF'<newline>pytest | tee x<newline>EOF   ok: a heredoc body
    cat > run.sh <<\\EOF<newline>pytest | tee x<newline>EOF   ok: escaped delimiter

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
    ALL_FLAG_TAKING_WRAPPER_COMMANDS,
    ALL_GROUP_CLOSE_TOKENS,
    ALL_OPERATOR_TOKENS_LONGEST_FIRST,
    ALL_PIPE_OPERATOR_TOKENS,
    ALL_PYTEST_PROGRAM_BASENAMES,
    ALL_QUOTE_CHARACTERS,
    ALL_REDIRECTION_SUFFIX_CHARACTERS,
    ALL_RUN_SUBCOMMAND_WRAPPER_COMMANDS,
    ALL_SEGMENT_RESET_OPERATOR_TOKENS,
    ALL_STRING_EXEC_COMMAND_FLAGS,
    ALL_STRING_EXECUTING_SHELL_BASENAMES,
    ALL_SUPPORTED_TOOL_NAMES,
    ALL_VALUE_TAKING_WRAPPER_OPTION_FLAGS,
    CALLING_HOOK_NAME,
    CLOSED_GROUP_DEPTH,
    COMMAND_LINE_SPLIT_PATTERN,
    COMMAND_OPTION_TOKEN_PATTERN,
    COMMENT_START_GROUP,
    COMMENT_START_SCAN_PATTERN,
    CORRECTIVE_MESSAGE,
    DENY_DECISION,
    DISABLED_LEXER_COMMENTERS,
    END_OF_OPTIONS_TOKEN,
    GROUP_CLOSE_CHARACTER,
    GROUP_OPEN_CHARACTER,
    HEREDOC_OPENER_PATTERN,
    HEREDOC_TERMINATOR_GROUP,
    HOOK_EVENT_NAME,
    LINE_CONTINUATION_JOIN,
    LINE_CONTINUATION_PATTERN,
    MODULE_RUN_FLAG,
    NO_FOLLOWING_OPERATOR,
    PAREN_GROUP_LINE_JOIN,
    PUNCTUATION_ONLY_TOKEN_PATTERN,
    PYTEST_MODULE_NAME,
    PYTHON_INTERPRETER_BASENAME_PATTERN,
    QUOTED_REGION_PATTERN,
    QUOTED_REGION_REPLACEMENT,
    RUN_SUBCOMMAND_NAME,
    WRAPPED_COMMAND_TOKEN_JOIN,
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

    The lexer's own commenters are cleared, because it cuts at a ``#`` anywhere
    in a word while a shell starts a comment only at a word's start. Leaving the
    default in place drops the rest of ``pytest tests#tag | tee run.log`` and
    hides the pipe. ``_command_line_without_comment`` owns comment removal and
    applies the shell's rule.
    """
    all_tokenizations: list[list[str]] = []
    for each_posix_mode in (True, False):
        lexer = shlex.shlex(command, posix=each_posix_mode, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.commenters = DISABLED_LEXER_COMMENTERS
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
    """Return True when any ``-m`` in the segment names pytest.

    ::

        ['python', '-m', 'pytest']                            flag
        ['python', '-mpytest']                                flag
        ['python', '-m', 'coverage', 'run', '-m', 'pytest']   flag: a later -m
        ['python', '-m', 'mypy']                              ok
        ['python', '-m']                                      ok

    A runner module such as coverage or debugpy takes its own ``-m``, so the
    scan reads every one rather than stopping at the first.

    Args:
        all_segment_tokens: The tokens of one simple command, operators removed.

    Returns:
        True when some ``-m pytest`` or ``-mpytest`` appears in the segment.
    """
    for each_index, each_token in enumerate(all_segment_tokens):
        if _glued_module_name(each_token) == PYTEST_MODULE_NAME:
            return True
        if each_token != MODULE_RUN_FLAG:
            continue
        module_index = each_index + 1
        if module_index >= len(all_segment_tokens):
            continue
        if _unquoted(all_segment_tokens[module_index]) == PYTEST_MODULE_NAME:
            return True
    return False


def _all_tokens_from_the_first_operand(all_tokens: list[str]) -> list[str]:
    """Return the tokens from the first non-option one on, dropping the option flags.

    ::

        ['-n', 'pytest', 'tests']            ['pytest', 'tests']
        ['-u', 'someone', 'pytest']          ['pytest']   -u takes the name
        ['--with', 'pytest', 'mypy', '.']    ['mypy', '.']   --with takes a name
        ['--', '-c', 'run.sh']               ['-c', 'run.sh']   -- ends the flags
        ['run', 'pytest']                    ['run', 'pytest']
        ['-n']                               []

    A flag that takes a separate value swallows the token after it, so the
    operand the wrapper runs is the token past that value rather than the value
    itself. ``--`` ends the option list outright, and every token after it is an
    operand however it is spelled.

    Args:
        all_tokens: The tokens following a wrapper command, in order.

    Returns:
        The tokens from the wrapper's first operand on, empty when it has none.
    """
    all_remaining_tokens = all_tokens
    while all_remaining_tokens:
        unquoted_token = _unquoted(all_remaining_tokens[0])
        if unquoted_token == END_OF_OPTIONS_TOKEN:
            return all_remaining_tokens[1:]
        if COMMAND_OPTION_TOKEN_PATTERN.match(unquoted_token) is None:
            return all_remaining_tokens
        flag_value_token_count = int(unquoted_token in ALL_VALUE_TAKING_WRAPPER_OPTION_FLAGS)
        all_remaining_tokens = all_remaining_tokens[1 + flag_value_token_count :]
    return []


def _all_tokens_after_one_wrapper(all_segment_tokens: list[str]) -> list[str] | None:
    """Return the tokens a single leading pass-through wrapper runs, else None.

    ::

        ['sudo', 'pytest', 'tests']                 ['pytest', 'tests']
        ['uv', 'run', 'pytest', 'tests']            ['pytest', 'tests']
        ['uv', 'run', '--frozen', 'pytest']         ['pytest']
        ['sudo', 'apt', 'update']                   ['apt', 'update']
        ['uv', 'sync']                              None   no ``run`` subcommand
        ['pytest', 'tests']                         None   no wrapper leads

    ``sudo`` runs whatever follows its own flags, so the step-over drops the
    flags and keeps the rest. ``uv``, ``poetry``, and ``pipenv`` run a program
    only behind the literal ``run`` subcommand, so any other subcommand leaves
    the wrapper as the program it already is. That subcommand takes flags of its
    own, so the step-over drops those too before it reads the program.
    """
    leading_program = effective_leading_program(all_segment_tokens)
    if leading_program is None:
        return None
    program_basename = token_basename(_unquoted(leading_program))
    leading_index = all_segment_tokens.index(leading_program)
    all_argument_tokens = _all_tokens_from_the_first_operand(
        all_segment_tokens[leading_index + 1 :]
    )
    if program_basename in ALL_FLAG_TAKING_WRAPPER_COMMANDS:
        return all_argument_tokens
    if program_basename not in ALL_RUN_SUBCOMMAND_WRAPPER_COMMANDS:
        return None
    if not all_argument_tokens or _unquoted(all_argument_tokens[0]) != RUN_SUBCOMMAND_NAME:
        return None
    return _all_tokens_from_the_first_operand(all_argument_tokens[1:])


def _all_tokens_after_wrappers(all_segment_tokens: list[str]) -> list[str]:
    """Return the segment tokens with every leading pass-through wrapper stepped over.

    ::

        ['sudo', 'uv', 'run', 'pytest']   ['pytest']
        ['git', 'status']                 ['git', 'status']

    Each step returns a strictly shorter token list, so the walk ends.
    """
    all_remaining_tokens = all_segment_tokens
    while True:
        all_stepped_tokens = _all_tokens_after_one_wrapper(all_remaining_tokens)
        if all_stepped_tokens is None:
            return all_remaining_tokens
        all_remaining_tokens = all_stepped_tokens


def segment_runs_pytest(all_segment_tokens: list[str]) -> bool:
    """Return True when a simple-command segment invokes pytest.

    ::

        ['pytest', 'tests']                         flag
        ['python', '-m', 'pytest']                  flag
        ['python', '-mpytest']                      flag
        ['time', 'pytest', 'tests']                 flag
        ['sudo', 'pytest', 'tests']                 flag
        ['uv', 'run', 'pytest', 'tests']            flag
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
    all_unwrapped_tokens = _all_tokens_after_wrappers(all_segment_tokens)
    leading_program = effective_leading_program(all_unwrapped_tokens)
    if leading_program is None:
        return False
    program_basename = token_basename(_unquoted(leading_program))
    if program_basename in ALL_PYTEST_PROGRAM_BASENAMES:
        return True
    if not PYTHON_INTERPRETER_BASENAME_PATTERN.fullmatch(program_basename):
        return False
    return _runs_pytest_as_a_module(all_unwrapped_tokens)


def _string_exec_flag_index(all_argument_tokens: list[str]) -> int | None:
    """Return the index of a wrapper's string-exec flag, or None when it takes none.

    ::

        ['-c', 'pytest tests']                 0
        ['-x', '-c', 'pytest tests']           1
        ['/c', 'python', '-m', 'pytest']       0
        ['scripts/ci.sh', '-c', 'pytest x']    None: the script is the operand
        ['--', '-c', 'pytest tests']           None: -- makes -c the script
        ['script.sh']                          None

    A string-exec flag counts only while it is still an option — that is, before
    the first operand. Once a script path appears the shell is running that
    script, and every later flag is the script's own argument rather than a
    command string the shell reads. ``--`` ends the options outright, so the
    ``-c`` behind one names a script file too.
    """
    for each_index, each_token in enumerate(all_argument_tokens):
        unquoted_token = _unquoted(each_token)
        if unquoted_token == END_OF_OPTIONS_TOKEN:
            return None
        if unquoted_token.lower() in ALL_STRING_EXEC_COMMAND_FLAGS:
            return each_index
        if COMMAND_OPTION_TOKEN_PATTERN.match(unquoted_token) is None:
            return None
    return None


def _string_exec_inner_command(all_segment_tokens: list[str]) -> str | None:
    """Return the command string a shell wrapper runs, or None for any other segment.

    ::

        bash -c 'pytest | tee run.log'         pytest | tee run.log
        pwsh -Command 'pytest'                 pytest
        cmd /c python -m pytest tests          python -m pytest tests
        bash scripts/ci.sh -c 'pytest tests'   None: the script takes the -c
        bash script.sh                         None
        pytest tests                           None

    Every token after the flag joins back into one string. A quoted inner
    command is one token already, so the join returns it unchanged; an unquoted
    one such as ``cmd /c python -m pytest tests`` spans several tokens, and
    reading only the first would see ``python`` alone and miss the pytest the
    ``-m`` names.
    """
    all_unwrapped_tokens = _all_tokens_after_wrappers(all_segment_tokens)
    leading_program = effective_leading_program(all_unwrapped_tokens)
    if leading_program is None:
        return None
    if token_basename(_unquoted(leading_program)) not in ALL_STRING_EXECUTING_SHELL_BASENAMES:
        return None
    leading_index = all_unwrapped_tokens.index(leading_program)
    all_argument_tokens = all_unwrapped_tokens[leading_index + 1 :]
    flag_index = _string_exec_flag_index(all_argument_tokens)
    if flag_index is None:
        return None
    inner_index = flag_index + 1
    if inner_index >= len(all_argument_tokens):
        return None
    return WRAPPED_COMMAND_TOKEN_JOIN.join(all_argument_tokens[inner_index:])


def _trailing_operator_token(token: str) -> str | None:
    """Return the longest control operator the token ends with, or None for any other token."""
    for each_operator in ALL_OPERATOR_TOKENS_LONGEST_FIRST:
        if token.endswith(each_operator):
            return each_operator
    return None


def _all_punctuation_token_parts(token: str) -> list[str]:
    """Split a punctuation-only token into its leading text and every trailing operator.

    ::

        )|      [')', '|']         a subshell closed right against a pipe
        )|&     [')', '|&']        the same against the stderr pipe
        )|(     [')', '|', '(']    one subshell piped straight into the next
        )||     [')', '||']        the longest operator wins, so this is no pipe
        >|      ['>|']             a clobber-override redirection, not a pipe
        |       ['|']              the whole token is already the operator
        tests   ['tests']          not punctuation only

    ``shlex`` with ``punctuation_chars=True`` glues consecutive punctuation into
    one token, so ``(pytest tests)|(tee x)`` arrives with ``)|(`` unsplit and the
    pipe invisible to the segment pairing. Peeling repeats until the leading text
    ends in no operator, so a token gluing several operators comes apart whole
    rather than surrendering its last one only.

    Args:
        token: One token from an operator-aware tokenization.

    Returns:
        The token's parts in their original order — a one-item list holding the
        token itself when it needs no splitting.
    """
    if PUNCTUATION_ONLY_TOKEN_PATTERN.fullmatch(token) is None:
        return [token]
    all_peeled_operators: list[str] = []
    remaining_text = token
    while True:
        trailing_operator = _trailing_operator_token(remaining_text)
        if trailing_operator is None or trailing_operator == remaining_text:
            break
        leading_text = remaining_text[: -len(trailing_operator)]
        if leading_text.endswith(ALL_REDIRECTION_SUFFIX_CHARACTERS):
            break
        all_peeled_operators.append(trailing_operator)
        remaining_text = leading_text
    return [remaining_text, *reversed(all_peeled_operators)]


def _all_operator_split_tokens(all_command_tokens: list[str]) -> list[str]:
    """Return the tokens with every glued punctuation-and-operator token split apart."""
    all_split_tokens: list[str] = []
    for each_token in all_command_tokens:
        all_split_tokens.extend(_all_punctuation_token_parts(each_token))
    return all_split_tokens


def _all_segments_with_following_operator(
    all_command_tokens: list[str],
) -> list[tuple[list[str], str]]:
    """Pair each simple-command segment with the control operator that ends it.

    A redirection token stays inside its segment, so ``pytest 2>&1 | tee x``
    keeps the pytest evidence the pipe check reads. A close paren stays inside
    too, so a subshell's pytest survives to the pipe that follows it — whether a
    space separates the two (``) | tee x``) or not (``)|tee x``).
    """
    all_segments: list[tuple[list[str], str]] = []
    current_segment: list[str] = []
    for each_token in _all_operator_split_tokens(all_command_tokens):
        if each_token in ALL_PIPE_OPERATOR_TOKENS or each_token in ALL_SEGMENT_RESET_OPERATOR_TOKENS:
            all_segments.append((current_segment, each_token))
            current_segment = []
            continue
        current_segment.append(each_token)
    all_segments.append((current_segment, NO_FOLLOWING_OPERATOR))
    return all_segments


def _wrapped_command_runs_pytest(inner_command: str) -> bool:
    """Return True when the command string a shell wrapper runs invokes pytest.

    ::

        pytest tests            flag
        python -m pytest -q     flag
        git status              ok
    """
    for each_tokenization in _all_operator_aware_tokenizations(inner_command):
        for each_segment, _ in _all_segments_with_following_operator(each_tokenization):
            if segment_runs_pytest(each_segment):
                return True
    return False


def _segment_reports_a_pytest_exit_code(all_segment_tokens: list[str]) -> bool:
    """Return True when the segment's exit code is pytest's, directly or through a wrapper.

    ::

        ['pytest', 'tests']                  flag
        ['bash', '-c', 'pytest tests']       flag: bash exits with pytest's code
        ['bash', 'script.sh']                ok
    """
    if segment_runs_pytest(all_segment_tokens):
        return True
    inner_command = _string_exec_inner_command(all_segment_tokens)
    if inner_command is None:
        return False
    return _wrapped_command_runs_pytest(inner_command)


def _holds_group_closers_only(all_segment_tokens: list[str]) -> bool:
    """Return True when the segment holds nothing but group-closing reserved words.

    ::

        ['}']                  True
        [')']                  True
        ['pytest', 'tests']    False
        []                     False
    """
    return bool(all_segment_tokens) and all(
        each_token in ALL_GROUP_CLOSE_TOKENS for each_token in all_segment_tokens
    )


def _all_status_reporting_tokens(
    all_segments: list[tuple[list[str], str]], segment_index: int
) -> list[str]:
    """Return the tokens whose exit code the segment at the index reports.

    ::

        { pytest tests; } | tee x   pytest tests   the group's last command
        pytest tests | tee x        pytest tests   the segment reports its own

    A brace group needs a terminator before its ``}``, so the closer lands in a
    segment of its own and a pipe after it reads the status of the command
    before it. Any segment carrying real words reports its own exit code.

    Args:
        all_segments: Every segment of one tokenization, paired with the
            operator that ends it.
        segment_index: The index of the segment the pipe follows.

    Returns:
        The tokens the pipe reads the exit code of, empty when only group
        closers precede it.
    """
    for each_index in range(segment_index, -1, -1):
        all_candidate_tokens = all_segments[each_index][0]
        if not _holds_group_closers_only(all_candidate_tokens):
            return all_candidate_tokens
    return []


def _tokenization_pipes_pytest(all_command_tokens: list[str]) -> bool:
    """Return True when a pytest segment feeds a pipe, at this level or inside a wrapper."""
    all_segments = _all_segments_with_following_operator(all_command_tokens)
    for each_index, (each_segment, each_operator) in enumerate(all_segments):
        if each_operator in ALL_PIPE_OPERATOR_TOKENS and _segment_reports_a_pytest_exit_code(
            _all_status_reporting_tokens(all_segments, each_index)
        ):
            return True
        inner_command = _string_exec_inner_command(each_segment)
        if inner_command is None:
            continue
        if find_piped_pytest_violation(inner_command) is not None:
            return True
    return False


def _all_live_command_lines(all_command_lines: list[str]) -> list[str]:
    """Return the lines the call runs, dropping every heredoc body and its terminator.

    ::

        cat > run.sh <<'EOF'          kept:    the redirection line runs
        pytest tests | tee out.log    dropped: script text, nothing runs
        EOF                           dropped: the terminator
        pytest tests | tee out.log    kept:    a live line below the heredoc

    A heredoc opener names the word that closes its body, so the lines between
    the two are text this call writes rather than commands it runs.

    Args:
        all_command_lines: The physical lines of one Bash command, in order.

    Returns:
        The lines outside every heredoc body, in their original order.
    """
    all_live_lines: list[str] = []
    pending_terminator: str | None = None
    for each_line in all_command_lines:
        if pending_terminator is not None:
            if each_line.strip() == pending_terminator:
                pending_terminator = None
            continue
        all_live_lines.append(each_line)
        heredoc_opener = HEREDOC_OPENER_PATTERN.search(each_line)
        if heredoc_opener is not None:
            pending_terminator = heredoc_opener.group(HEREDOC_TERMINATOR_GROUP)
    return all_live_lines


def _command_line_without_comment(command_line: str) -> str:
    """Return the line with a shell comment and everything after it removed.

    ::

        python -m pytest tests  # fast   python -m pytest tests
        # the fast run                   (nothing runs on this line)
        pytest -k "a#b"                  unchanged: the hash sits inside quotes
        tee run#1.log                    unchanged: the hash sits inside a word

    A comment ends at its own newline. Removing it here keeps the lines under it
    live once a parenthesis group joins them into one logical line, where a
    surviving hash would comment the joined pipe out instead.

    Args:
        command_line: One physical command line.

    Returns:
        The line up to its comment, or the whole line when it carries none.
    """
    for each_match in COMMENT_START_SCAN_PATTERN.finditer(command_line):
        if each_match.group(COMMENT_START_GROUP) is not None:
            return command_line[: each_match.start(COMMENT_START_GROUP)]
    return command_line


def _all_comment_free_lines(all_command_lines: list[str]) -> list[str]:
    """Return every line with its shell comment removed.

    ::

        # note the <<EOF form   (nothing runs on this line)
        pytest tests  # fast    pytest tests

    This runs before the heredoc scan, so a ``<<WORD`` written inside a comment
    opens no heredoc and cannot drop the live lines beneath it.

    Args:
        all_command_lines: The physical lines of one Bash command, in order.

    Returns:
        The comment-free lines, in their original order and count.
    """
    return [_command_line_without_comment(each_line) for each_line in all_command_lines]


def _paren_depth_change(command_line: str) -> int:
    """Return how many parenthesis groups the line opens, minus the ones it closes.

    Quoted text and backslash-escaped characters drop out first, so
    ``pytest -k "(a)"`` counts as no group at all.
    """
    unquoted_line = QUOTED_REGION_PATTERN.sub(QUOTED_REGION_REPLACEMENT, command_line)
    return unquoted_line.count(GROUP_OPEN_CHARACTER) - unquoted_line.count(GROUP_CLOSE_CHARACTER)


def _all_paren_group_joined_lines(all_command_lines: list[str]) -> list[str]:
    """Return the lines with each open parenthesis group joined into one logical line.

    ::

        (                            joined: the group is still open
        # the fast run               joined: a comment ends at its own newline
        python -m pytest tests       joined: the group is still open
        ) | tee run.log              ( python -m pytest tests ) | tee run.log
        pytest tests                 pytest tests

    A subshell opened on one line and closed on a later one is one command, so
    the pipe after the close paren belongs to the pytest run inside it. Comments
    are already gone by this point, so a parenthesis inside a comment opens no
    group and a comment never reaches across the newline that ends it.

    Args:
        all_command_lines: The live command lines, comments removed and heredoc
            bodies already dropped.

    Returns:
        One line per parenthesis group, and the unchanged line for every other.
    """
    all_joined_lines: list[str] = []
    all_pending_lines: list[str] = []
    open_group_depth = CLOSED_GROUP_DEPTH
    for each_line in all_command_lines:
        all_pending_lines.append(each_line)
        open_group_depth = max(
            open_group_depth + _paren_depth_change(each_line), CLOSED_GROUP_DEPTH
        )
        if open_group_depth > CLOSED_GROUP_DEPTH:
            continue
        all_joined_lines.append(PAREN_GROUP_LINE_JOIN.join(all_pending_lines))
        all_pending_lines = []
    if all_pending_lines:
        all_joined_lines.append(PAREN_GROUP_LINE_JOIN.join(all_pending_lines))
    return all_joined_lines


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
    result on the newline and carriage-return terminators, drops each line's
    comment, drops every heredoc body, joins the lines of each still-open
    parenthesis group, then tokenizes each remaining line so shell operators
    stand alone and quoted text stays whole. Comments go first, so a ``<<WORD``
    written inside one opens no heredoc; heredoc bodies go next, so a body
    inside a subshell is gone before the group join reads it and a ``(`` written
    into a heredoc opens no group. A
    pipe operator tests the segment that feeds it; a command separator
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
    all_command_lines = COMMAND_LINE_SPLIT_PATTERN.split(joined_command)
    all_live_lines = _all_live_command_lines(_all_comment_free_lines(all_command_lines))
    for each_command_line in _all_paren_group_joined_lines(all_live_lines):
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
