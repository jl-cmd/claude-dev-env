"""Markdown assertion tests for monitor-open-prs team lifecycle.

Locks in the contract that the sweep must:
  - own a single long-lived team for every dispatched /bugteam
  - pass attach mode + the team name into each per-PR /bugteam dispatch
  - tear down only after all PR polling completes
"""

from __future__ import annotations

import pathlib


def _skill_text() -> str:
    here = pathlib.Path(__file__).parent
    return (here / "SKILL.md").read_text(encoding="utf-8")


def test_skill_creates_one_team_for_the_whole_sweep():
    skill_text = _skill_text()
    assert "TeamCreate" in skill_text
    sweep_phrases = [
        "one team for the whole sweep",
        "single team for the sweep",
        "single long-lived team",
    ]
    assert any(phrase in skill_text for phrase in sweep_phrases)


def test_skill_passes_attach_lifecycle_to_each_bugteam_dispatch():
    skill_text = _skill_text()
    assert "BUGTEAM_TEAM_LIFECYCLE" in skill_text
    assert "attach" in skill_text
    assert "BUGTEAM_TEAM_NAME" in skill_text


def test_skill_tears_down_team_after_polling_completes():
    skill_text = _skill_text()
    assert "TeamDelete" in skill_text
    teardown_phrases = [
        "after every PR has exited polling",
        "after polling completes",
        "after the sweep",
        "after all polling",
    ]
    assert any(phrase in skill_text for phrase in teardown_phrases)
