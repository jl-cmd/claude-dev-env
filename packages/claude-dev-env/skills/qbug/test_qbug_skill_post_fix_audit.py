"""Tests verifying qbug SKILL.md contains required post-fix self-audit structural elements.

Covers:
- Post-fix self-audit inserted between py_compile and git add
- Internal iteration cap of 3
- loop-N-diagnostics.json with all eight source keys
- converged condition requires both primary and post-fix audits clean
- Stuck state when post-fix audit does not converge after 3 iterations
"""

from __future__ import annotations

from pathlib import Path


SKILL_FILE_PATH = Path(__file__).parent / "SKILL.md"


def _load_skill_text() -> str:
    return SKILL_FILE_PATH.read_text(encoding="utf-8")


def test_should_require_post_fix_gate_before_git_add() -> None:
    skill_text = _load_skill_text()
    assert "code_rules_gate" in skill_text, (
        "FIX step must run code_rules_gate against modified files"
    )
    assert "post-fix" in skill_text.lower() or "post_fix" in skill_text.lower(), (
        "FIX step must reference a post-fix audit phase"
    )


def test_should_require_post_fix_audit_of_fix_diff() -> None:
    skill_text = _load_skill_text()
    assert "fix_diff" in skill_text, (
        "FIX step must compute fix_diff for the post-fix scoped audit"
    )


def test_should_require_paranoid_mode_with_haiku_on_post_fix() -> None:
    skill_text = _load_skill_text()
    assert "paranoid" in skill_text.lower(), (
        "Post-fix audit must be flagged as paranoid mode with Haiku secondary"
    )


def test_should_require_internal_iteration_cap_of_three() -> None:
    skill_text = _load_skill_text()
    assert "internal iteration cap = 3" in skill_text, (
        "FIX step must specify the exact phrase 'internal iteration cap = 3'"
    )
    assert "stuck: post-fix audit not converging" in skill_text, (
        "Exit message for cap exceeded must be 'stuck: post-fix audit not converging'"
    )


def test_should_only_git_add_when_post_fix_audit_is_clean() -> None:
    skill_text = _load_skill_text()
    post_fix_audit_block_header = "Post-fix self-audit"
    post_fix_audit_block_index = skill_text.find(post_fix_audit_block_header)
    assert post_fix_audit_block_index != -1, (
        f"SKILL.md must contain the literal block header '{post_fix_audit_block_header}'"
    )
    git_add_index = skill_text.find("git add", post_fix_audit_block_index)
    assert git_add_index > post_fix_audit_block_index, (
        "git add must appear after the Post-fix self-audit block header, not before"
    )


def test_should_require_loop_n_diagnostics_json() -> None:
    skill_text = _load_skill_text()
    assert "diagnostics.json" in skill_text, (
        "Each loop must write loop-N-diagnostics.json"
    )


def test_contract_should_require_all_eight_source_keys_in_diagnostics() -> None:
    contract_path = (
        Path(__file__).parent.parent / "bugteam" / "reference" / "audit-contract.md"
    )
    contract_text = contract_path.read_text(encoding="utf-8")
    required_keys = [
        "loop",
        "gate_findings",
        "primary_findings",
        "adversarial_findings",
        "haiku_findings",
        "post_fix_findings",
        "merged",
        "deduped",
    ]
    for each_key in required_keys:
        assert each_key in contract_text, (
            f"loop-N-diagnostics.json schema in audit-contract.md must contain key '{each_key}'"
        )


def test_should_update_exit_conditions_to_require_post_fix_clean() -> None:
    skill_text = _load_skill_text()
    assert (
        "post_fix_audit_clean" in skill_text
        or "post-fix audit clean" in skill_text.lower()
    ), "converged exit condition must require post_fix_audit_clean"
