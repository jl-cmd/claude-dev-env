"""Markdown assertion tests for monitor-open-prs SKILL.md."""

from __future__ import annotations

import pathlib


def _read_skill_text() -> str:
    skill_path = pathlib.Path(__file__).parent / "SKILL.md"
    return skill_path.read_text(encoding="utf-8")


def test_skill_has_frontmatter_name():
    skill_text = _read_skill_text()
    assert skill_text.startswith("---\n")
    assert "name: monitor-open-prs" in skill_text


def test_skill_requires_agent_teams_env_var():
    skill_text = _read_skill_text()
    assert "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" in skill_text


def test_skill_invokes_bugteam_with_groq_implementer():
    skill_text = _read_skill_text()
    assert "BUGTEAM_FIX_IMPLEMENTER" in skill_text
    assert "groq-coder" in skill_text


def test_skill_references_bugbot_retrigger_flag():
    skill_text = _read_skill_text()
    assert "--bugbot-retrigger" in skill_text


def test_skill_enumerates_both_owner_scopes():
    skill_text = _read_skill_text()
    assert "jl-cmd" in skill_text
    assert "JonEcho" in skill_text


def test_skill_documents_bws_wrapping():
    skill_text = _read_skill_text()
    assert "bws run" in skill_text
