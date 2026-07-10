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


def test_is_bugbot_disabled_via_env_returns_true_when_env_lists_bugbot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "bugbot")
    assert reviews_disabled.is_bugbot_disabled_via_env() is True


def test_is_bugbot_disabled_via_env_returns_true_when_no_env_vars_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    monkeypatch.delenv("CLAUDE_REVIEWS_ENABLED", raising=False)
    assert reviews_disabled.is_bugbot_disabled_via_env() is True


def test_is_bugbot_disabled_via_env_returns_false_when_enabled_lists_bugbot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    monkeypatch.setenv("CLAUDE_REVIEWS_ENABLED", "bugbot")
    assert reviews_disabled.is_bugbot_disabled_via_env() is False


def test_is_bugbot_disabled_via_env_enabled_parse_is_case_and_space_tolerant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    monkeypatch.setenv("CLAUDE_REVIEWS_ENABLED", " BugBot ")
    assert reviews_disabled.is_bugbot_disabled_via_env() is False


def test_is_bugbot_disabled_via_env_true_when_disabled_overrides_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "bugbot")
    monkeypatch.setenv("CLAUDE_REVIEWS_ENABLED", "bugbot")
    assert reviews_disabled.is_bugbot_disabled_via_env() is True


def test_is_bugbot_disabled_via_env_true_when_bugteam_listed_and_not_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "bugteam")
    monkeypatch.delenv("CLAUDE_REVIEWS_ENABLED", raising=False)
    assert reviews_disabled.is_bugbot_disabled_via_env() is True


def test_is_bugbot_disabled_via_env_true_when_both_tokens_listed_mixed_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", " BugTeam , BUGBOT ")
    assert reviews_disabled.is_bugbot_disabled_via_env() is True
    assert reviews_disabled.is_bugteam_disabled_via_env() is True


def test_is_copilot_disabled_via_env_returns_true_when_env_lists_copilot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "copilot")
    assert reviews_disabled.is_copilot_disabled_via_env() is True


def test_is_copilot_disabled_via_env_returns_false_when_env_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    assert reviews_disabled.is_copilot_disabled_via_env() is False


def test_is_copilot_disabled_via_env_returns_false_when_only_bugbot_listed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "bugbot")
    assert reviews_disabled.is_copilot_disabled_via_env() is False


def test_is_copilot_disabled_via_env_true_when_listed_among_other_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", " BugBot , CoPilot ")
    assert reviews_disabled.is_copilot_disabled_via_env() is True
    assert reviews_disabled.is_bugbot_disabled_via_env() is True


def test_cli_main_returns_zero_when_named_reviewer_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "bugbot")
    assert reviews_disabled.main(["--reviewer", "bugbot"]) == 0


def test_cli_main_returns_one_when_bugbot_enabled_via_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    monkeypatch.setenv("CLAUDE_REVIEWS_ENABLED", "bugbot")
    assert reviews_disabled.main(["--reviewer", "bugbot"]) == 1


def test_cli_main_returns_one_for_bugbot_when_enabled_despite_bugteam_optout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "bugteam")
    monkeypatch.setenv("CLAUDE_REVIEWS_ENABLED", "bugbot")
    assert reviews_disabled.main(["--reviewer", "bugbot"]) == 1


def test_cli_main_supports_bugteam_reviewer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "bugteam")
    assert reviews_disabled.main(["--reviewer", "bugteam"]) == 0


def test_cli_main_supports_copilot_reviewer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "copilot")
    assert reviews_disabled.main(["--reviewer", "copilot"]) == 0


def test_cli_main_returns_one_for_copilot_when_only_bugbot_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "bugbot")
    assert reviews_disabled.main(["--reviewer", "copilot"]) == 1
