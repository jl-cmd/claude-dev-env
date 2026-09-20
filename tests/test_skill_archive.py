"""Verify retired skills stay out of active discovery."""

from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_SKILLS_DIRECTORY = (
    REPOSITORY_ROOT / "packages" / "claude-dev-env" / ".agents" / "skills"
)
EXPECTED_SKILL_NAMES = frozenset({
    "hitl", "autoconverge", "pr-cleanup", "pr-name-by-capability",
    "pr-plain-language-cleanup", "pr-refinement", "pr-shared-extraction",
    "pr-small-cl", "pr-title-description", "prototype", "rebase",
    "review-router", "review-tier", "run-claude-dev-env", "session-log",
    "session-tidy", "skill-builder", "source-command-sr-loop", "update",
})
EXPECTED_STUB_TEXT = (
    "---\n"
    "name: skill-builder\n"
    "disable-model-invocation: true\n"
    "description: Placeholder for the skill-builder rework to follow pstack philosophy.\n"
    "---\n\n"
    "# Skill builder\n\n"
    "TODO: Rework to follow pstack philosophy.\n"
)


def test_retired_skills_are_absent_from_active_discovery() -> None:
    for skill_name in EXPECTED_SKILL_NAMES - {"skill-builder"}:
        assert not (ACTIVE_SKILLS_DIRECTORY / skill_name).exists(), skill_name


def test_skill_builder_keeps_only_the_requested_stub_and_instruction_files() -> None:
    stub_directory = ACTIVE_SKILLS_DIRECTORY / "skill-builder"
    assert (stub_directory / "SKILL.md").read_text(encoding="utf-8") == EXPECTED_STUB_TEXT
    actual_files = {
        file_path.relative_to(stub_directory).as_posix()
        for file_path in stub_directory.rglob("*")
        if file_path.is_file()
    }
    assert actual_files == {"SKILL.md", "AGENTS.md", ".claude/CLAUDE.md"}
