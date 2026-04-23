"""Markdown assertion tests for bugteam SKILL.md additive options."""

from __future__ import annotations

import pathlib


def _read_skill_text() -> str:
    skill_path = pathlib.Path(__file__).parent / "SKILL.md"
    return skill_path.read_text(encoding="utf-8")


def test_skill_references_fix_implementer_env_var():
    skill_text = _read_skill_text()
    assert "BUGTEAM_FIX_IMPLEMENTER" in skill_text


def test_skill_names_default_implementer_subagent_type():
    skill_text = _read_skill_text()
    assert "clean-coder" in skill_text


def test_skill_names_optional_groq_implementer_subagent_type():
    skill_text = _read_skill_text()
    assert "groq-coder" in skill_text


def test_skill_documents_bugbot_retrigger_flag():
    skill_text = _read_skill_text()
    assert "--bugbot-retrigger" in skill_text
