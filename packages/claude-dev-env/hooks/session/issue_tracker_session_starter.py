#!/usr/bin/env python3
"""SessionStart hook — repository-gated issue-tracker context via shared injector.

Default off. When CLAUDE_ISSUE_TRACKER_SESSION_STARTER_ENABLED is set and the
session cwd's git root appears in ~/.claude/project-paths.json, emit an
additionalContext directive for the issue-tracker skill. Missing registry or
unregistered repos fail closed with no output.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.issue_tracker_session_starter_constants import (  # noqa: E402
    ALL_ISSUE_TRACKER_STARTER_ENABLED_ENV_VALUES,
    ISSUE_TRACKER_SESSION_START_DIRECTIVE,
    ISSUE_TRACKER_SESSION_STARTER_ENABLED_ENV_VAR,
    ISSUE_TRACKER_STARTER_TIMEOUT_MILLISECONDS,
)
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)
from hooks_constants.project_paths_reader import (  # noqa: E402
    find_git_root,
    load_registry,
    registry_contains_path,
)
from hooks_constants.session_start_injector import (  # noqa: E402
    InjectorConfiguration,
    build_additional_context_payload,
    inject_session_start_context,
)
from hooks_constants.session_start_injector_constants import (  # noqa: E402
    ALL_KNOWN_SESSION_START_SOURCES,
)


def issue_tracker_session_starter_enabled_in_environment() -> bool:
    """Return True only when the opt-in env var holds an enabled value."""
    raw_setting = os.environ.get(ISSUE_TRACKER_SESSION_STARTER_ENABLED_ENV_VAR, "")
    return raw_setting.strip().lower() in ALL_ISSUE_TRACKER_STARTER_ENABLED_ENV_VALUES


def repository_is_registered(
    working_directory: str,
    registry_by_name: dict[str, str],
) -> bool:
    """Return True when cwd git root is a value in the project-paths registry.

    Missing registry, missing git root, or unregistered root fail closed.

    Args:
        working_directory: Session cwd used to locate the git root.
        registry_by_name: Name-to-path map; empty map fails closed.
    """
    if not registry_by_name:
        return False
    git_root = find_git_root(working_directory)
    if git_root is None:
        return False
    return registry_contains_path(registry_by_name, git_root)


def build_issue_tracker_injector_configuration(
    timeout_milliseconds: int,
) -> InjectorConfiguration:
    """Build injector config with the issue-tracker directive per known source.

    Args:
        timeout_milliseconds: Injector budget; zero or less yields timeout status.
    """
    context_by_source = {
        each_source: ISSUE_TRACKER_SESSION_START_DIRECTIVE
        for each_source in ALL_KNOWN_SESSION_START_SOURCES
    }
    return InjectorConfiguration(
        is_enabled=True,
        timeout_milliseconds=timeout_milliseconds,
        context_by_source=context_by_source,
        default_context_for_unknown="",
    )


def run_issue_tracker_session_starter(
    payload_by_key: dict[str, object],
    is_enabled: bool,
    is_repository_eligible: bool,
    timeout_milliseconds: int,
) -> dict[str, str]:
    """Return additionalContext when opt-in and repo gate both pass, else empty.

    Args:
        payload_by_key: Parsed SessionStart payload.
        is_enabled: When False, return empty without calling the injector.
        is_repository_eligible: When False, return empty without calling the injector.
        timeout_milliseconds: Injector timeout budget.

    Returns:
        ``{"additionalContext": ...}`` when injected, else ``{}``.
    """
    if not is_enabled or not is_repository_eligible:
        return {}
    configuration = build_issue_tracker_injector_configuration(timeout_milliseconds)
    injection_result = inject_session_start_context(payload_by_key, configuration)
    return build_additional_context_payload(injection_result)


def main() -> None:
    """Emit issue-tracker additionalContext when opt-in and registry gate pass."""
    payload_by_key = read_hook_input_dictionary_from_stdin()
    if payload_by_key is None:
        return
    is_enabled = issue_tracker_session_starter_enabled_in_environment()
    is_repository_eligible = (
        repository_is_registered(os.getcwd(), load_registry()) if is_enabled else False
    )
    payload = run_issue_tracker_session_starter(
        payload_by_key,
        is_enabled,
        is_repository_eligible,
        ISSUE_TRACKER_STARTER_TIMEOUT_MILLISECONDS,
    )
    if payload:
        print(json.dumps(payload))


if __name__ == "__main__":
    main()
