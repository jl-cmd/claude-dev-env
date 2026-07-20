"""Tests for orchestrator_auto_starter — SessionStart injector for /orchestrator.

Each test drives the real ``main()`` with a JSON payload on stdin, so the source
gate and the environment toggle run through the production code path.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from types import ModuleType

import orchestrator_auto_starter as starter
import pytest
from hooks_constants.orchestrator_auto_starter_constants import (
    AUTO_ORCHESTRATOR_ENV_VAR_NAME,
    ORCHESTRATOR_START_DIRECTIVE,
)
from hooks_constants.session_start_injector_constants import (
    ADDITIONAL_CONTEXT_KEY,
    HOOK_EVENT_NAME_KEY,
    HOOK_SPECIFIC_OUTPUT_KEY,
    SESSION_START_EVENT_NAME,
)

_STARTUP_SOURCE = "startup"


def test_enabled_start_emits_the_nested_payload(
    monkeypatch: pytest.MonkeyPatch,
    run_hook_main_with_payload: Callable[[ModuleType, dict[str, object]], str],
) -> None:
    monkeypatch.delenv(AUTO_ORCHESTRATOR_ENV_VAR_NAME, raising=False)

    emitted = json.loads(run_hook_main_with_payload(starter, {"source": _STARTUP_SOURCE}))

    nested_output = emitted[HOOK_SPECIFIC_OUTPUT_KEY]
    assert nested_output[HOOK_EVENT_NAME_KEY] == SESSION_START_EVENT_NAME
    assert nested_output[ADDITIONAL_CONTEXT_KEY] == ORCHESTRATOR_START_DIRECTIVE
    assert ADDITIONAL_CONTEXT_KEY not in emitted


def test_toggle_off_stays_silent(
    monkeypatch: pytest.MonkeyPatch,
    run_hook_main_with_payload: Callable[[ModuleType, dict[str, object]], str],
) -> None:
    monkeypatch.setenv(AUTO_ORCHESTRATOR_ENV_VAR_NAME, "off")

    output = run_hook_main_with_payload(starter, {"source": _STARTUP_SOURCE})

    assert output.strip() == ""


@pytest.mark.parametrize("ineligible_source", ["resume", "compact"])
def test_ineligible_source_stays_silent(
    monkeypatch: pytest.MonkeyPatch,
    run_hook_main_with_payload: Callable[[ModuleType, dict[str, object]], str],
    ineligible_source: str,
) -> None:
    monkeypatch.delenv(AUTO_ORCHESTRATOR_ENV_VAR_NAME, raising=False)

    output = run_hook_main_with_payload(starter, {"source": ineligible_source})

    assert output.strip() == ""


def test_build_orchestrator_directive_returns_the_shared_constant() -> None:
    assert starter.build_orchestrator_directive() == ORCHESTRATOR_START_DIRECTIVE
