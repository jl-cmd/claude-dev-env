"""Tests for the reviewer-availability + settings resolution of the convergence gate.

::

    probe out-of-quota   ok:   waived, "copilot unavailable: <reason>"
    probe available       flag: enforced, no note
    probe API down        flag: enforced, probe_error_reason set (not waived)
    probe exception       flag: enforced, probe_error_reason set
    disk lists copilot    ok:   waived even when env omits it (disk authoritative)
    disk omits copilot    flag: enforced even when env lists it (disk authoritative)
    disk unreadable       ok:   env fallback, logged once per process
"""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
from pathlib import Path
from types import ModuleType
from typing import Callable

import pytest

import _pr_converge_path_setup  # noqa: F401
from pr_loop_shared_constants.copilot_quota_constants import (
    EXIT_CODE_NO_ACCOUNT_CONFIGURED,
    EXIT_CODE_OUT_OF_QUOTA,
    EXIT_CODE_QUOTA_API_DOWN,
    EXIT_CODE_QUOTA_AVAILABLE,
)

_SCRIPTS_DIRECTORY = Path(__file__).absolute().parent


def _load_availability() -> ModuleType:
    if str(_SCRIPTS_DIRECTORY) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIRECTORY))
    module_path = _SCRIPTS_DIRECTORY / "check_convergence_availability.py"
    spec = importlib.util.spec_from_file_location(
        "check_convergence_availability_under_test", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


availability = _load_availability()


class _StubQuotaDecision:
    """Stand-in for QuotaDecision the copilot probe reads exit_code and message off."""

    def __init__(self, exit_code: int, message: str) -> None:
        self.exit_code = exit_code
        self.message = message


def _stub_quota(exit_code: int, message: str) -> Callable[..., _StubQuotaDecision]:
    def _probe(**_call_keywords: object) -> _StubQuotaDecision:
        return _StubQuotaDecision(exit_code, message)

    return _probe


def _write_settings(
    tmp_path: Path,
    *,
    reviews_disabled_value: str | None = None,
    reviews_enabled_value: str | None = None,
) -> Path:
    env_block: dict[str, str] = {}
    if reviews_disabled_value is not None:
        env_block["CLAUDE_REVIEWS_DISABLED"] = reviews_disabled_value
    if reviews_enabled_value is not None:
        env_block["CLAUDE_REVIEWS_ENABLED"] = reviews_enabled_value
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"env": env_block}), encoding="utf-8")
    return settings_path


@pytest.fixture(autouse=True)
def _reset_probe_cache_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    availability._probe_copilot_quota.cache_clear()
    availability._log_disk_settings_fallback_once.cache_clear()
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    monkeypatch.delenv("CLAUDE_REVIEWS_ENABLED", raising=False)
    monkeypatch.setattr(
        availability,
        "get_claude_user_settings_path",
        lambda: Path("does-not-exist"),
    )


def should_copilot_probe_waive_on_out_of_quota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        availability,
        "evaluate_copilot_quota",
        _stub_quota(EXIT_CODE_OUT_OF_QUOTA, "out of premium quota"),
    )
    waiver = availability._probe_copilot_quota()
    assert waiver.is_waived is True
    assert waiver.bypass_note == "copilot unavailable: out of premium quota"
    assert waiver.probe_error_reason == ""


def should_copilot_probe_enforce_when_quota_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        availability,
        "evaluate_copilot_quota",
        _stub_quota(EXIT_CODE_QUOTA_AVAILABLE, "quota available"),
    )
    waiver = availability._probe_copilot_quota()
    assert waiver.is_waived is False
    assert waiver.bypass_note == ""
    assert waiver.probe_error_reason == ""


def should_copilot_probe_set_probe_error_on_quota_api_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        availability,
        "evaluate_copilot_quota",
        _stub_quota(EXIT_CODE_QUOTA_API_DOWN, "quota API unreachable"),
    )
    waiver = availability._probe_copilot_quota()
    assert waiver.is_waived is False
    assert waiver.bypass_note == ""
    assert waiver.probe_error_reason == "quota API unreachable"


def should_copilot_probe_set_probe_error_on_no_account_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        availability,
        "evaluate_copilot_quota",
        _stub_quota(
            EXIT_CODE_NO_ACCOUNT_CONFIGURED,
            "no account configured",
        ),
    )
    waiver = availability._probe_copilot_quota()
    assert waiver.is_waived is False
    assert waiver.bypass_note == ""
    assert waiver.probe_error_reason == "no account configured"


