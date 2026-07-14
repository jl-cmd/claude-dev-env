"""Behavioral tests for the decisions parts module."""

import json
from pathlib import Path

import pytest
from tdd_enforcer_parts import decisions


def test_build_deny_reason_names_candidates_and_production_path() -> None:
    reason = decisions.build_deny_reason(Path("pkg/orders.py"), [Path("pkg/test_orders.py")])
    assert "orders.py" in reason
    assert "test_orders.py" in reason
    assert "propose" in reason.lower() or "enhancement" in reason.lower()


def test_build_deny_reason_points_exemption_guidance_at_entry_hook() -> None:
    reason = decisions.build_deny_reason(Path("pkg/orders.py"), [])
    assert "tdd_enforcer.py" in reason
    assert "decisions.py" not in reason


def test_emit_allow_writes_allow_decision(capsys: pytest.CaptureFixture[str]) -> None:
    decisions.emit_allow()
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_emit_deny_writes_deny_and_system_message(capsys: pytest.CaptureFixture[str]) -> None:
    decisions.emit_deny("blocked because no fresh test")
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert parsed["suppressOutput"] is True
    assert isinstance(parsed["systemMessage"], str)
