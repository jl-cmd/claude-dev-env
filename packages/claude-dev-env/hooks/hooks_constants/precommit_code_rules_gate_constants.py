"""Constants for the precommit_code_rules_gate PreToolUse hook.

Command parsing, git timeouts, and the staged-gate invocation surface used
to run the shared code_rules_gate engine before a git commit.
"""

from pathlib import Path

GIT_DASH_C_COMMIT_PATTERN: str = r"git\s+-C\s+[\"']?[^\"';&|]+?[\"']?\s+commit\b"
GIT_COMMAND_TIMEOUT_SECONDS: int = 5
GATE_TIMEOUT_SECONDS: int = 120
GATE_RELATIVE_PATH: Path = Path("_shared") / "pr-loop" / "scripts" / "code_rules_gate.py"
ALL_STAGED_PYTHON_FILES_COMMAND: tuple[str, ...] = (
    "git",
    "diff",
    "--cached",
    "--name-only",
    "--diff-filter=ACMR",
    "--",
    "*.py",
)
ALL_GIT_REPOSITORY_ROOT_COMMAND: tuple[str, ...] = (
    "git",
    "rev-parse",
    "--show-toplevel",
)
