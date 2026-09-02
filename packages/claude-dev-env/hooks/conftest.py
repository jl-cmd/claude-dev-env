"""Shared pytest fixtures for the hooks/ suite, visible under blocking/ and validators/."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_HOOKS_DIRECTORY = Path(__file__).resolve().parent
_BLOCKING_DIRECTORY = _HOOKS_DIRECTORY / "blocking"
for each_directory in (_HOOKS_DIRECTORY, _BLOCKING_DIRECTORY):
    if str(each_directory) not in sys.path:
        sys.path.insert(0, str(each_directory))

_code_rules_shared = importlib.import_module("code_rules_shared")
_code_rules_enforcer_constants = importlib.import_module(
    "hooks_constants.code_rules_enforcer_constants"
)
_is_ephemeral_script_path = _code_rules_shared.is_ephemeral_script_path
_EPHEMERAL_EXEMPT_DISABLE_ENVIRONMENT_VARIABLE_NAME = (
    _code_rules_enforcer_constants.EPHEMERAL_EXEMPT_DISABLE_ENVIRONMENT_VARIABLE_NAME
)


@pytest.fixture
def ephemeral_exempt_off(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Turn off the ephemeral scratch-path exemption for the current test.

    Sets ``CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT`` so a gate under test
    evaluates the test's own ``tmp_path`` targets for real, even though they
    sit under the shared OS temp root.

    Args:
        monkeypatch: Pytest's environment-variable patcher, torn down after the test.
        tmp_path: The test's own scratch directory, proving the flag took effect.
    """
    monkeypatch.setenv(_EPHEMERAL_EXEMPT_DISABLE_ENVIRONMENT_VARIABLE_NAME, "1")
    assert _is_ephemeral_script_path(str(tmp_path)) is False, (
        "ephemeral_exempt_off must turn off the scratch-path exemption for tmp_path; "
        "a change that stops reading the disable flag must fail here, not silently "
        "return every test in the file to deciding nothing"
    )
