"""Constants shared by the SessionStart directive-injection hooks.

Holds the values that decide whether a SessionStart hook injects a directive and
the key names of the nested output payload it emits: the environment off-values
that switch a default-on injector off, the input sources that make a session
eligible for injection, the SessionStart payload field names the hooks read, and
the nested ``hookSpecificOutput`` payload keys and event name the hooks write.
"""

from __future__ import annotations

__all__ = [
    "ALL_INJECTION_OFF_VALUES",
    "ALL_ELIGIBLE_SESSION_SOURCES",
    "SESSION_SOURCE_FIELD_KEY",
    "SESSION_CWD_FIELD_KEY",
    "HOOK_SPECIFIC_OUTPUT_KEY",
    "HOOK_EVENT_NAME_KEY",
    "ADDITIONAL_CONTEXT_KEY",
    "SESSION_START_EVENT_NAME",
]

ALL_INJECTION_OFF_VALUES: frozenset[str] = frozenset({"0", "false", "off", "no"})

_SESSION_SOURCE_STARTUP = "startup"
_SESSION_SOURCE_CLEAR = "clear"
ALL_ELIGIBLE_SESSION_SOURCES: frozenset[str] = frozenset(
    {_SESSION_SOURCE_STARTUP, _SESSION_SOURCE_CLEAR}
)

SESSION_SOURCE_FIELD_KEY = "source"
SESSION_CWD_FIELD_KEY = "cwd"

HOOK_SPECIFIC_OUTPUT_KEY = "hookSpecificOutput"
HOOK_EVENT_NAME_KEY = "hookEventName"
ADDITIONAL_CONTEXT_KEY = "additionalContext"
SESSION_START_EVENT_NAME = "SessionStart"