def should_copilot_probe_set_probe_error_on_exception(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def _raising_probe(**_call_keywords: object) -> object:
        raise RuntimeError("quota API unreachable")

    monkeypatch.setattr(availability, "evaluate_copilot_quota", _raising_probe)
    with caplog.at_level(logging.WARNING):
        waiver = availability._probe_copilot_quota()
    assert waiver.is_waived is False
    assert waiver.probe_error_reason == "quota API unreachable"
    assert "probe error" in caplog.text


def should_probe_copilot_at_most_once_per_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe_call_count = 0

    def _counting_probe(**_call_keywords: object) -> _StubQuotaDecision:
        nonlocal probe_call_count
        probe_call_count += 1
        return _StubQuotaDecision(EXIT_CODE_OUT_OF_QUOTA, "down once")

    monkeypatch.setattr(availability, "evaluate_copilot_quota", _counting_probe)
    availability._probe_copilot_quota()
    availability._probe_copilot_quota()
    assert probe_call_count == 1


def should_resolve_copilot_waiver_from_flag_with_pinned_note() -> None:
    waiver = availability._resolve_copilot_waiver(True)
    assert waiver.is_waived is True
    assert waiver.bypass_note == "copilot_down"
    assert waiver.probe_error_reason == ""


def should_resolve_copilot_waiver_from_frozen_env_with_pinned_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "copilot")
    waiver = availability._resolve_copilot_waiver(False)
    assert waiver.is_waived is True
    assert waiver.bypass_note == "copilot_down"


def should_waive_copilot_from_disk_when_env_omits_it_without_union_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "bugbot")
    settings_path = _write_settings(tmp_path, reviews_disabled_value="bugbot,copilot")
    monkeypatch.setattr(
        availability, "get_claude_user_settings_path", lambda: settings_path
    )
    with caplog.at_level(logging.WARNING):
        waiver = availability._resolve_copilot_waiver(False)
    assert waiver.is_waived is True
    assert waiver.bypass_note == "copilot_down"
    assert "taking the union" not in caplog.text
    assert "differs" not in caplog.text


def should_enforce_copilot_from_disk_when_env_still_lists_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "copilot")
    settings_path = _write_settings(tmp_path, reviews_disabled_value="bugbot")
    monkeypatch.setattr(
        availability, "get_claude_user_settings_path", lambda: settings_path
    )
    monkeypatch.setattr(
        availability,
        "evaluate_copilot_quota",
        _stub_quota(EXIT_CODE_QUOTA_AVAILABLE, "quota available"),
    )
    waiver = availability._resolve_copilot_waiver(False)
    assert waiver.is_waived is False
    assert waiver.probe_error_reason == ""


def should_not_fall_through_to_env_when_readable_disk_omits_disabled_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "copilot")
    settings_path = _write_settings(tmp_path)
    monkeypatch.setattr(
        availability, "get_claude_user_settings_path", lambda: settings_path
    )
    monkeypatch.setattr(
        availability,
        "evaluate_copilot_quota",
        _stub_quota(EXIT_CODE_QUOTA_AVAILABLE, "quota available"),
    )
    waiver = availability._resolve_copilot_waiver(False)
    assert waiver.is_waived is False


def should_use_env_fallback_and_log_once_when_disk_unreadable(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "copilot,bugbot")
    monkeypatch.setenv("CLAUDE_REVIEWS_ENABLED", "bugbot")
    with caplog.at_level(logging.WARNING):
        copilot_waiver = availability._resolve_copilot_waiver(False)
        bugbot_waiver = availability._resolve_bugbot_waiver(False)
    assert copilot_waiver.is_waived is True
    assert bugbot_waiver.is_waived is True
    fallback_log_count = caplog.text.count("settings.json unreadable")
    assert fallback_log_count == 1


def should_resolve_bugbot_disabled_when_enabled_list_omits_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings_path = _write_settings(
        tmp_path, reviews_disabled_value="", reviews_enabled_value=""
    )
    monkeypatch.setattr(
        availability, "get_claude_user_settings_path", lambda: settings_path
    )
    waiver = availability._resolve_bugbot_waiver(False)
    assert waiver.is_waived is True
    assert waiver.bypass_note == "bugbot_down"


def should_enforce_bugbot_when_disk_enables_it_even_if_env_omits_opt_in(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("CLAUDE_REVIEWS_ENABLED", raising=False)
    settings_path = _write_settings(
        tmp_path, reviews_disabled_value="", reviews_enabled_value="bugbot"
    )
    monkeypatch.setattr(
        availability, "get_claude_user_settings_path", lambda: settings_path
    )
    waiver = availability._resolve_bugbot_waiver(False)
    assert waiver.is_waived is False
    assert waiver.probe_error_reason == ""


def should_read_settings_via_get_claude_user_settings_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings_path = _write_settings(tmp_path, reviews_disabled_value="copilot")
    resolved_paths: list[Path] = []

    def _recording_settings_path() -> Path:
        resolved_paths.append(settings_path)
        return settings_path

    monkeypatch.setattr(
        availability, "get_claude_user_settings_path", _recording_settings_path
    )
    waiver = availability._resolve_copilot_waiver(False)
    assert resolved_paths == [settings_path]
    assert waiver.is_waived is True
    assert waiver.bypass_note == "copilot_down"


def should_probe_copilot_when_neither_flag_env_nor_disk_disable_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        availability,
        "evaluate_copilot_quota",
        _stub_quota(EXIT_CODE_OUT_OF_QUOTA, "quota exhausted"),
    )
    waiver = availability._resolve_copilot_waiver(False)
    assert waiver.is_waived is True
    assert waiver.bypass_note == "copilot unavailable: quota exhausted"
