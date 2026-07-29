"""Constants for the piped-pytest PreToolUse Bash blocker.

Holds the tool names, the pytest program basenames and the python-interpreter
basename pattern, the module-run flag and module name, the pipe and
segment-reset operator token sets, the line-continuation and physical-line
patterns, the heredoc-opener pattern that marks a script body, the
comment-start pattern that ends a line early, the parenthesis-group counters
that join a multi-line subshell, the group-closing reserved words a pipe reads
a group's status through, the option-token pattern that separates a wrapper's
flags from its first operand, the wrapper commands whose run passes through to
the program behind them, the separator that rejoins a wrapper's argument
tokens, the empty commenter set that leaves ``#`` to the comment-start pattern,
the quote characters stripped before a basename read, and the deny message.
Segment helpers come from ``shell_command_segments.py``.

Two wrapper shapes reach the program behind them differently. ``sudo`` and
``uvx`` take their own option flags and then the command, so the step-over drops
the flags. ``uv``, ``poetry``, ``pipenv``, ``pdm``, ``hatch``, ``rye``, and
``coverage`` take the literal ``run`` subcommand first, so the step-over reads
that word and passes only when it is there — ``uv sync`` and ``coverage report``
keep the wrapper as its own program. ``uv`` spells the same pass-through as
``uv tool run`` too, so ``TOOL_SUBCOMMAND_NAME`` names the word the step-over
reads before it looks for ``run``. A ``run`` subcommand takes its own flags too,
so the step-over drops those before it reads the program.

An option that takes a separate value swallows the token after it, so
``sudo -u someone pytest`` runs pytest while ``uv run --with pytest mypy .``
runs mypy. ``ALL_VALUE_TAKING_WRAPPER_OPTION_FLAGS`` names those flags so the
operand scan reads past the value rather than mistaking it for the program, and
``ALL_VALUE_TAKING_SHELL_OPTION_FLAGS`` does the same for the shells that run a
command string, so the ``-c`` behind ``bash -o pipefail`` stays visible. POSIX
lets short options cluster, and a cluster's value is the next token only when
the value-taking letter ends the cluster — ``sudo -nu ci`` takes ``ci`` while
``sudo -nuci`` carries the value glued on. ``SHORT_OPTION_CLUSTER_PATTERN``
marks the tokens that walk letter by letter for that reading.
``--`` ends an option list outright: every token after it is an operand however
it is spelled, so ``bash -- -c script`` runs a script named ``-c`` rather than a
command string.

A POSIX shell reads ``-c`` inside a cluster as well, so ``bash -euc 'pytest'``
runs the command string the same way ``bash -c 'pytest'`` does.
``ALL_CLUSTERED_STRING_EXEC_OPTION_LETTERS`` names the letters that carry that
reading, and ``ALL_SHORT_OPTION_CLUSTERING_SHELL_BASENAMES`` limits it to the
shells that cluster: PowerShell spells its options as words, where the ``c`` in
``-NonInteractive`` is a letter of a name rather than an option of its own. The
letter check reads the token in its own case, because ``-C`` is bash's noclobber
switch while ``-c`` takes the command string.

A heredoc delimiter is any shell word, so the opener pattern takes one written
bare, quoted, or backslash-escaped (``<<\\EOF`` quotes the delimiter the way
``<<'EOF'`` does). ``<<<`` is a here-string rather than a heredoc, so the
pattern refuses to read one as an opener and leave the lines below it unread.
The opener also reports its own ``-``, because ``<<`` closes on a line spelling
the delimiter exactly while ``<<-`` closes on one carrying leading tabs.

The string-executing shell basenames and command flags start from the shared
``unscoped_search_blocker_constants.py`` sets and add the Windows command shell
(``cmd /c "…"``) on top, locally. Widening the shared sets themselves would hand
``cmd`` unwrapping to ``unscoped_search_blocker`` as a side effect of a
piped-pytest fix, so the addition stays in this module and that blocker keeps
its current behavior.

The operator sets partition ``ALL_SHELL_CONTROL_OPERATOR_TOKENS``. That
derivation covers the operator inventory only; quote-awareness stays local to
the blocker's own lexer.
"""

