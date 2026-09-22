"""Verify preserved skill trees and their removal from active discovery."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_DIRECTORY = REPOSITORY_ROOT / "skill-archive"
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


def _git_output(*arguments: str) -> str:
    environment = {
        environment_name: environment_text
        for environment_name, environment_text in os.environ.items()
        if not environment_name.upper().startswith("GIT_")
    }
    completed_process = subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed_process.stdout.strip()


def test_archived_skill_trees_match_recorded_sources() -> None:
    manifest = json.loads(
        (ARCHIVE_DIRECTORY / "source-trees.json").read_text(encoding="utf-8")
    )
    assert set(manifest["skills"]) == EXPECTED_SKILL_NAMES
    assert manifest["archive_directory"] == "skill-archive"
    assert manifest["retained_stub"] == "skill-builder"
    for skill_name, expected_tree in manifest["skills"].items():
        assert (ARCHIVE_DIRECTORY / skill_name / "SKILL.md").is_file()
        actual_tree = _git_output("rev-parse", f"HEAD:skill-archive/{skill_name}")
        assert actual_tree == expected_tree, skill_name
    assert _git_output("diff", "--name-only", "HEAD", "--", "skill-archive") == ""


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
    assert (ARCHIVE_DIRECTORY / "skill-builder" / "workflows").is_dir()
    assert (ARCHIVE_DIRECTORY / "skill-builder" / "references").is_dir()
    assert (ARCHIVE_DIRECTORY / "skill-builder" / "templates").is_dir()
