"""Named constants for converge pacer selection.

Consumed by ``select_converge_pacer.py``. Pacer names are the only values the
skill hubs and the portable driver accept.
"""

from __future__ import annotations

ENTRY_SKILL_PR_CONVERGE: str = "pr-converge"
ENTRY_SKILL_AUTOCONVERGE: str = "autoconverge"
ALL_ENTRY_SKILLS: tuple[str, ...] = (
    ENTRY_SKILL_PR_CONVERGE,
    ENTRY_SKILL_AUTOCONVERGE,
)

PACER_WORKFLOW: str = "workflow"
PACER_SCHEDULE_WAKEUP: str = "schedule_wakeup"
PACER_PORTABLE: str = "portable"
ALL_PACERS: tuple[str, ...] = (
    PACER_WORKFLOW,
    PACER_SCHEDULE_WAKEUP,
    PACER_PORTABLE,
)

CLI_SKILL_FLAG: str = "--skill"
CLI_HAS_WORKFLOW_FLAG: str = "--has-workflow"
CLI_HAS_SCHEDULE_WAKEUP_FLAG: str = "--has-schedule-wakeup"

RESULT_KEY_PACER: str = "pacer"
RESULT_KEY_ENTRY_SKILL: str = "entry_skill"
RESULT_KEY_HAS_WORKFLOW: str = "has_workflow"
RESULT_KEY_HAS_SCHEDULE_WAKEUP: str = "has_schedule_wakeup"

ALL_TRUTHY_FLAG_TOKENS: frozenset[str] = frozenset(
    {"1", "true", "yes", "on", "y", "t"}
)
ALL_FALSY_FLAG_TOKENS: frozenset[str] = frozenset(
    {"0", "false", "no", "off", "n", "f"}
)

ENTRY_SKILL_JOIN_SEPARATOR: str = ", "

UNKNOWN_ENTRY_SKILL_ERROR: str = (
    "entry skill must be one of {allowed}; got {got!r}"
)
INVALID_BOOL_FLAG_ERROR: str = (
    "flag value must be a boolean token (0/1, true/false, yes/no, on/off); "
    "got {got!r}"
)

EXIT_SUCCESS: int = 0
EXIT_USAGE_ERROR: int = 2
