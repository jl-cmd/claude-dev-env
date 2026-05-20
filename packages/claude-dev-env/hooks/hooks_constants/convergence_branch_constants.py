"""Convergence branch naming policy constants.

Shared by destructive_command_blocker convergence-branch exemptions
and convergence_gate_blocker pre-flight checks.
"""

ALL_CONVERGENCE_BRANCH_PREFIXES: tuple[str, ...] = ("claude/", "worktree-")
CONVERGENCE_BRANCH_SUFFIX_PATTERN: str = r"pr-.*-converge$"
CONVERGENCE_FORCE_PUSH_DETECTION_PATTERN: str = r"\bgit\s+push\b\s+(.*(?:--force|-f)\b.*)"
