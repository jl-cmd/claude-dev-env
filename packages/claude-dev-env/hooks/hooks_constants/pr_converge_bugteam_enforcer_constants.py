"""Configuration constants for the pr_converge_bugteam_enforcer hook pair.

The enforcer denies ``Agent({subagent_type: "clean-coder"})`` invocations that
substitute audit-shaped work for the formal ``Skill({skill: "bugteam"})`` call
during Step 5 BUGTEAM of the pr-converge loop. The tracker records every
formal ``Skill({skill: "bugteam"})`` invocation so the enforcer can confirm
the Skill fired this tick at the current HEAD before allowing follow-on
clean-coder spawns.
"""

from __future__ import annotations

AGENT_TOOL_NAME: str = "Agent"
SKILL_TOOL_NAME: str = "Skill"

CLEAN_CODER_SUBAGENT_TYPE: str = "clean-coder"
BUGTEAM_SKILL_NAME: str = "bugteam"

PR_CONVERGE_STATE_FILENAME: str = "pr-converge-state.json"
CLAUDE_JOB_DIR_ENV_VAR: str = "CLAUDE_JOB_DIR"

BUGTEAM_PHASE: str = "BUGTEAM"

STATE_FIELD_PHASE: str = "phase"
STATE_FIELD_CURRENT_HEAD: str = "current_head"
STATE_FIELD_TICK_COUNT: str = "tick_count"
STATE_FIELD_BUGTEAM_SKILL_INVOKED_AT_HEAD: str = "bugteam_skill_invoked_at_head"
STATE_FIELD_BUGTEAM_SKILL_INVOKED_AT_TICK: str = "bugteam_skill_invoked_at_tick"

ALL_AUDIT_PROMPT_SUBSTRINGS: tuple[str, ...] = (
    "audit",
    "findings",
    "bugteam",
    "a-j categor",
    "code-quality",
    "verify_clean",
    "converge",
)

ENFORCER_CORRECTIVE_MESSAGE: str = (
    "BLOCKED [pr-converge-bugteam-enforcer]: Step 5 BUGTEAM advances ONLY after "
    '`Skill({skill: "bugteam", args: "<PR URL>"})` fires this tick at the '
    'current HEAD. Substituting an `Agent({subagent_type: "clean-coder"})` '
    "audit call for the formal Skill invocation is a protocol violation — the "
    "formal Skill writes the artifact `check_convergence.py`'s `bugteam_clean_at` "
    "gate looks for, and a substituted audit silently bypasses that gate.\n\n"
    "`qbug` is NOT an accepted substitute — `bugteam` is the only allowed skill "
    "at this step.\n\n"
    'Run `Skill({skill: "bugteam", args: "<PR URL>"})` first. Follow-on '
    "clean-coder fix spawns are allowed once the formal Skill has registered at "
    "the current HEAD and tick."
)

STATE_FILE_ATOMIC_WRITE_SUFFIX: str = ".tmp"
STATE_FILE_JSON_INDENT_SPACES: int = 2
