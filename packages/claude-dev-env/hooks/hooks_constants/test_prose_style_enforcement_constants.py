"""Behavioral tests for the shared prose-style enforcement switch.

These assert the switch ships off as a bool, and that every hook named on the
roster obeys it: one violating payload per hook blocks with the switch forced
on and passes with the same switch forced off.

::

    payload: a heavy word in a .md write
    ok:   switch forced off -> no block decision, no deny decision
    flag: switch forced on  -> the hook blocks the write

Each hook runs as a subprocess through a launcher that sets the switch on the
hook module before calling ``main()``, so the shipped constant never decides
the outcome.
"""

import json
import pathlib
import subprocess
import sys

import pytest

_CONSTANTS_DIRECTORY = pathlib.Path(__file__).parent
_BLOCKING_DIRECTORY = _CONSTANTS_DIRECTORY.parent / "blocking"
_HOOKS_ROOT = str(_CONSTANTS_DIRECTORY.parent)
if _HOOKS_ROOT not in sys.path:
    sys.path.insert(0, _HOOKS_ROOT)

from hooks_constants.prose_style_enforcement_constants import (  # noqa: E402
    ALL_PROSE_STYLE_HOOK_MODULE_NAMES,
    PROSE_STYLE_ENFORCEMENT_ENABLED,
)

BLOCK_DECISION = "block"
DENY_DECISION = "deny"

VIOLATING_PAYLOAD_BY_HOOK_MODULE_NAME = {
    "hedging_language_blocker": {
        "last_assistant_message": "This is likely correct.",
    },
    "question_to_user_enforcer": {
        "last_assistant_message": (
            "I applied the rename across both files. "
            "Should this also propagate to the docs?"
        ),
    },
    "intent_only_ending_blocker": {
        "last_assistant_message": (
            "I'll now run the test suite and fix any failures that come up."
        ),
    },
    "plain_language_blocker": {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "notes.md",
            "content": "This utilize pattern is heavy.",
        },
    },
    "state_description_blocker": {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "src/main.py",
            "content": "# Uses X instead of Y",
        },
    },
}


def build_switch_forced_program(hook_module_name: str, is_enforcement_enabled: bool) -> str:
    """Build a launcher that pins the prose-style switch, then runs one hook.

    Args:
        hook_module_name: Module name of the hook to import and run.
        is_enforcement_enabled: Value to pin the switch to inside the hook module.

    Returns:
        The program text to pass to the interpreter's ``-c`` flag.
    """
    return (
        "import sys;"
        f"sys.path.insert(0, {repr(str(_BLOCKING_DIRECTORY))});"
        f"import {hook_module_name} as hook_module;"
        f"hook_module.PROSE_STYLE_ENFORCEMENT_ENABLED = {is_enforcement_enabled};"
        "hook_module.main()"
    )


def run_hook_with_switch_forced(
    hook_module_name: str, is_enforcement_enabled: bool
) -> subprocess.CompletedProcess[str]:
    """Run one rostered hook on its violating payload with the switch pinned.

    Args:
        hook_module_name: Module name of the hook to run.
        is_enforcement_enabled: Value to pin the switch to for this run.

    Returns:
        The completed subprocess result with stdout captured.
    """
    violating_payload = VIOLATING_PAYLOAD_BY_HOOK_MODULE_NAME[hook_module_name]
    return subprocess.run(
        [sys.executable, "-c", build_switch_forced_program(hook_module_name, is_enforcement_enabled)],
        input=json.dumps(violating_payload),
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
    )


def is_blocking_output(completed_process: subprocess.CompletedProcess[str]) -> bool:
    """Report whether a hook run blocked, across both hook response shapes.

    Args:
        completed_process: The completed subprocess from running a hook.

    Returns:
        True when the stdout carries a Stop-hook block decision or a PreToolUse
        deny decision, and False for silent or unparsable output.
    """
    stdout_text = completed_process.stdout.strip()
    try:
        parsed_output = json.loads(stdout_text)
    except json.JSONDecodeError:
        return False
    if parsed_output.get("decision") == BLOCK_DECISION:
        return True
    hook_specific_output = parsed_output.get("hookSpecificOutput", {})
    if not isinstance(hook_specific_output, dict):
        return False
    return hook_specific_output.get("permissionDecision") == DENY_DECISION


def test_enforcement_defaults_to_off() -> None:
    assert PROSE_STYLE_ENFORCEMENT_ENABLED is False
    assert isinstance(PROSE_STYLE_ENFORCEMENT_ENABLED, bool)


def test_roster_matches_the_hooks_this_suite_exercises() -> None:
    assert set(ALL_PROSE_STYLE_HOOK_MODULE_NAMES) == set(
        VIOLATING_PAYLOAD_BY_HOOK_MODULE_NAME
    )


@pytest.mark.parametrize("hook_module_name", ALL_PROSE_STYLE_HOOK_MODULE_NAMES)
def test_rostered_hook_blocks_when_the_switch_is_forced_on(hook_module_name: str) -> None:
    completed_process = run_hook_with_switch_forced(hook_module_name, True)

    assert completed_process.returncode == 0
    assert is_blocking_output(completed_process) is True


@pytest.mark.parametrize("hook_module_name", ALL_PROSE_STYLE_HOOK_MODULE_NAMES)
def test_rostered_hook_stays_silent_when_the_switch_is_forced_off(
    hook_module_name: str,
) -> None:
    completed_process = run_hook_with_switch_forced(hook_module_name, False)

    assert completed_process.returncode == 0
    assert is_blocking_output(completed_process) is False
