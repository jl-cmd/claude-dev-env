"""Constants for the shared SessionStart context injector.

Claude Code SessionStart payloads carry ``source`` as one of::

    startup | resume | clear | compact

Unknown sources map to a safe default status without blocking the session.
"""

from __future__ import annotations

SESSION_START_SOURCE_PAYLOAD_KEY: str = "source"

SESSION_START_SOURCE_STARTUP: str = "startup"
SESSION_START_SOURCE_RESUME: str = "resume"
SESSION_START_SOURCE_CLEAR: str = "clear"
SESSION_START_SOURCE_COMPACT: str = "compact"

ALL_KNOWN_SESSION_START_SOURCES: frozenset[str] = frozenset(
    {
        SESSION_START_SOURCE_STARTUP,
        SESSION_START_SOURCE_RESUME,
        SESSION_START_SOURCE_CLEAR,
        SESSION_START_SOURCE_COMPACT,
    }
)

SESSION_START_SOURCE_UNKNOWN: str = "unknown"

INJECTION_STATUS_OK: str = "ok"
INJECTION_STATUS_DISABLED: str = "disabled"
INJECTION_STATUS_TIMEOUT: str = "timeout"
INJECTION_STATUS_UNKNOWN_SOURCE: str = "unknown_source"

ALL_INJECTION_STATUSES: frozenset[str] = frozenset(
    {
        INJECTION_STATUS_OK,
        INJECTION_STATUS_DISABLED,
        INJECTION_STATUS_TIMEOUT,
        INJECTION_STATUS_UNKNOWN_SOURCE,
    }
)

SESSION_START_INJECTOR_ENABLED_ENV_VAR: str = "CLAUDE_SESSION_START_INJECTOR_ENABLED"
ALL_INJECTOR_ENABLED_ENV_VALUES: frozenset[str] = frozenset({"1", "true", "yes", "on"})
DEFAULT_INJECTOR_TIMEOUT_MILLISECONDS: int = 50

ALL_DEFAULT_CONTEXT_BY_SOURCE: dict[str, str] = {
    SESSION_START_SOURCE_STARTUP: "",
    SESSION_START_SOURCE_RESUME: "",
    SESSION_START_SOURCE_CLEAR: "",
    SESSION_START_SOURCE_COMPACT: "",
}

