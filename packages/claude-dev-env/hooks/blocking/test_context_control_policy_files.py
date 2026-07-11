"""Validation fixtures for context-control policy artifacts."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RULE_PATH = ROOT / "rules" / "prompt-workflow-context-controls.md"
HOOK_SPEC_PATH = ROOT / "hooks" / "HOOK_SPECS_PROMPT_WORKFLOW.md"


def test_context_control_rule_exists_with_required_sections() -> None:
    text = RULE_PATH.read_text(encoding="utf-8")
    assert "Base Minimal Instruction Layer" in text
    assert "On-Demand Skill Loading" in text
    assert "Compaction and Caching Strategy" in text
    assert "Runtime Enforcement Signals" in text
    assert "base_minimal_instruction_layer: true" in text
    assert "on_demand_skill_loading: true" in text


def test_hook_spec_exists_with_required_gates() -> None:
    text = HOOK_SPEC_PATH.read_text(encoding="utf-8")
    assert "PreToolUse Task/Agent (removed)" in text
    assert "agent-execution-intent-gate.py" in text
    assert "Leakage + Checklist + Scope (Stop)" in text
    assert "Required Deterministic Checklist Rows" in text
    assert "Runtime Context-Control Signals" in text
