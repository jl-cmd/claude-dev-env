"""Constants for the orchestrator-refresh ScheduleWakeup reschedule gate."""

from __future__ import annotations

SCHEDULE_WAKEUP_TOOL_NAME = "ScheduleWakeup"
CRON_CREATE_TOOL_NAME = "CronCreate"
ALL_SCHEDULE_TOOL_NAMES: frozenset[str] = frozenset(
    {
        SCHEDULE_WAKEUP_TOOL_NAME,
        CRON_CREATE_TOOL_NAME,
    }
)

ORCHESTRATOR_REFRESH_PROMPT_TOKEN = "/orchestrator-refresh"
RUN_SLUG_PROMPT_FLAG = "--run-slug"
RUN_SLUG_PROMPT_VALUE_PATTERN = r"(?:=\s*|\s+)([^\s]+)"
PROMPT_FIELD_NAME = "prompt"
TOOL_NAME_FIELD_NAME = "tool_name"
TOOL_INPUT_FIELD_NAME = "tool_input"
CWD_FIELD_NAME = "cwd"

REASON_CRON_CREATE_FORBIDDEN = "cron_create_forbidden"

DENY_REASON_TEMPLATE = (
    "BLOCKED: orchestrator-refresh re-arm denied ({reason}). "
    "Use one-shot delayed wake only (never CronCreate / never recurring). "
    "At most one re-arm slot: begin-firing at refresh start, claim-rearm "
    "before schedule create, release-rearm if create fails. "
    "Status must be active: "
    "python skills/orchestrator/scripts/status_gate.py set "
    "--status active. When finished: --status done. Never re-arm an idle loop."
)

CALLING_HOOK_NAME = "orchestrator_refresh_reschedule_gate.py"
HOOK_EVENT_NAME = "PreToolUse"

ALL_SKILL_SCRIPTS_RELATIVE_PARTS: tuple[str, ...] = (
    "skills",
    "orchestrator",
    "scripts",
)
PLUGIN_ROOT_ENV_VAR = "CLAUDE_PLUGIN_ROOT"
ALL_HOME_SKILLS_RELATIVE_PARTS: tuple[str, ...] = (
    ".claude",
    "skills",
    "orchestrator",
    "scripts",
)
