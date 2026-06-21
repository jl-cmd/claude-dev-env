"""Configuration constants for the code_verifier_spawn_preflight_gate hook.

The gate denies an ``Agent`` spawn whose ``subagent_type`` is ``code-verifier``
when the branch carries a merge conflict against its base ref or a CODE_RULES
violation on a line added in the uncommitted working tree. It runs two
pre-flight checks before the expensive verification spawn and addresses its
deny reason to the spawning agent so that agent fixes the named issues and
re-spawns. Every literal the hook body reads lives here; the hook imports
``AGENT_TOOL_NAME`` from ``pr_converge_bugteam_enforcer_constants`` rather than
redefining it.
"""

from __future__ import annotations

from pathlib import Path

CODE_VERIFIER_SUBAGENT_TYPE: str = "code-verifier"

ALL_MERGE_TREE_COMMAND_FLAGS: tuple[str, ...] = (
    "merge-tree",
    "--write-tree",
    "--name-only",
)
MERGE_TREE_CONFLICT_EXIT_CODE: int = 1
MERGE_TREE_CLEAN_EXIT_CODE: int = 0
MERGE_TREE_TIMEOUT_SECONDS: int = 30

ALL_NAME_ONLY_WORKTREE_DIFF_FLAGS: tuple[str, ...] = (
    "-c",
    "core.quotePath=false",
    "diff",
    "--name-only",
    "--no-renames",
)
ALL_UNIFIED_ZERO_DIFF_FLAGS: tuple[str, ...] = ("diff", "--unified=0")

DENY_REASON_LEAD: str = (
    "BLOCKED [code-verifier-spawn-preflight]: an Agent spawn with subagent_type "
    "code-verifier is blocked because the branch is not in a committable state. "
    "Fix these, then re-spawn the code-verifier:"
)
MERGE_CONFLICT_SECTION_HEADER: str = "Merge conflicts vs {base_ref}:"
CODE_RULES_SECTION_HEADER: str = "CODE_RULES violations on changed lines:"

GATE_SCRIPTS_RELATIVE_PATH: Path = Path("_shared") / "pr-loop" / "scripts"
