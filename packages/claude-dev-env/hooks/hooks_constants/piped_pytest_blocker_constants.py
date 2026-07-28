"""Constants for the piped-pytest PreToolUse Bash blocker.

Holds the tool names, the pytest program basenames and the python-interpreter
basename pattern, the module-run flag and module name, the pipe and
segment-reset operator token sets, the line-continuation and physical-line
patterns, the heredoc-opener pattern that marks a script body, the quote
characters stripped before a basename read, and the deny message. Segment
helpers come from ``shell_command_segments.py``; the string-executing shell
basenames and command flags come from ``unscoped_search_blocker_constants.py``,
so both re-entering blockers read one set.

The operator sets partition ``ALL_SHELL_CONTROL_OPERATOR_TOKENS``. That
derivation covers the operator inventory only; quote-awareness stays local to
the blocker's own lexer.
"""

from __future__ import annotations

import re

from hooks_constants.shell_command_segments import ALL_SHELL_CONTROL_OPERATOR_TOKENS
from hooks_constants.unscoped_search_blocker_constants import (
    ALL_STRING_EXEC_COMMAND_FLAGS,
    ALL_STRING_EXECUTING_SHELL_BASENAMES,
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
    "ALL_STRING_EXECUTING_SHELL_BASENAMES",
    "ALL_STRING_EXEC_COMMAND_FLAGS",
    "LINE_CONTINUATION_PATTERN",
    "LINE_CONTINUATION_JOIN",
    "COMMAND_LINE_SPLIT_PATTERN",
    "HEREDOC_OPENER_PATTERN",
    "HEREDOC_TERMINATOR_GROUP",
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
    {"pytest", "pytest.exe", "py.test", "py.test.exe"}
)
PYTHON_INTERPRETER_BASENAME_PATTERN = re.compile(r"^(?:python[0-9._]*|py)(?:\.exe)?$")
MODULE_RUN_FLAG = "-m"
PYTEST_MODULE_NAME = "pytest"

_ALL_PIPE_OPERATOR_SPELLINGS: frozenset[str] = frozenset({"|", "|&"})
_ALL_LOCAL_SEGMENT_RESET_EXTRAS: frozenset[str] = frozenset({";;", "("})

ALL_PIPE_OPERATOR_TOKENS: frozenset[str] = (
    ALL_SHELL_CONTROL_OPERATOR_TOKENS & _ALL_PIPE_OPERATOR_SPELLINGS
)
ALL_SEGMENT_RESET_OPERATOR_TOKENS: frozenset[str] = (
    ALL_SHELL_CONTROL_OPERATOR_TOKENS - ALL_PIPE_OPERATOR_TOKENS
) | _ALL_LOCAL_SEGMENT_RESET_EXTRAS

LINE_CONTINUATION_PATTERN = re.compile(r"\\(?:\r\n|[\r\n])")
LINE_CONTINUATION_JOIN = ""
COMMAND_LINE_SPLIT_PATTERN = re.compile(r"[\n\r]+")
HEREDOC_OPENER_PATTERN = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
HEREDOC_TERMINATOR_GROUP = 2
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