from __future__ import annotations

import re

from hooks_constants.shell_command_segments import ALL_SHELL_CONTROL_OPERATOR_TOKENS
from hooks_constants.unscoped_search_blocker_constants import (
    ALL_STRING_EXEC_COMMAND_FLAGS as _ALL_SHARED_STRING_EXEC_COMMAND_FLAGS,
)
from hooks_constants.unscoped_search_blocker_constants import (
    ALL_STRING_EXECUTING_SHELL_BASENAMES as _ALL_SHARED_STRING_EXECUTING_SHELL_BASENAMES,
)

__all__ = [
    "BASH_TOOL_NAME",
    "ALL_SUPPORTED_TOOL_NAMES",
    "ALL_PYTEST_PROGRAM_BASENAMES",
    "PYTHON_INTERPRETER_BASENAME_PATTERN",
    "MODULE_RUN_FLAG",
    "PYTEST_MODULE_NAME",
    "ALL_PIPE_OPERATOR_TOKENS",
    "ALL_SEGMENT_RESET_OPERATOR_TOKENS",
    "ALL_OPERATOR_TOKENS_LONGEST_FIRST",
    "PUNCTUATION_ONLY_TOKEN_PATTERN",
    "ALL_REDIRECTION_SUFFIX_CHARACTERS",
    "ALL_STRING_EXECUTING_SHELL_BASENAMES",
    "ALL_STRING_EXEC_COMMAND_FLAGS",
    "ALL_CLUSTERED_STRING_EXEC_OPTION_LETTERS",
    "ALL_SHORT_OPTION_CLUSTERING_SHELL_BASENAMES",
    "COMMAND_OPTION_TOKEN_PATTERN",
    "SHORT_OPTION_CLUSTER_PATTERN",
    "SHORT_OPTION_PREFIX",
    "END_OF_OPTIONS_TOKEN",
    "ALL_VALUE_TAKING_WRAPPER_OPTION_FLAGS",
    "ALL_VALUE_TAKING_SHELL_OPTION_FLAGS",
    "ALL_FLAG_TAKING_WRAPPER_COMMANDS",
    "ALL_RUN_SUBCOMMAND_WRAPPER_COMMANDS",
    "RUN_SUBCOMMAND_NAME",
    "TOOL_SUBCOMMAND_NAME",
    "WRAPPED_COMMAND_TOKEN_JOIN",
    "DISABLED_LEXER_COMMENTERS",
    "LINE_CONTINUATION_PATTERN",
    "LINE_CONTINUATION_JOIN",
    "COMMAND_LINE_SPLIT_PATTERN",
    "QUOTED_REGION_PATTERN",
    "QUOTED_REGION_REPLACEMENT",
    "COMMENT_START_SCAN_PATTERN",
    "COMMENT_START_GROUP",
    "GROUP_OPEN_CHARACTER",
    "GROUP_CLOSE_CHARACTER",
    "ALL_GROUP_CLOSE_TOKENS",
    "PAREN_GROUP_LINE_JOIN",
    "CLOSED_GROUP_DEPTH",
    "HEREDOC_OPENER_PATTERN",
    "HEREDOC_TAB_STRIP_GROUP",
    "HEREDOC_QUOTE_GROUP",
    "HEREDOC_TERMINATOR_GROUP",
    "HEREDOC_TAB_STRIP_MARKER",
    "HEREDOC_STRIPPED_INDENT_CHARACTERS",
    "NO_FOLLOWING_OPERATOR",
    "ALL_QUOTE_CHARACTERS",
    "HOOK_EVENT_NAME",
    "DENY_DECISION",
    "CALLING_HOOK_NAME",
    "CORRECTIVE_MESSAGE",
]

BASH_TOOL_NAME = "Bash"
ALL_SUPPORTED_TOOL_NAMES: frozenset[str] = frozenset({BASH_TOOL_NAME})

