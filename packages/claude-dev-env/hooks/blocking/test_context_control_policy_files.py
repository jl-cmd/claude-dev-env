"""Validation fixtures for context-control policy artifacts."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HOOK_SPEC_PATH = ROOT / "hooks" / "HOOK_SPECS_PROMPT_WORKFLOW.md"


def test_hook_spec_exists_with_required_gates() -> None:
    text = HOOK_SPEC_PATH.read_text(encoding="utf-8")
    assert "PreToolUse Task/Agent (removed)" in text
    assert "agent-execution-intent-gate.py" in text
    assert "Leakage + Checklist + Scope (Stop)" in text
    assert "Required Deterministic Checklist Rows" in text
    assert "Runtime Context-Control Signals" in text
