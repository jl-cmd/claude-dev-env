"""Tests for the opt-in orchestrator SessionStart auto-starter."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants.orchestrator_auto_starter_constants import (
    ORCHESTRATOR_AUTO_STARTER_ENABLED_ENV_VAR,
    ORCHESTRATOR_SESSION_START_DIRECTIVE,
    ORCHESTRATOR_STARTER_TIMEOUT_MILLISECONDS,
)
from session.orchestrator_auto_starter import (
    orchestrator_auto_starter_enabled_in_environment,
    run_orchestrator_auto_starter,
)

STARTER_SCRIPT = Path(__file__).resolve().parent / "orchestrator_auto_starter.py"
DEFAULT_TIMEOUT = ORCHESTRATOR_STARTER_TIMEOUT_MILLISECONDS


def test_default_environment_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ORCHESTRATOR_AUTO_STARTER_ENABLED_ENV_VAR, raising=False)
    assert orchestrator_auto_starter_enabled_in_environment() is False


def test_enabled_env_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ORCHESTRATOR_AUTO_STARTER_ENABLED_ENV_VAR, "1")
    assert orchestrator_auto_starter_enabled_in_environment() is True
    monkeypatch.setenv(ORCHESTRATOR_AUTO_STARTER_ENABLED_ENV_VAR, "true")
    assert orchestrator_auto_starter_enabled_in_environment() is True


def test_disabled_path_emits_empty_without_context() -> None:
    payload = run_orchestrator_auto_starter(
        {"source": "startup"}, False, DEFAULT_TIMEOUT
    )
    assert payload == {}


def test_enabled_startup_emits_orchestrator_directive() -> None:
    payload = run_orchestrator_auto_starter(
        {"source": "startup"}, True, DEFAULT_TIMEOUT
    )
    assert payload["additionalContext"] == ORCHESTRATOR_SESSION_START_DIRECTIVE


@pytest.mark.parametrize("source", ("startup", "resume", "clear", "compact"))
def test_enabled_known_sources_emit_directive(source: str) -> None:
    payload = run_orchestrator_auto_starter({"source": source}, True, DEFAULT_TIMEOUT)
    assert ORCHESTRATOR_SESSION_START_DIRECTIVE in payload.get("additionalContext", "")


def test_enabled_unknown_source_emits_nothing() -> None:
    payload = run_orchestrator_auto_starter({"source": "not-real"}, True, DEFAULT_TIMEOUT)
    assert payload == {}


def test_timeout_budget_zero_emits_nothing() -> None:
    payload = run_orchestrator_auto_starter({"source": "startup"}, True, 0)
    assert payload == {}


def test_main_stdin_enabled_prints_json() -> None:
    completed = subprocess.run(
        [sys.executable, str(STARTER_SCRIPT)],
        input=json.dumps({"source": "startup"}),
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, ORCHESTRATOR_AUTO_STARTER_ENABLED_ENV_VAR: "1"},
    )
    assert completed.returncode == 0
    parsed = json.loads(completed.stdout)
    assert parsed["additionalContext"] == ORCHESTRATOR_SESSION_START_DIRECTIVE


def test_main_stdin_disabled_prints_nothing() -> None:
    environment_by_key = os.environ.copy()
    environment_by_key.pop(ORCHESTRATOR_AUTO_STARTER_ENABLED_ENV_VAR, None)
    completed = subprocess.run(
        [sys.executable, str(STARTER_SCRIPT)],
        input=json.dumps({"source": "startup"}),
        capture_output=True,
        text=True,
        check=False,
        env=environment_by_key,
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == ""
