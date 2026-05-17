"""Direct unit tests for the shared reviews_disabled helper."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _load_reviews_disabled_module() -> ModuleType:
    module_path = Path(__file__).parent.parent / "reviews_disabled.py"
    specification = importlib.util.spec_from_file_location(
        "reviews_disabled", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


reviews_disabled = _load_reviews_disabled_module()


def test_is_bugteam_disabled_via_env_returns_true_when_env_lists_bugteam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "bugteam")
    assert reviews_disabled.is_bugteam_disabled_via_env() is True


def test_is_bugteam_disabled_via_env_returns_false_when_env_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    assert reviews_disabled.is_bugteam_disabled_via_env() is False
