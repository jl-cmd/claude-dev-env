"""Markdown assertion tests for pr-converge orchestrator team lifecycle.

Locks in the contract that pr-converge multi-PR orchestration must:
  - own a single long-lived team for the whole sweep
  - pass that team to every bugteam invocation via attach mode
  - tear down only when every PR reaches `converged` or `blocked`
"""

from __future__ import annotations

import pathlib


def _skill_text() -> str:
    here = pathlib.Path(__file__).parent
    return (here / "SKILL.md").read_text(encoding="utf-8")


def test_skill_documents_orchestrator_owned_team_in_multi_pr_mode():
    skill_text = _skill_text()
    assert "team_name" in skill_text
    assert "TeamCreate" in skill_text
    assert "orchestrator" in skill_text.lower()


def test_skill_passes_attach_mode_to_bugteam_invocations():
    skill_text = _skill_text()
    assert "BUGTEAM_TEAM_LIFECYCLE" in skill_text
    assert "attach" in skill_text
    assert "BUGTEAM_TEAM_NAME" in skill_text


def test_skill_tears_down_team_only_on_full_convergence():
    skill_text = _skill_text()
    assert "TeamDelete" in skill_text
    convergence_phrases = [
        "every PR",
        "all PRs",
        "fully converged",
        "every prs[",
    ]
    assert any(phrase in skill_text for phrase in convergence_phrases)


def test_state_schema_includes_team_name_field():
    skill_text = _skill_text()
    assert '"team_name"' in skill_text or "team_name:" in skill_text