ALL_PYTEST_PROGRAM_BASENAMES: frozenset[str] = frozenset(
    {
        "pytest",
        "pytest.exe",
        "pytest.bat",
        "pytest.cmd",
        "py.test",
        "py.test.exe",
        "py.test.bat",
        "py.test.cmd",
    }
)
PYTHON_INTERPRETER_BASENAME_PATTERN = re.compile(
    r"^(?:(?:python|pypy)w?[0-9._]*t?|pyw?)(?:\.exe|\.bat|\.cmd)?$"
)
MODULE_RUN_FLAG = "-m"
PYTEST_MODULE_NAME = "pytest"

_ALL_PIPE_OPERATOR_SPELLINGS: frozenset[str] = frozenset({"|", "|&"})
_ALL_LOCAL_SEGMENT_RESET_EXTRAS: frozenset[str] = frozenset({";;", "(", "{"})

ALL_PIPE_OPERATOR_TOKENS: frozenset[str] = (
    ALL_SHELL_CONTROL_OPERATOR_TOKENS & _ALL_PIPE_OPERATOR_SPELLINGS
)
ALL_SEGMENT_RESET_OPERATOR_TOKENS: frozenset[str] = (
    ALL_SHELL_CONTROL_OPERATOR_TOKENS - ALL_PIPE_OPERATOR_TOKENS
) | _ALL_LOCAL_SEGMENT_RESET_EXTRAS

ALL_OPERATOR_TOKENS_LONGEST_FIRST: tuple[str, ...] = tuple(
    sorted(
        ALL_PIPE_OPERATOR_TOKENS | ALL_SEGMENT_RESET_OPERATOR_TOKENS,
        key=len,
        reverse=True,
    )
)
PUNCTUATION_ONLY_TOKEN_PATTERN = re.compile(r"[();<>|&]+")
ALL_REDIRECTION_SUFFIX_CHARACTERS: tuple[str, ...] = ("<", ">")

_ALL_WINDOWS_COMMAND_SHELL_BASENAMES: frozenset[str] = frozenset({"cmd", "cmd.exe"})
_ALL_WINDOWS_COMMAND_SHELL_FLAGS: frozenset[str] = frozenset({"/c", "/k"})
ALL_STRING_EXECUTING_SHELL_BASENAMES: frozenset[str] = (
    _ALL_SHARED_STRING_EXECUTING_SHELL_BASENAMES | _ALL_WINDOWS_COMMAND_SHELL_BASENAMES
)
ALL_STRING_EXEC_COMMAND_FLAGS: frozenset[str] = (
    _ALL_SHARED_STRING_EXEC_COMMAND_FLAGS | _ALL_WINDOWS_COMMAND_SHELL_FLAGS
)
ALL_CLUSTERED_STRING_EXEC_OPTION_LETTERS: frozenset[str] = frozenset({"c"})
ALL_SHORT_OPTION_CLUSTERING_SHELL_BASENAMES: frozenset[str] = frozenset(
    {"bash", "bash.exe", "sh", "sh.exe"}
)
COMMAND_OPTION_TOKEN_PATTERN = re.compile(r"^(?:-.*|/[A-Za-z])$")
SHORT_OPTION_CLUSTER_PATTERN = re.compile(r"-[A-Za-z]{2,}")
SHORT_OPTION_PREFIX = "-"
END_OF_OPTIONS_TOKEN = "--"
ALL_VALUE_TAKING_WRAPPER_OPTION_FLAGS: frozenset[str] = frozenset(
    {
        "-C",
        "-D",
        "-R",
        "-T",
        "-U",
        "-g",
        "-h",
        "-p",
        "-r",
        "-t",
        "-u",
        "--concurrency",
        "--context",
        "--data-file",
        "--directory",
        "--env-file",
        "--extra",
        "--from",
        "--group",
        "--include",
        "--omit",
        "--package",
        "--project",
        "--python",
        "--rcfile",
        "--source",
        "--user",
        "--with",
    }
)
ALL_VALUE_TAKING_SHELL_OPTION_FLAGS: frozenset[str] = frozenset(
    {
        "-o",
        "--rcfile",
        "--init-file",
        "-configurationname",
        "-custompipename",
        "-executionpolicy",
        "-inputformat",
        "-outputformat",
        "-settingsfile",
        "-version",
        "-windowstyle",
        "-workingdirectory",
    }
)

