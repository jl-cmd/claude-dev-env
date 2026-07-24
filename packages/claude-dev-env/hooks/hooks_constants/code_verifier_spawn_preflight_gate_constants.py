"""Configuration constants for the code_verifier_spawn_preflight_gate hook.

The gate denies an ``Agent`` or ``Task`` spawn whose ``subagent_type`` is
``code-verifier`` when a staged CODE_RULES attestation is absent, malformed, or
stale for the worktree, HEAD, or index tree. It also denies merge conflicts,
CODE_RULES violations on working-tree-added lines, and a CODE_RULES engine
import/load failure. It runs those checks before the expensive verification
spawn and addresses its deny reason to the spawning agent so that agent fixes
the named issues and re-spawns. Every literal the hook body reads lives here;
``AGENT_TOOL_NAME`` comes from
``pr_converge_bugteam_enforcer_constants`` and joins ``TASK_TOOL_NAME`` in
``ALL_CODE_VERIFIER_SPAWN_TOOL_NAMES`` so both spawn tool names share one source.
"""

from __future__ import annotations

from pathlib import Path

from hooks_constants.pr_converge_bugteam_enforcer_constants import AGENT_TOOL_NAME

CODE_VERIFIER_SUBAGENT_TYPE: str = "code-verifier"
TASK_TOOL_NAME: str = "Task"
ALL_CODE_VERIFIER_SPAWN_TOOL_NAMES: frozenset[str] = frozenset(
    {AGENT_TOOL_NAME, TASK_TOOL_NAME}
)

ALL_MERGE_TREE_COMMAND_FLAGS: tuple[str, ...] = (
    "merge-tree",
    "--write-tree",
    "--name-only",
)
MERGE_TREE_CONFLICT_EXIT_CODE: int = 1
MERGE_TREE_CLEAN_EXIT_CODE: int = 0
MERGE_TREE_TIMEOUT_SECONDS: int = 30

ALL_MERGE_HEAD_PROBE_FLAGS: tuple[str, ...] = ("rev-parse", "--verify", "--quiet", "MERGE_HEAD")
ALL_UNMERGED_PATHS_DIFF_FLAGS: tuple[str, ...] = ("diff", "--name-only", "--diff-filter=U")

ALL_NAME_ONLY_WORKTREE_DIFF_FLAGS: tuple[str, ...] = (
    "-c",
    "core.quotePath=false",
    "diff",
    "--name-only",
    "--no-renames",
)
ALL_UNIFIED_ZERO_DIFF_FLAGS: tuple[str, ...] = ("diff", "--unified=0")

DENY_REASON_LEAD: str = (
    "BLOCKED [code-verifier-spawn-preflight]: a code-verifier spawn "
    "(Agent or Task tool, subagent_type code-verifier) is blocked because "
    "the branch is not in a committable state. "
    "Fix these, then re-spawn the code-verifier:"
)
MERGE_CONFLICT_SECTION_HEADER: str = "Merge conflicts vs {base_ref}:"
CODE_RULES_SECTION_HEADER: str = "CODE_RULES violations on changed lines:"
STAGED_ATTESTATION_SECTION: str = (
    "Staged CODE_RULES attestation is missing, malformed, or stale. Run "
    "code_rules_gate.py --staged and repair every reported check before "
    "re-spawning code-verifier."
)
BASE_RESOLUTION_FAILURE_SECTION: str = (
    "Base reference could not be resolved:\n"
    "  The code-verifier spawn requires a local merge base. Configure or fetch "
    "the base reference, then re-spawn code-verifier."
)
ENGINE_LOAD_FAILURE_SECTION: str = (
    "CODE_RULES engine failed to load:\n"
    "  The CODE_RULES validate_content engine could not be imported or loaded "
    "(package import/load failure). Repair the enforcer so load_validate_content "
    "succeeds, then re-spawn code-verifier."
)

GATE_SCRIPTS_RELATIVE_PATH: Path = Path("_shared") / "pr-loop" / "scripts"
