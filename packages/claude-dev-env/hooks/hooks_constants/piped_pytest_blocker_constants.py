"""Constants for the piped-pytest PreToolUse Bash blocker.

Holds the tool names, the pytest program basenames and the python-interpreter
basename pattern, the module-run flag and module name, the pipe and
segment-reset operator token sets, the quote characters stripped before a
basename read, and the deny message. Segment helpers come from
``shell_command_segments.py``.
"""

from __future__ import annotations

import re

__all__ = [
    "BASH_TOOL_NAME",
    "ALL_SUPPORTED_TOOL_NAMES",
    "ALL_PYTEST_PROGRAM_BASENAMES",
    "PYTHON_INTERPRETER_BASENAME_PATTERN",
    "MODULE_RUN_FLAG",
    "PYTEST_MODULE_NAME",
    "ALL_PIPE_OPERATOR_TOKENS",
    "ALL_SEGMENT_RESET_OPERATOR_TOKENS",
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

ALL_PIPE_OPERATOR_TOKENS: frozenset[str] = frozenset({"|", "|&"})
ALL_SEGMENT_RESET_OPERATOR_TOKENS: frozenset[str] = frozenset(
    {"&&", "||", ";", ";;", "&", "(", ")"}
)
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
