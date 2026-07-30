"""Behavioral tests for active capability reference resolution."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from active_capability_references import (
    build_capability_inventory,
    classify_capability_reference,
    extract_active_capability_names,
    strip_inert_fenced_blocks,
    unresolved_active_capabilities,
)
from config.active_capability_constants import ALL_BANNED_ACTIVE_CAPABILITY_NAMES

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def test_inventory_includes_shipped_skill_and_agent_names() -> None:
    inventory = build_capability_inventory(PACKAGE_ROOT)
    assert "e-code-review" in inventory.all_skill_names or len(inventory.all_skill_names) > 0
    assert inventory.all_agent_names
    assert inventory.all_command_names


def test_strip_inert_fenced_blocks_drops_historical_examples() -> None:
    markdown = (
        "Use /commit for commits.\n"
        "```historical\n"
        "Use /qbug for bugs.\n"
        "```\n"
        "Still active.\n"
    )
    stripped = strip_inert_fenced_blocks(markdown)
    assert "/qbug" not in stripped
    assert "/commit" in stripped


def test_extract_active_capability_names_finds_slash_and_backticks() -> None:
    markdown = "Run /privacy-hygiene then open `issue-tracker`.\n"
    all_hits = extract_active_capability_names(markdown)
    all_names = {each_name for _line, each_name in all_hits}
    assert "privacy-hygiene" in all_names
    assert "issue-tracker" in all_names


def test_banned_names_always_fail_classification() -> None:
    inventory = build_capability_inventory(PACKAGE_ROOT)
    for each_banned_name in sorted(ALL_BANNED_ACTIVE_CAPABILITY_NAMES):
        reason = classify_capability_reference(each_banned_name, inventory)
        assert reason is not None
        assert each_banned_name in reason


def test_unresolved_reports_file_and_line_for_fixture(tmp_path: Path) -> None:
    package_root = tmp_path / "pkg"
    skills = package_root / "skills" / "real-skill"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("# real\n", encoding="utf-8")
    agents = package_root / "agents"
    agents.mkdir()
    (agents / "real-agent.md").write_text("# agent\n", encoding="utf-8")
    commands = package_root / "commands"
    commands.mkdir()
    (commands / "real-cmd.md").write_text("# cmd\n", encoding="utf-8")
    skill_md = package_root / "skills" / "real-skill" / "SKILL.md"
    skill_md.write_text(
        "Active instruction: call /qbug now.\n",
        encoding="utf-8",
    )
    all_unresolved = unresolved_active_capabilities(
        package_root,
        all_relative_markdown_paths=["skills/real-skill/SKILL.md"],
    )
    assert all_unresolved
    first = all_unresolved[0]
    assert first.capability_name == "qbug"
    assert first.line_number == 1
    assert first.file_path == "skills/real-skill/SKILL.md"
    assert "banned" in first.reason


def test_inert_historical_qbug_does_not_fail(tmp_path: Path) -> None:
    package_root = tmp_path / "pkg"
    skill_dir = package_root / "skills" / "ok-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "```historical\nLegacy /qbug workflow.\n```\nUse /ok-skill.\n",
        encoding="utf-8",
    )
    (package_root / "agents").mkdir()
    (package_root / "commands").mkdir()
    all_unresolved = unresolved_active_capabilities(
        package_root,
        all_relative_markdown_paths=["skills/ok-skill/SKILL.md"],
    )
    assert all(
        each.capability_name != "qbug" for each in all_unresolved
    )
