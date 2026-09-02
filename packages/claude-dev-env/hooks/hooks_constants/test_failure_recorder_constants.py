"""Constants for the failing-test-run PostToolUse recorder hook.

Holds the cheap substring check the hook runs before any shell parsing, the
harness's own exit-code error prefix, the chaining and redirection operator
tokens that keep the recognizer to one unchained command, the pytest program
and Python interpreter basenames, and the flag-token marker the path
extractor uses to skip an option rather than an existing test file argument.

``BASH_TOOL_NAME`` lives in ``gh_pr_author_swap_constants`` already; this
module reuses that name rather than a second literal. The pytest-program and
interpreter recognition here is deliberately its own small, stdlib-only
check rather than a reuse of ``piped_pytest_blocker_constants`` /
``pytest_invocation``: those solve the harder pipe-and-wrapper problem and
pull in a much larger transitive import for every Bash call regardless of
content, working against the point of the recognizer's own cheap prefilter.
"""

from __future__ import annotations

import re

ALL_PYTEST_MENTION_SUBSTRINGS: tuple[str, ...] = ("pytest", "py.test")
EXIT_CODE_ERROR_PREFIX: str = "Error: Exit code "
OPTION_TOKEN_PREFIX: str = "-"
NODE_ID_FILE_PATH_SEPARATOR: str = "::"
ALL_CHAINING_OPERATOR_SUBSTRINGS: tuple[str, ...] = ("&&", "||", ";", "|", "\n")
ALL_REDIRECTION_TOKENS: frozenset[str] = frozenset(
    {">", ">>", "<", "<<", "2>&1", "1>&2", "2>", "1>"}
)
ALL_PYTEST_PROGRAM_BASENAMES: frozenset[str] = frozenset({"pytest", "py.test"})
MODULE_RUN_FLAG: str = "-m"
PYTEST_MODULE_NAME: str = "pytest"
PYTHON_INTERPRETER_BASENAME_PATTERN: re.Pattern[str] = re.compile(
    r"^(?:python|py|pypy)[0-9.]*(?:\.exe)?$"
)
