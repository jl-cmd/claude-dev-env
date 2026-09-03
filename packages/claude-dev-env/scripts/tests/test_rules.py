"""Tests for discovered Claude-to-Cursor rule mappings."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from sync_to_cursor.rules import build_mappings

_PACKAGE_ROOT = _SCRIPTS_DIR.parent
_SKIPPED_RULE_FILE_NAMES = frozenset({"CLAUDE.md", "AGENTS.md"})


def _write_minimal_curated_rules(rules_directory: Path) -> None:
    rules_directory.mkdir(parents=True, exist_ok=True)
    (rules_directory / "code-standards.md").write_text(
        "# Code standards stub\n", encoding="utf-8"
    )
    (rules_directory / "tasklings-preferences.md").write_text(
        '---\npaths:\n  - "Y:/x/**"\n---\n\n# Tasklings\n',
        encoding="utf-8",
    )
    (rules_directory / "bdd.md").write_text("# BDD\n", encoding="utf-8")
    (rules_directory / "testing.md").write_text(
        '---\npaths:\n  - "**/test_*.py"\n---\n\n# Testing\n',
        encoding="utf-8",
    )
    (rules_directory / "research-mode.md").write_text("# RM\n", encoding="utf-8")
    (rules_directory / "explore-thoroughly.md").write_text("# ET\n", encoding="utf-8")


def test_build_mappings_emits_stem_mdc_for_remaining_claude_rules(
    tmp_path: Path,
) -> None:
    claude = tmp_path / ".claude"
    _write_minimal_curated_rules(claude / "rules")
    (claude / "docs").mkdir(parents=True, exist_ok=True)
    (claude / "rules" / "asd-ste100-language.md").write_text(
        "# ASD-STE100 Language Policy\n\nBe brief.\n",
        encoding="utf-8",
    )
    (claude / "rules" / "CLAUDE.md").write_text(
        "# Package inventory\n", encoding="utf-8"
    )
    (claude / "rules" / "AGENTS.md").write_text("# Agent inventory\n", encoding="utf-8")
    mappings = build_mappings(claude)
    output_by_key = {each_mapping.key: each_mapping for each_mapping in mappings}
    discovered = output_by_key["asd-ste100-language"]
    assert discovered.output_name == "asd-ste100-language.mdc"
    assert discovered.always_apply is True
    assert discovered.description == "ASD-STE100 Language Policy"
    assert "CLAUDE.md" not in {
        each_source.name
        for each_mapping in mappings
        for each_source in each_mapping.sources
    }
    assert "AGENTS.md" not in {
        each_source.name
        for each_mapping in mappings
        for each_source in each_mapping.sources
    }


def test_every_shipped_claude_rule_maps_to_an_mdc() -> None:
    mappings = build_mappings(_PACKAGE_ROOT)
    output_name_by_rule_file = {}
    for each_mapping in mappings:
        for each_source in each_mapping.sources:
            if each_source.parent.name == "rules" and each_source.suffix == ".md":
                output_name_by_rule_file[each_source.name] = each_mapping.output_name
    for each_rule_file in sorted((_PACKAGE_ROOT / "rules").glob("*.md")):
        if each_rule_file.name in _SKIPPED_RULE_FILE_NAMES:
            continue
        assert each_rule_file.name in output_name_by_rule_file, each_rule_file.name


def _comment_policy_phrases() -> tuple[str, ...]:
    return (
        "when a change touches code that an existing comment describes or is attached to",
        "leave comments tied to untouched code unchanged",
        "keep comment cleanup inside the requested task",
        "production and tests follow one rule",
        "changed directive, todo, fixme, hack, xxx, and type-ignore comments are removed rather than added or justified",
    )


def _comment_policy_surfaces(package_root: Path) -> tuple[Path, ...]:
    return (
        package_root.parent.parent / "AGENTS.md",
        package_root / "AGENTS.md",
        package_root / "docs" / "CODE_RULES.md",
        package_root / "system-prompts" / "software-engineer.xml",
        package_root / ".agents" / "agents" / "clean-coder.md",
        package_root / ".agents" / "agents" / "code-quality-agent.md",
        package_root / "_shared" / "pr-loop" / "code-rules-gate.md",
        package_root / "audit-rubrics" / "category_rubrics" / "category-j-code-rules-compliance.md",
        package_root / "audit-rubrics" / "prompts" / "category-j-code-rules-compliance.md",
        package_root / "audit-rubrics" / "category_rubrics" / "category-l-behavior-equivalence.md",
        package_root / "audit-rubrics" / "prompts" / "category-l-behavior-equivalence.md",
        package_root / ".agents" / "skills" / "grok-spawn" / "reference" / "worker-briefs.md",
        package_root.parent.parent / ".github" / "copilot-instructions.md",
    )


def _worker_policy_phrases() -> tuple[str, ...]:
    return (
        "do not add code comments.",
        "preserve existing comments.",
        "docstrings remain allowed.",
    )


def _worker_policy_surfaces(package_root: Path) -> tuple[Path, ...]:
    return (
        package_root.parent.parent / "AGENTS.md",
        package_root / "AGENTS.md",
        package_root / "docs" / "CODE_RULES.md",
        package_root / "system-prompts" / "software-engineer.xml",
        package_root / ".agents" / "agents" / "clean-coder.md",
        package_root / ".agents" / "skills" / "grok-spawn" / "reference" / "worker-briefs.md",
        package_root.parent.parent / ".github" / "copilot-instructions.md",
    )


def test_comment_guidance_reaches_installed_instruction_surfaces() -> None:
    expected_phrases = _comment_policy_phrases()
    all_surface_paths = _comment_policy_surfaces(_PACKAGE_ROOT)

    for each_surface_path in all_surface_paths:
        surface_text = each_surface_path.read_text(encoding="utf-8").lower()
        for each_phrase in expected_phrases:
            assert each_phrase in surface_text, each_surface_path
    for each_surface_path in _worker_policy_surfaces(_PACKAGE_ROOT):
        surface_text = each_surface_path.read_text(encoding="utf-8").lower()
        for each_phrase in _worker_policy_phrases():
            assert each_phrase in surface_text, each_surface_path
