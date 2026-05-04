"""Markdown assertion tests for bugteam team-lifecycle decoupling.

Locks in the contract that the bugteam skill must:
  - support three team lifecycle modes (`owned`, `attach`, `auto`)
  - default to `auto` (back-compat for solo invocations, safe for nested ones)
  - skip `TeamDelete` when the invocation did not create the team
  - parse the runtime's `Already leading team "<name>"` error and attach
"""

from __future__ import annotations

import pathlib


def _read(relative_path: str) -> str:
    here = pathlib.Path(__file__).parent
    return (here / relative_path).read_text(encoding="utf-8")


def _skill_text() -> str:
    return _read("SKILL.md")


def _path_a_text() -> str:
    return _read("reference/workflow-path-a-orchestrated-teams.md")


def _constraints_text() -> str:
    return _read("CONSTRAINTS.md")


def test_skill_documents_three_team_lifecycle_modes():
    skill_text = _skill_text()
    assert "BUGTEAM_TEAM_LIFECYCLE" in skill_text
    assert "owned" in skill_text
    assert "attach" in skill_text
    assert "auto" in skill_text


def test_skill_documents_auto_as_default_lifecycle():
    skill_text = _skill_text()
    assert "default" in skill_text.lower()
    assert "BUGTEAM_TEAM_LIFECYCLE" in skill_text
    auto_default_phrases = [
        "default: `auto`",
        "default `auto`",
        "defaults to `auto`",
        "defaults to auto",
        "default to `auto`",
    ]
    assert any(phrase in skill_text for phrase in auto_default_phrases)


def test_skill_documents_BUGTEAM_TEAM_NAME_env_for_attach_mode():
    skill_text = _skill_text()
    assert "BUGTEAM_TEAM_NAME" in skill_text


def test_path_a_workflow_handles_already_leading_team_error():
    workflow_text = _path_a_text()
    assert 'Already leading team "' in workflow_text
    assert "team_owned" in workflow_text


def test_path_a_workflow_step_4_skips_team_delete_when_not_owned():
    workflow_text = _path_a_text()
    assert "TeamDelete" in workflow_text
    assert "team_owned" in workflow_text
    skip_phrases = [
        "skip `TeamDelete`",
        "skip TeamDelete",
        "omit `TeamDelete`",
        "omit TeamDelete",
        "do not call `TeamDelete`",
        "do not call TeamDelete",
    ]
    assert any(phrase in workflow_text for phrase in skip_phrases)


def test_path_a_workflow_documents_attach_mode_reuses_team_name():
    workflow_text = _path_a_text()
    assert "BUGTEAM_TEAM_NAME" in workflow_text
    assert "attach" in workflow_text


def test_constraints_lead_only_cleanup_includes_team_owned():
    constraints_text = _constraints_text()
    assert "team_owned" in constraints_text


def test_constraints_warn_against_owned_mode_inside_orchestrator():
    constraints_text = _constraints_text()
    assert "orchestrator" in constraints_text.lower()
    assert "attach" in constraints_text


def test_skill_md_physical_lines_fit_eighty_column_limit():
    skill_text = _skill_text()
    for each_line_number, each_physical_line in enumerate(skill_text.splitlines(), 1):
        assert len(each_physical_line) <= 80, (
            "SKILL.md line %s exceeds 80 columns (%s chars)"
            % (each_line_number, len(each_physical_line))
        )
