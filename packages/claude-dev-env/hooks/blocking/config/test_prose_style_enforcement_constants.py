"""Tests for the prose-style enforcement opt-in flag (default off)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_CONSTANTS_PATH = Path(__file__).resolve().parent / "prose_style_enforcement_constants.py"


def _load_constants_module(monkeypatch: pytest.MonkeyPatch, env_value: str | None):
    module_name = "prose_style_enforcement_constants_under_test"
    if env_value is None:
        monkeypatch.delenv("CLAUDE_PROSE_STYLE_ENFORCEMENT", raising=False)
    else:
        monkeypatch.setenv("CLAUDE_PROSE_STYLE_ENFORCEMENT", env_value)
    module_spec = importlib.util.spec_from_file_location(module_name, _CONSTANTS_PATH)
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def test_absent_env_is_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_constants_module(monkeypatch, None)
    assert module.PROSE_STYLE_ENFORCEMENT_ENABLED is False
    assert module.prose_style_enforcement_enabled_in_environment() is False


@pytest.mark.parametrize("enabled_value", ["1", "true", "yes", "on", " True "])
def test_truthy_env_enables(
    monkeypatch: pytest.MonkeyPatch, enabled_value: str
) -> None:
    module = _load_constants_module(monkeypatch, enabled_value)
    assert module.PROSE_STYLE_ENFORCEMENT_ENABLED is True


@pytest.mark.parametrize("disabled_value", ["0", "false", "no", "off", ""])
def test_falsy_env_stays_off(
    monkeypatch: pytest.MonkeyPatch, disabled_value: str
) -> None:
    module = _load_constants_module(monkeypatch, disabled_value)
    assert module.PROSE_STYLE_ENFORCEMENT_ENABLED is False
