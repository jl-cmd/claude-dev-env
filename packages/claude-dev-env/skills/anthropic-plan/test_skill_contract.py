"""Contract tests for the anthropic-plan skill packet workflow."""

from __future__ import annotations

from pathlib import Path


SKILL_DIRECTORY = Path(__file__).resolve().parent
CLAUDE_DIRECTORY = SKILL_DIRECTORY.parent.parent
SKILL_PATH = SKILL_DIRECTORY / "SKILL.md"
PLAN_COMMAND_PATH = CLAUDE_DIRECTORY / "commands" / "plan.md"
VALIDATOR_AGENT_PATH = CLAUDE_DIRECTORY / "agents" / "plan-packet-validator.md"


def test_skill_invokes_plan_packet_workflow() -> None:
    skill_text = SKILL_PATH.read_text(encoding="utf-8")

    assert "Workflow({" in skill_text
    assert "workflow/plan-packet.mjs" in skill_text
    assert "docs/plans/<slug>/" in skill_text


def test_skill_launches_workflow_with_args_payload() -> None:
    skill_text = SKILL_PATH.read_text(encoding="utf-8")

    assert "args:" in skill_text
    assert "input:" not in skill_text


def test_skill_no_longer_mentions_single_home_plan_file() -> None:
    skill_text = SKILL_PATH.read_text(encoding="utf-8")

    assert "~/.claude/plans/<slug>.md" not in skill_text
    assert "single-file plan" not in skill_text.lower()


def test_skill_isolates_into_a_worktree_before_launch() -> None:
    skill_text = SKILL_PATH.read_text(encoding="utf-8")

    assert "EnterWorktree" in skill_text
    assert ".claude/worktrees/" in skill_text


def test_skill_documents_self_healing_writes() -> None:
    skill_text = SKILL_PATH.read_text(encoding="utf-8").lower()

    assert "worktree" in skill_text
    assert "stages" in skill_text
    assert "copies" in skill_text


def test_skill_names_validator_and_stop_before_code_rules() -> None:
    skill_text = SKILL_PATH.read_text(encoding="utf-8")

    assert "plan-packet-validator" in skill_text
    assert "validate_packet.py" in skill_text
    assert "stop before implementation" in skill_text.lower()


def test_plan_command_routes_to_anthropic_plan_without_stale_skills() -> None:
    command_text = PLAN_COMMAND_PATH.read_text(encoding="utf-8")

    assert "anthropic-plan" in command_text
    assert "write-plan" not in command_text
    assert "review-plan" not in command_text
    assert "plan-executor" not in command_text


def test_validator_agent_exists_and_is_read_only() -> None:
    agent_text = VALIDATOR_AGENT_PATH.read_text(encoding="utf-8")

    assert "name: plan-packet-validator" in agent_text
    assert "tools: Read, Grep, Glob, Bash" in agent_text
    assert "Never edit" in agent_text
    assert "source-backed" in agent_text
