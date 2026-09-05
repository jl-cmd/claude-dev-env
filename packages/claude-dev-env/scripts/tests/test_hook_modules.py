"""Behavior tests for repository-check hook module loading."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIRECTORY))

from repository_checks.hook_modules import load_hooks_module


def test_should_load_a_hooks_module_by_its_dotted_name() -> None:
    loaded_module = load_hooks_module("hooks_constants.pii_prevention_constants")
    assert loaded_module.__name__ == "hooks_constants.pii_prevention_constants"
