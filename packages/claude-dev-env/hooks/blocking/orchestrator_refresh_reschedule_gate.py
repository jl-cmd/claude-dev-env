#!/usr/bin/env python3
"""PreToolUse gate: deny orchestrator-refresh re-arm when the run is not active.

Fires on ``ScheduleWakeup`` and ``CronCreate`` when the prompt targets
``/orchestrator-refresh``. Uses the same status-file gate as
``skills/orchestrator/scripts/status_gate.py`` so idle loops
cannot be re-armed on the Claude host without an active status file.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Mapping

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.orchestrator_refresh_reschedule_gate_constants import (  # noqa: E402
    ALL_HOME_SKILLS_RELATIVE_PARTS,
    ALL_SCHEDULE_TOOL_NAMES,
    ALL_SKILL_SCRIPTS_RELATIVE_PARTS,
    CALLING_HOOK_NAME,
    CRON_CREATE_TOOL_NAME,
    CWD_FIELD_NAME,
    DENY_REASON_TEMPLATE,
    HOOK_EVENT_NAME,
    ORCHESTRATOR_REFRESH_PROMPT_TOKEN,
    PLUGIN_ROOT_ENV_VAR,
    PROMPT_FIELD_NAME,
    REASON_CRON_CREATE_FORBIDDEN,
    RUN_SLUG_PROMPT_FLAG,
    RUN_SLUG_PROMPT_VALUE_PATTERN,
    TOOL_INPUT_FIELD_NAME,
    TOOL_NAME_FIELD_NAME,
)


def _candidate_skill_script_directories() -> list[Path]:
    """Return ordered paths that may contain status_gate.py.

    Returns:
        Absolute candidate directories in preference order.
    """
    all_candidates: list[Path] = []
    plugin_root = os.environ.get(PLUGIN_ROOT_ENV_VAR)
    if plugin_root:
        all_candidates.append(
            Path(plugin_root).joinpath(*ALL_SKILL_SCRIPTS_RELATIVE_PARTS)
        )
    package_hooks_parent = Path(__file__).resolve().parents[2]
    all_candidates.append(
        package_hooks_parent.joinpath(*ALL_SKILL_SCRIPTS_RELATIVE_PARTS)
    )
    all_candidates.append(Path.home().joinpath(*ALL_HOME_SKILLS_RELATIVE_PARTS))
    return all_candidates


def _load_status_gate_module() -> ModuleType | None:
    """Import status_gate from the skill scripts package.

    Returns:
        The loaded module, or None when no candidate path is usable.
    """
    for each_directory in _candidate_skill_script_directories():
        module_path = each_directory / "status_gate.py"
        if not module_path.is_file():
            continue
        scripts_directory = str(each_directory)
        if scripts_directory not in sys.path:
            sys.path.insert(0, scripts_directory)
        spec = importlib.util.spec_from_file_location(
            "orchestrator_status_gate_for_reschedule_hook",
            module_path,
        )
        if spec is None or spec.loader is None:
            continue
        status_gate_module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = status_gate_module
        spec.loader.exec_module(status_gate_module)
        return status_gate_module
    return None


def _prompt_targets_orchestrator_refresh(
    all_tool_input: Mapping[str, object],
) -> bool:
    """Return True when the schedule prompt re-enters orchestrator-refresh.

    Args:
        all_tool_input: PreToolUse tool_input mapping.

    Returns:
        True when the prompt field contains the refresh skill token.
    """
    prompt_value = all_tool_input.get(PROMPT_FIELD_NAME, "")
    if not isinstance(prompt_value, str):
        return False
    stripped_prompt = prompt_value.lstrip()
    if not stripped_prompt.startswith(ORCHESTRATOR_REFRESH_PROMPT_TOKEN):
        return False
    if len(stripped_prompt) == len(ORCHESTRATOR_REFRESH_PROMPT_TOKEN):
        return True
    return stripped_prompt[len(ORCHESTRATOR_REFRESH_PROMPT_TOKEN)] in (" ", "\n", "\t")


def _should_evaluate(all_payload_by_field: Mapping[str, object]) -> bool:
    """Return True for schedule tools re-arming orchestrator-refresh.

    Args:
        all_payload_by_field: Full PreToolUse payload.

    Returns:
        True when this gate must run.
    """
    tool_name = all_payload_by_field.get(TOOL_NAME_FIELD_NAME, "")
    if tool_name not in ALL_SCHEDULE_TOOL_NAMES:
        return False
    tool_input = all_payload_by_field.get(TOOL_INPUT_FIELD_NAME, {})
    if not isinstance(tool_input, dict):
        return False
    return _prompt_targets_orchestrator_refresh(tool_input)


def _run_slug_from_prompt(prompt_value: str) -> str:
    """Extract ``--run-slug`` from a ScheduleWakeup prompt when present.

    Args:
        prompt_value: The schedule tool prompt text.

    Returns:
        The slug string, or empty when the flag is absent.
    """
    run_slug_from_prompt_pattern = re.compile(
        re.escape(RUN_SLUG_PROMPT_FLAG) + RUN_SLUG_PROMPT_VALUE_PATTERN
    )
    matched = run_slug_from_prompt_pattern.search(prompt_value)
    if matched is None:
        return ""
    return matched.group(1)


def _resolve_status_file_path(
    status_gate_module: ModuleType,
    all_payload_by_field: Mapping[str, object],
) -> Path:
    """Resolve the run status file for this schedule attempt without chdir.

    Args:
        status_gate_module: Loaded status_gate module.
        all_payload_by_field: PreToolUse payload (may carry cwd and prompt).

    Returns:
        Absolute status file path.
    """
    base_directory: Path | None = None
    working_directory_value = all_payload_by_field.get(CWD_FIELD_NAME)
    if isinstance(working_directory_value, str) and working_directory_value:
        base_directory = Path(working_directory_value)
    run_slug = ""
    tool_input = all_payload_by_field.get(TOOL_INPUT_FIELD_NAME, {})
    if isinstance(tool_input, dict):
        prompt_value = tool_input.get(PROMPT_FIELD_NAME, "")
        if isinstance(prompt_value, str):
            run_slug = _run_slug_from_prompt(prompt_value)
    return status_gate_module.resolve_status_file_path(
        None, base_directory, run_slug
    )


def build_denial_response(reason_code: str) -> dict[str, dict[str, str]]:
    """Build the PreToolUse deny payload.

    Args:
        reason_code: Machine reason from decide_should_reschedule.

    Returns:
        Hook-specific deny JSON structure.
    """
    denial_reason = DENY_REASON_TEMPLATE.format(reason=reason_code)
    return {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "permissionDecision": "deny",
            "permissionDecisionReason": denial_reason,
        }
    }


def _emit_denial(
    reason_code: str,
    all_payload_by_field: Mapping[str, object],
) -> None:
    """Log and print a deny decision for the current schedule attempt.

    Args:
        reason_code: Machine reason string.
        all_payload_by_field: PreToolUse payload for logging context.
    """
    denial = build_denial_response(reason_code)
    hook_specific_output = denial["hookSpecificOutput"]
    block_reason = hook_specific_output["permissionDecisionReason"]
    log_hook_block(
        calling_hook_name=CALLING_HOOK_NAME,
        hook_event=HOOK_EVENT_NAME,
        block_reason=block_reason,
        tool_name=str(all_payload_by_field.get(TOOL_NAME_FIELD_NAME, "")),
        offending_input_preview=str(
            all_payload_by_field.get(TOOL_INPUT_FIELD_NAME, {})
        ),
    )
    print(json.dumps(denial))


def main() -> None:
    """Read PreToolUse stdin and deny idle orchestrator-refresh re-arms."""
    try:
        payload_by_field = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if not isinstance(payload_by_field, dict):
        sys.exit(0)
    if not _should_evaluate(payload_by_field):
        sys.exit(0)

    tool_name = payload_by_field.get(TOOL_NAME_FIELD_NAME, "")
    if tool_name == CRON_CREATE_TOOL_NAME:
        _emit_denial(REASON_CRON_CREATE_FORBIDDEN, payload_by_field)
        sys.exit(0)

    status_gate_module = _load_status_gate_module()
    if status_gate_module is None:
        _emit_denial("status_gate_unavailable", payload_by_field)
        sys.exit(0)

    status_file_path = _resolve_status_file_path(status_gate_module, payload_by_field)
    is_reschedule_allowed, reason_code = status_gate_module.decide_should_reschedule(
        status_file_path
    )
    if is_reschedule_allowed:
        sys.exit(0)

    _emit_denial(reason_code, payload_by_field)
    sys.exit(0)


if __name__ == "__main__":
    main()
