"""Tests for session_start_injector — the shared SessionStart injector logic."""

from __future__ import annotations

import pytest
from hooks_constants.session_start_injector import (
    build_session_start_payload,
    is_eligible_source,
    is_injection_enabled,
)
from hooks_constants.session_start_injector_constants import (
    ADDITIONAL_CONTEXT_KEY,
    HOOK_EVENT_NAME_KEY,
    HOOK_SPECIFIC_OUTPUT_KEY,
    SESSION_START_EVENT_NAME,
)

_TOGGLE_NAME = "CLAUDE_TEST_INJECTOR_TOGGLE"
_DIRECTIVE_SAMPLE = "start the tracker"


class TestInjectionEnabled:
    def test_unset_variable_is_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(_TOGGLE_NAME, raising=False)
        assert is_injection_enabled(_TOGGLE_NAME) is True

    @pytest.mark.parametrize("off_value", ["0", "false", "off", "no", "OFF", " No "])
    def test_off_values_disable(self, monkeypatch: pytest.MonkeyPatch, off_value: str) -> None:
        monkeypatch.setenv(_TOGGLE_NAME, off_value)
        assert is_injection_enabled(_TOGGLE_NAME) is False

    @pytest.mark.parametrize("on_value", ["1", "true", "yes", "on", "anything"])
    def test_non_off_values_enable(self, monkeypatch: pytest.MonkeyPatch, on_value: str) -> None:
        monkeypatch.setenv(_TOGGLE_NAME, on_value)
        assert is_injection_enabled(_TOGGLE_NAME) is True


class TestEligibleSource:
    @pytest.mark.parametrize("eligible_source", ["startup", "clear"])
    def test_startup_and_clear_are_eligible(self, eligible_source: str) -> None:
        assert is_eligible_source(eligible_source) is True

    @pytest.mark.parametrize("ineligible_source", ["resume", "compact", ""])
    def test_resume_and_compact_are_not_eligible(self, ineligible_source: str) -> None:
        assert is_eligible_source(ineligible_source) is False


class TestPayloadShape:
    def test_payload_uses_the_nested_shape(self) -> None:
        payload = build_session_start_payload(_DIRECTIVE_SAMPLE)
        nested_output = payload[HOOK_SPECIFIC_OUTPUT_KEY]
        assert nested_output[HOOK_EVENT_NAME_KEY] == SESSION_START_EVENT_NAME
        assert nested_output[ADDITIONAL_CONTEXT_KEY] == _DIRECTIVE_SAMPLE

    def test_payload_is_not_the_flat_shape(self) -> None:
        payload = build_session_start_payload(_DIRECTIVE_SAMPLE)
        assert ADDITIONAL_CONTEXT_KEY not in payload
