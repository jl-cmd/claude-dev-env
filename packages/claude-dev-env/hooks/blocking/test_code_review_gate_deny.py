"""Behavioral tests for the shared code-review gate deny scaffold.

The tests drive the two shared helpers directly: the payload builder's shape and
the log-and-emit helper's stdout, so both code-review gates inherit one verified
deny path.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

_HOOK_DIR = Path(__file__).resolve().parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))


def _load_module(module_name: str) -> ModuleType:
    module_spec = importlib.util.spec_from_file_location(
        module_name, _HOOK_DIR / f"{module_name}.py"
    )
    assert module_spec is not None
    assert module_spec.loader is not None
    loaded_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


deny_module = _load_module("code_review_gate_deny")


def test_build_payload_carries_reason_and_deny_decision() -> None:
    deny_payload = deny_module.build_code_review_deny_payload("blocked reason")
    hook_output = deny_payload["hookSpecificOutput"]
    assert hook_output["permissionDecision"] == "deny"
    assert hook_output["permissionDecisionReason"] == "blocked reason"


def test_log_and_emit_code_review_deny_writes_payload_to_stdout(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    deny_module.log_and_emit_code_review_deny("blocked reason", "Bash", "code_review_push_gate")
    emitted_payload = json.loads(capsys.readouterr().out)
    hook_output = emitted_payload["hookSpecificOutput"]
    assert hook_output["permissionDecision"] == "deny"
    assert hook_output["permissionDecisionReason"] == "blocked reason"