ALL_FLAG_TAKING_WRAPPER_COMMANDS: frozenset[str] = frozenset(
    {"sudo", "sudo.exe", "uvx", "uvx.exe"}
)
ALL_RUN_SUBCOMMAND_WRAPPER_COMMANDS: frozenset[str] = frozenset(
    {
        "uv",
        "uv.exe",
        "poetry",
        "poetry.exe",
        "pipenv",
        "pipenv.exe",
        "pdm",
        "pdm.exe",
        "hatch",
        "hatch.exe",
        "rye",
        "rye.exe",
        "coverage",
        "coverage.exe",
    }
)
RUN_SUBCOMMAND_NAME = "run"
TOOL_SUBCOMMAND_NAME = "tool"
WRAPPED_COMMAND_TOKEN_JOIN = " "
DISABLED_LEXER_COMMENTERS = ""

LINE_CONTINUATION_PATTERN = re.compile(r"\\(?:\r\n|[\r\n])")
LINE_CONTINUATION_JOIN = ""
COMMAND_LINE_SPLIT_PATTERN = re.compile(r"[\n\r]+")
QUOTED_REGION_PATTERN = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"|\\.")
QUOTED_REGION_REPLACEMENT = ""
COMMENT_START_GROUP = "comment_start"
COMMENT_START_SCAN_PATTERN = re.compile(
    rf"'[^']*'|\"(?:\\.|[^\"\\])*\"|\\.|(?P<{COMMENT_START_GROUP}>(?<![^\s])#)"
)
GROUP_OPEN_CHARACTER = "("
GROUP_CLOSE_CHARACTER = ")"
_BRACE_GROUP_CLOSE_TOKEN = "}"
ALL_GROUP_CLOSE_TOKENS: frozenset[str] = frozenset(
    {GROUP_CLOSE_CHARACTER, _BRACE_GROUP_CLOSE_TOKEN}
)
PAREN_GROUP_LINE_JOIN = " "
CLOSED_GROUP_DEPTH = 0
_HEREDOC_DELIMITER_CHARACTER_CLASS = r"[^\s'\"<>|&;()`$\\]"
HEREDOC_TAB_STRIP_GROUP = "heredoc_tab_strip"
HEREDOC_QUOTE_GROUP = "heredoc_quote"
HEREDOC_TERMINATOR_GROUP = "heredoc_terminator"
HEREDOC_OPENER_PATTERN = re.compile(
    rf"(?<!<)<<(?!<)(?P<{HEREDOC_TAB_STRIP_GROUP}>-?)\s*(?P<{HEREDOC_QUOTE_GROUP}>['\"]?)\\?"
    rf"(?P<{HEREDOC_TERMINATOR_GROUP}>{_HEREDOC_DELIMITER_CHARACTER_CLASS}+)"
    rf"(?P={HEREDOC_QUOTE_GROUP})"
)
HEREDOC_TAB_STRIP_MARKER = "-"
HEREDOC_STRIPPED_INDENT_CHARACTERS = "\t"
NO_FOLLOWING_OPERATOR = ""
ALL_QUOTE_CHARACTERS = "\"'"

HOOK_EVENT_NAME = "PreToolUse"
DENY_DECISION = "deny"
CALLING_HOOK_NAME = "piped_pytest_blocker.py"

CORRECTIVE_MESSAGE = (
    "Piped pytest run blocked. Run pytest alone; the pipe makes the tool report "
    "the downstream command's exit code, so a failing suite reads as a pass. "
    "When you need the output on disk, redirect it "
    "(`python -m pytest tests > run.log 2>&1`) and read the file."
)
