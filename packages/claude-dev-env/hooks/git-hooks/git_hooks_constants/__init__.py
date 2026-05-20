"""Constants for the claude-dev-env git-hook entry points.

Co-located with ``pre_commit.py`` and ``pre_push.py`` so the installed shim
directory is self-contained at runtime: the shim prepends its own directory
to ``sys.path`` before importing the hook module, which makes ``from config
import ...`` resolve against this file both inside the repo and under
``~/.claude/hooks/git-hooks/`` after installation.
"""

from __future__ import annotations


STAGED_SCOPE_ARGUMENT: str = "--staged"
BASE_REFERENCE_ARGUMENT: str = "--base"
DEFAULT_REMOTE_BASE_REFERENCE: str = "origin/HEAD"
ALL_ZEROS_OBJECT_NAME_CHARACTER: str = "0"
STDIN_LINE_FIELD_COUNT: int = 4
STDIN_REMOTE_OBJECT_FIELD_INDEX: int = 3
GATE_PATH_OVERRIDE_ENV_VAR: str = "CODE_RULES_GATE_PATH"
CLAUDE_HOME_ENV_VAR: str = "CLAUDE_HOME"
CLAUDE_HOME_DEFAULT_SUBDIRECTORY: str = ".claude"
GATE_SCRIPT_RELATIVE_PATH: tuple[str, ...] = (
    "_shared",
    "pr-loop",
    "scripts",
    "code_rules_gate.py",
)
GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE: int = 2
GATE_SCRIPT_NOT_FOUND_MESSAGE: str = (
    "claude-dev-env pre-commit: gate script not found at {path}, skipping enforcement"
)
PRE_PUSH_GATE_SCRIPT_NOT_FOUND_MESSAGE: str = (
    "claude-dev-env pre-push: gate script not found at {path}, skipping enforcement"
)
STDIN_READ_FAILURE_MESSAGE: str = (
    "claude-dev-env pre-push: could not read stdin ({error}), aborting"
)
INVOKE_GATE_FAILURE_MESSAGE: str = (
    "claude-dev-env: could not launch gate script ({error}), aborting"
)
MALFORMED_STDIN_LINE_MESSAGE: str = (
    "claude-dev-env pre-push: ignoring malformed stdin line: {line!r}"
)
LOCAL_SHA_FIELD_INDEX: int = 1
NO_PARSEABLE_STDIN_LINES_MESSAGE: str = (
    "claude-dev-env pre-push: no parseable stdin lines; aborting"
)
NO_PARSEABLE_STDIN_LINES_SENTINEL: str = "__no_parseable_stdin_lines__"
