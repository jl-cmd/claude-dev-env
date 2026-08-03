#!/usr/bin/env python3
"""SessionStart hook — opt-in orchestrator context via shared injector.

Default off. When CLAUDE_ORCHESTRATOR_AUTO_STARTER_ENABLED is set, emit an
additionalContext directive that points the session at the orchestrator skill.
Disabled paths exit without calling the injector (no timeout budget spent).

Manual /orchestrator and the orchestrator agent definition are unchanged.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.orchestrator_auto_starter_constants import (  # noqa: E402
    ALL_ORCHESTRATOR_STARTER_ENABLED_ENV_VALUES,
    ORCHESTRATOR_AUTO_STARTER_ENABLED_ENV_VAR,
    ORCHESTRATOR_SESSION_START_DIRECTIVE,
    ORCHESTRATOR_STARTER_TIMEOUT_MILLISECONDS,
)
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)
from hooks_constants.session_start_injector import (  # noqa: E402
    InjectorConfiguration,
    build_additional_context_payload,
    inject_session_start_context,
)
from hooks_constants.session_start_injector_constants import (  # noqa: E402
    ALL_KNOWN_SESSION_START_SOURCES,
)


def orchestrator_auto_starter_enabled_in_environment() -> bool:
    """Return True only when the opt-in env var holds an enabled value."""
    raw_setting = os.environ.get(ORCHESTRATOR_AUTO_STARTER_ENABLED_ENV_VAR, "")
    return raw_setting.strip().lower() in ALL_ORCHESTRATOR_STARTER_ENABLED_ENV_VALUES


def build_orchestrator_injector_configuration(
    timeout_milliseconds: int,
) -> InjectorConfiguration:
    """Build injector config that injects the orchestrator directive per source.

    Args:
        timeout_milliseconds: Injector budget; zero or less yields timeout status.
    """
    context_by_source = {
        each_source: ORCHESTRATOR_SESSION_START_DIRECTIVE
        for each_source in ALL_KNOWN_SESSION_START_SOURCES
    }
    return InjectorConfiguration(
        is_enabled=True,
        timeout_milliseconds=timeout_milliseconds,
        context_by_source=context_by_source,
        default_context_for_unknown="",
    )


def run_orchestrator_auto_starter(
    payload_by_key: dict[str, object],
    is_enabled: bool,
    timeout_milliseconds: int,
) -> dict[str, str]:
    """Return additionalContext payload when opt-in injects, else empty dict.

    Args:
        payload_by_key: Parsed SessionStart payload.
        is_enabled: When False, return empty without calling the injector.
        timeout_milliseconds: Injector timeout budget.

    Returns:
        ``{"additionalContext": ...}`` when injected, else ``{}``.
    """
    if not is_enabled:
        return {}
    configuration = build_orchestrator_injector_configuration(timeout_milliseconds)
    injection_result = inject_session_start_context(payload_by_key, configuration)
    return build_additional_context_payload(injection_result)


def main() -> None:
    """Emit orchestrator additionalContext when opt-in is enabled; else exit 0."""
    payload_by_key = read_hook_input_dictionary_from_stdin()
    if payload_by_key is None:
        return
    payload = run_orchestrator_auto_starter(payload_by_key, orchestrator_auto_starter_enabled_in_environment(), ORCHESTRATOR_STARTER_TIMEOUT_MILLISECONDS)
    if payload:
        print(json.dumps(payload))


if __name__ == "__main__":
    main()
