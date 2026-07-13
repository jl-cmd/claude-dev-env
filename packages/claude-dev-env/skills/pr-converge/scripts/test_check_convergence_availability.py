"""Tests for the reviewer-availability + settings resolution of the convergence gate.

::

    probe down        ok:   waived, "copilot unavailable: <reason>"
    probe up           flag: enforced, no note
    probe raises        flag: enforced fail-safe, "probe error: <exc>" (distinct state)
    disk lists copilot  ok:   waived even when env omits it (mid-session settings change)
    disk != env          ->  discrepancy logged to stderr

The three probe states stay distinguishable so a broken probe never reads as a
healthy enforcement. The disk/env union closes the frozen-env staleness that
stalled the mark-ready re-check when settings.json changed mid-session.
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

_SCRIPTS_DIRECTORY = Path(__file__).absolute().parent

COPILOT_REVIEWER = "copilot"
BUGBOT_REVIEWER = "bugbot"


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


class _StubAvailability:
    """Stand-in for ReviewerAvailability the probe reads exit_code and message off."""

    def __init__(self, exit_code: int, message: str) -> None:
        self.exit_code = exit_code
        self.message = message


def _stub_probe(exit_code: int, message: str) -> Callable[..., _StubAvailability]:
    def _probe(**_call_keywords: object) -> _StubAvailability:
        return _StubAvailability(exit_code, message)

    return _probe


def _write_settings(tmp_path: Path, reviews_disabled_value: str) -> Path:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"env": {"CLAUDE_REVIEWS_DISABLED": reviews_disabled_value}}),
        encoding="utf-8",
    )
    return settings_path


@pytest.fixture(autouse=True)
def _reset_probe_cache_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    availability._probe_reviewer_down.cache_clear()
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    monkeypatch.delenv("CLAUDE_REVIEWS_ENABLED", raising=False)
    monkeypatch.setattr(
        availability, "_settings_json_path", lambda: Path("does-not-exist")
    )


def should_probe_report_down_with_reviewer_named_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        availability,
        "evaluate_reviewer_availability",
        _stub_probe(availability.EXIT_CODE_REVIEWER_DOWN, "out of premium quota"),
    )
    waiver = availability._probe_reviewer_down(COPILOT_REVIEWER)
    assert waiver.is_waived is True
    assert waiver.bypass_note == "copilot unavailable: out of premium quota"


def should_probe_report_up_and_enforce_with_no_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        availability,
        "evaluate_reviewer_availability",
        _stub_probe(0, "quota available"),
    )
    waiver = availability._probe_reviewer_down(COPILOT_REVIEWER)
    assert waiver.is_waived is False
    assert waiver.bypass_note == ""


def should_probe_fail_safe_enforced_with_distinct_probe_error_note(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def _raising_probe(**_call_keywords: object) -> object:
        raise RuntimeError("quota API unreachable")

    monkeypatch.setattr(availability, "evaluate_reviewer_availability", _raising_probe)
    with caplog.at_level(logging.WARNING):
        waiver = availability._probe_reviewer_down(COPILOT_REVIEWER)
    assert waiver.is_waived is False
    assert waiver.bypass_note.startswith("probe error:")
    assert "quota API unreachable" in waiver.bypass_note
    assert "probe error" in caplog.text


def should_probe_each_reviewer_at_most_once_per_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe_call_count = 0

    def _counting_probe(**_call_keywords: object) -> _StubAvailability:
        nonlocal probe_call_count
        probe_call_count += 1
        return _StubAvailability(availability.EXIT_CODE_REVIEWER_DOWN, "down once")

    monkeypatch.setattr(availability, "evaluate_reviewer_availability", _counting_probe)
    availability._probe_reviewer_down(COPILOT_REVIEWER)
    availability._probe_reviewer_down(COPILOT_REVIEWER)
    assert probe_call_count == 1


def should_resolve_copilot_waiver_from_flag_with_pinned_note() -> None:
    waiver = availability._resolve_copilot_waiver(True)
    assert waiver.is_waived is True
    assert waiver.bypass_note == "copilot_down"


def should_resolve_copilot_waiver_from_frozen_env_with_pinned_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "copilot")
    waiver = availability._resolve_copilot_waiver(False)
    assert waiver.is_waived is True
    assert waiver.bypass_note == "copilot_down"


def should_waive_copilot_from_disk_settings_when_frozen_env_omits_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "bugbot")
    settings_path = _write_settings(tmp_path, "bugbot,copilot")
    monkeypatch.setattr(availability, "_settings_json_path", lambda: settings_path)
    with caplog.at_level(logging.WARNING):
        waiver = availability._resolve_copilot_waiver(False)
    assert waiver.is_waived is True
    assert waiver.bypass_note == "copilot_down"
    assert "CLAUDE_REVIEWS_DISABLED" in caplog.text


def should_probe_copilot_when_neither_flag_env_nor_disk_disable_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        availability,
        "evaluate_reviewer_availability",
        _stub_probe(availability.EXIT_CODE_REVIEWER_DOWN, "quota exhausted"),
    )
    waiver = availability._resolve_copilot_waiver(False)
    assert waiver.is_waived is True
    assert waiver.bypass_note == "copilot unavailable: quota exhausted"


def should_resolve_bugbot_waiver_from_probe_with_bugbot_named_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_ENABLED", "bugbot")
    monkeypatch.setattr(
        availability,
        "evaluate_reviewer_availability",
        _stub_probe(availability.EXIT_CODE_REVIEWER_DOWN, "bugbot offline"),
    )
    waiver = availability._resolve_bugbot_waiver(False)
    assert waiver.is_waived is True
    assert waiver.bypass_note == "bugbot unavailable: bugbot offline"

