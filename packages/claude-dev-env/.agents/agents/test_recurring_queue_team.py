"""Behavior checks for the recurring queue team definitions."""

import json
import re
from pathlib import Path

import pytest


team_directory = Path(__file__).parent
skill_directory = team_directory.parent / "skills" / "recurring-queue-team"
role_names = (
    "queue-coordinator",
    "queue-labeler",
    "queue-size-splitter",
    "queue-conflict-fixer",
    "queue-cleanup-runner",
    "queue-ops",
)
slack_channel_id_pattern = re.compile(r"\bC[A-Z0-9]{10}\b")


@pytest.mark.parametrize("role_name", role_names)
def test_role_profile_carries_shared_runtime_contract(role_name: str) -> None:
    profile = (team_directory / f"{role_name}.md").read_text(encoding="utf-8")
    assert "TOKEN-LITE" in profile
    assert "$env:SLACK_CHANNEL_ID" in profile
    assert slack_channel_id_pattern.search(profile) is None
    assert "~/.agents/workspaces/recurring-queue/team-ledger.json" in profile
    assert "07:00–01:00" in profile
    assert "spawn" in profile.lower() or "Delegate every heavy" in profile


def test_skill_records_ordered_gates_and_keepalive() -> None:
    skill = (skill_directory / "SKILL.md").read_text(encoding="utf-8")
    assert "Size, Conflict, Cleanup" in skill
    assert "Labeling runs in parallel" in skill
    assert "Keepalive" in skill
    assert "TOKEN-LITE" in skill
    assert "$env:SLACK_CHANNEL_ID" in skill
    assert slack_channel_id_pattern.search(skill) is None


def test_ledger_template_is_shared_and_empty() -> None:
    ledger_text = (skill_directory / "templates" / "team-ledger.json").read_text(
        encoding="utf-8"
    )
    ledger = json.loads(ledger_text)
    assert ledger["slack_channel_env_var"] == "SLACK_CHANNEL_ID"
    assert slack_channel_id_pattern.search(ledger_text) is None
    assert ledger["items"] == {}
    assert ledger["bake_in_confirmations"] == {}
