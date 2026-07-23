"""Shared logic for the SessionStart directive-injection hooks.

Two SessionStart hooks decide whether to inject a directive and, when they do,
emit the same nested payload shape. This module carries the three decisions they
share: reading a default-on toggle from the environment, judging whether the
session source is one an injector acts on, and wrapping directive text in the
nested SessionStart output payload Claude Code reads.
"""

from __future__ import annotations

import os

from hooks_constants.session_start_injector_constants import (
    ADDITIONAL_CONTEXT_KEY,
    ALL_ELIGIBLE_SESSION_SOURCES,
    ALL_INJECTION_OFF_VALUES,
    HOOK_EVENT_NAME_KEY,
    HOOK_SPECIFIC_OUTPUT_KEY,
    SESSION_START_EVENT_NAME,
)


def is_injection_enabled(environment_variable_name: str) -> bool:
    """Report whether a default-on injector toggle is switched on.

    ::

        unset      -> on   (the default)
        "off"/"no" -> off
        "1"/"true" -> on

    An absent variable stays on. A present value counts as off only when it
    matches one of the off-values once lowercased and stripped.

    Args:
        environment_variable_name: Name of the environment toggle to read.

    Returns:
        True unless the variable holds a recognized off-value.
    """
    raw_value = os.environ.get(environment_variable_name)
    if raw_value is None:
        return True
    return raw_value.strip().lower() not in ALL_INJECTION_OFF_VALUES


def is_eligible_source(session_source: str) -> bool:
    """Report whether a SessionStart source is one an injector acts on.

    ::

        "startup" -> eligible
        "clear"   -> eligible
        "resume"  -> skip
        "compact" -> skip

    Args:
        session_source: The ``source`` field from the SessionStart payload.

    Returns:
        True when the source is a fresh start or a cleared session.
    """
    return session_source in ALL_ELIGIBLE_SESSION_SOURCES


def build_session_start_payload(directive_text: str) -> dict[str, dict[str, str]]:
    """Wrap directive text in the nested SessionStart output payload.

    ::

        build_session_start_payload("do X") -> {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": "do X",
            }
        }

    Args:
        directive_text: The instruction Claude reads at session start.

    Returns:
        The nested payload Claude Code reads for SessionStart additionalContext.
    """
    return {
        HOOK_SPECIFIC_OUTPUT_KEY: {
            HOOK_EVENT_NAME_KEY: SESSION_START_EVENT_NAME,
            ADDITIONAL_CONTEXT_KEY: directive_text,
        }
    }
