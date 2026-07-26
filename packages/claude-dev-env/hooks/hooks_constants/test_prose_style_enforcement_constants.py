"""Behavioral tests for the shared prose-style enforcement switch.

These assert the switch ships off, and that every hook named on the roster
imports the switch by name, so a prose hook that enforces regardless of the
switch fails loudly here.
"""

import importlib.util
import pathlib

_CONSTANTS_DIRECTORY = pathlib.Path(__file__).parent
_BLOCKING_DIRECTORY = _CONSTANTS_DIRECTORY.parent / "blocking"
_PYTHON_SUFFIX = ".py"

_constants_spec = importlib.util.spec_from_file_location(
    "prose_style_enforcement_constants",
    _CONSTANTS_DIRECTORY / "prose_style_enforcement_constants.py",
)
assert _constants_spec is not None
assert _constants_spec.loader is not None
_constants_module = importlib.util.module_from_spec(_constants_spec)
_constants_spec.loader.exec_module(_constants_module)

PROSE_STYLE_ENFORCEMENT_ENABLED = _constants_module.PROSE_STYLE_ENFORCEMENT_ENABLED
ALL_PROSE_STYLE_HOOK_MODULE_NAMES = _constants_module.ALL_PROSE_STYLE_HOOK_MODULE_NAMES
PROSE_STYLE_ENFORCEMENT_FLAG_NAME = _constants_module.PROSE_STYLE_ENFORCEMENT_FLAG_NAME


def test_enforcement_defaults_to_off() -> None:
    assert PROSE_STYLE_ENFORCEMENT_ENABLED is False


def test_roster_names_the_five_prose_hooks() -> None:
    assert set(ALL_PROSE_STYLE_HOOK_MODULE_NAMES) == {
        "hedging_language_blocker",
        "question_to_user_enforcer",
        "intent_only_ending_blocker",
        "plain_language_blocker",
        "state_description_blocker",
    }


def test_every_rostered_hook_reads_the_switch() -> None:
    all_hooks_missing_the_switch = [
        each_module_name
        for each_module_name in ALL_PROSE_STYLE_HOOK_MODULE_NAMES
        if PROSE_STYLE_ENFORCEMENT_FLAG_NAME
        not in (_BLOCKING_DIRECTORY / (each_module_name + _PYTHON_SUFFIX)).read_text(
            encoding="utf-8"
        )
    ]
    assert all_hooks_missing_the_switch == []
