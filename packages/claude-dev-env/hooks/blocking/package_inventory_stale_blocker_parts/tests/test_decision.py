"""Tests for the package-inventory blocker decision parts module."""

import json

import pytest
from package_inventory_stale_blocker_parts import decision as decision_module
from package_inventory_stale_blocker_parts.config.inventory_blocker_constants import (
    FILE_FIRST_RETRY_HINT,
)
from package_inventory_stale_blocker_parts.decision import (
    build_block_payload,
    deny_stale_inventory,
)
from package_inventory_stale_blocker_parts.inventory_detection import _InventorySurvey


def test_deny_stale_inventory_emits_deny(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(decision_module, "log_hook_block", lambda **each_argument: None)
    survey = _InventorySurvey(["README.md"], {"alpha.py", "beta.py"})
    deny_stale_inventory("/pkg/gamma.py", survey)
    emitted_payload = json.loads(capsys.readouterr().out)
    assert emitted_payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_build_block_payload_names_the_file_and_denies() -> None:
    survey = _InventorySurvey(["README.md"], {"alpha.py", "beta.py"})
    block_payload = build_block_payload("/pkg/gamma.py", survey)
    hook_output = block_payload["hookSpecificOutput"]
    assert hook_output["permissionDecision"] == "deny"
    assert "gamma.py" in hook_output["permissionDecisionReason"]


def test_build_block_payload_appends_retry_hint() -> None:
    survey = _InventorySurvey(["README.md"], {"alpha.py", "beta.py"})
    block_payload = build_block_payload("/pkg/gamma.py", survey)
    assert FILE_FIRST_RETRY_HINT in block_payload["hookSpecificOutput"]["permissionDecisionReason"]
