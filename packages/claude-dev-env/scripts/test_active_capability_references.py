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
    retired_capability_names,
    strip_inert_fenced_blocks,
    unresolved_active_capabilities,
)

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def test_inventory_includes_shipped_skill_and_agent_names() -> None:
    inventory = build_capability_inventory(PACKAGE_ROOT)
    assert "e-code-review" in inventory.all_skill_names or len(inventory.all_skill_names) > 0
    assert inventory.all_agent_names
    assert inventory.all_command_names


def test_strip_inert_fenced_blocks_drops_historical_examples() -> None:
    markdown = (
        "Use /sr-loop for cleanup.\n"
        "```historical\n"
        "Use /qbug for bugs.\n"
        "```\n"
        "Still active.\n"
    )
    stripped = strip_inert_fenced_blocks(markdown)
    assert "/qbug" not in stripped
    assert "/sr-loop" in stripped


def test_extract_active_capability_names_finds_invocations_and_manifests() -> None:
    markdown = (
        "Run /privacy-hygiene then open `issue-tracker/SKILL.md`.\n"
        "See the guide at [review guide](../reviews/SKILL.md).\n"
    )
    all_hits = extract_active_capability_names(markdown)
    all_names = {each_name for _line, each_name in all_hits}
    assert all_names == {"privacy-hygiene", "issue-tracker", "reviews"}


def test_urls_and_deep_paths_name_no_capability() -> None:
    markdown = (
        "Read [the advisor guide](https://code.claude.com/docs/en/advisor).\n"
        "Call `POST /repos/{owner}/{repo}/issues/{number}/comments`.\n"
        "The default role is `bugteam`.\n"
    )
    assert extract_active_capability_names(markdown) == []


def test_retired_names_come_from_the_shipped_inventory() -> None:
    inventory = build_capability_inventory(PACKAGE_ROOT)
    all_retired_names = retired_capability_names(PACKAGE_ROOT, inventory)
    assert "qbug" in all_retired_names
    assert "findbugs" in all_retired_names
    assert not all_retired_names.intersection(inventory.all_known_names())


def test_a_retired_name_fails_classification() -> None:
    inventory = build_capability_inventory(PACKAGE_ROOT)
    all_retired_names = retired_capability_names(PACKAGE_ROOT, inventory)
    for each_retired_name in sorted(all_retired_names):
        reason = classify_capability_reference(each_retired_name, all_retired_names)
        assert reason is not None
        assert each_retired_name in reason


def test_shipped_and_unknown_names_pass() -> None:
    inventory = build_capability_inventory(PACKAGE_ROOT)
    all_retired_names = retired_capability_names(PACKAGE_ROOT, inventory)
    for each_shipped_name in sorted(inventory.all_known_names()):
        assert (
            classify_capability_reference(each_shipped_name, all_retired_names) is None
        ), each_shipped_name
    assert classify_capability_reference("not-a-capability", all_retired_names) is None


def test_a_skill_dropped_from_the_tree_reports_without_a_hand_kept_list(
    tmp_path: Path,
) -> None:
    package_root = tmp_path / "pkg"
    skill_directory = package_root / "skills" / "kept-skill"
    skill_directory.mkdir(parents=True)
    (skill_directory / "SKILL.md").write_text(
        "Run /dropped-skill after /kept-skill.\n", encoding="utf-8"
    )
    (package_root / "agents").mkdir()
    (package_root / "commands").mkdir()
    (package_root / "bin").mkdir()
    (package_root / "bin" / "ever-shipped-skills.mjs").write_text(
        "export const EVER_SHIPPED_SKILL_NAMES = new Set([\n"
        "    'kept-skill',\n"
        "    'dropped-skill',\n"
        "]);\n",
        encoding="utf-8",
    )
    all_unresolved = unresolved_active_capabilities(
        package_root,
        all_relative_markdown_paths=["skills/kept-skill/SKILL.md"],
    )
    assert [each.capability_name for each in all_unresolved] == ["dropped-skill"]


def _write_fixture_package(package_root: Path, skill_name: str, prose: str) -> None:
    skill_directory = package_root / "skills" / skill_name
    skill_directory.mkdir(parents=True)
    (skill_directory / "SKILL.md").write_text(prose, encoding="utf-8")
    (package_root / "agents").mkdir()
    (package_root / "agents" / "shipped-agent.md").write_text(
        "# agent\n", encoding="utf-8"
    )
    (package_root / "commands").mkdir()
    (package_root / "commands" / "shipped-command.md").write_text(
        "# command\n", encoding="utf-8"
    )
    (package_root / "bin").mkdir()
    (package_root / "bin" / "ever-shipped-skills.mjs").write_text(
        "export const EVER_SHIPPED_SKILL_NAMES = new Set([\n"
        f"    '{skill_name}',\n"
        "    'qbug',\n"
        "]);\n",
        encoding="utf-8",
    )


def test_unresolved_reports_file_and_line_for_fixture(tmp_path: Path) -> None:
    package_root = tmp_path / "pkg"
    _write_fixture_package(
        package_root, "shipped-skill", "Active instruction: call /qbug now.\n"
    )
    all_unresolved = unresolved_active_capabilities(
        package_root,
        all_relative_markdown_paths=["skills/shipped-skill/SKILL.md"],
    )
    assert all_unresolved
    first = all_unresolved[0]
    assert first.capability_name == "qbug"
    assert first.line_number == 1
    assert first.file_path == "skills/shipped-skill/SKILL.md"
    assert "retired" in first.reason


def test_inert_historical_qbug_does_not_fail(tmp_path: Path) -> None:
    package_root = tmp_path / "pkg"
    _write_fixture_package(
        package_root,
        "ok-skill",
        "```historical\nLegacy /qbug workflow.\n```\nUse /ok-skill.\n",
    )
    all_unresolved = unresolved_active_capabilities(
        package_root,
        all_relative_markdown_paths=["skills/ok-skill/SKILL.md"],
    )
    assert all(each.capability_name != "qbug" for each in all_unresolved)


def test_the_package_names_no_retired_capability() -> None:
    all_unresolved = unresolved_active_capabilities(PACKAGE_ROOT)
    report = "\n".join(
        f"{each.file_path}:{each.line_number} {each.capability_name}"
        for each in all_unresolved
    )
    assert not all_unresolved, report
