"""Tests for orchestrator_auto_starter — SessionStart injector for /orchestrator.

Each test drives the real ``main()`` with a JSON payload on stdin, so the source
gate and the environment toggle run through the production code path.
"""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

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


def _run_main_with_payload(payload: dict[str, str]) -> str:
    """Return stdout from running the hook's main() with payload on stdin."""
    captured_stdout = StringIO()
    with (
        patch("sys.stdin", StringIO(json.dumps(payload))),
        patch("sys.stdout", captured_stdout),
        pytest.raises(SystemExit),
    ):
        starter.main()
    return captured_stdout.getvalue()


def test_enabled_start_emits_the_nested_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(AUTO_ORCHESTRATOR_ENV_VAR_NAME, raising=False)

    emitted = json.loads(_run_main_with_payload({"source": _STARTUP_SOURCE}))

    nested_output = emitted[HOOK_SPECIFIC_OUTPUT_KEY]
    assert nested_output[HOOK_EVENT_NAME_KEY] == SESSION_START_EVENT_NAME
    assert nested_output[ADDITIONAL_CONTEXT_KEY] == ORCHESTRATOR_START_DIRECTIVE
    assert ADDITIONAL_CONTEXT_KEY not in emitted


def test_toggle_off_stays_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(AUTO_ORCHESTRATOR_ENV_VAR_NAME, "off")

    output = _run_main_with_payload({"source": _STARTUP_SOURCE})

    assert output.strip() == ""


@pytest.mark.parametrize("ineligible_source", ["resume", "compact"])
def test_ineligible_source_stays_silent(
    monkeypatch: pytest.MonkeyPatch, ineligible_source: str
) -> None:
    monkeypatch.delenv(AUTO_ORCHESTRATOR_ENV_VAR_NAME, raising=False)

    output = _run_main_with_payload({"source": ineligible_source})

    assert output.strip() == ""


def test_build_orchestrator_directive_returns_the_shared_constant() -> None:
    assert starter.build_orchestrator_directive() == ORCHESTRATOR_START_DIRECTIVE
