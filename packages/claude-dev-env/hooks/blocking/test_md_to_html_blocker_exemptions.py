"""Tests for md_to_html_blocker directory and filename exemptions.

Covers which directory trees (`.claude/`, `.claude-*/` profile and plugin
directories, source subtrees under `packages/claude-dev-env/`, `agents/`,
`skills/`, `commands/`) and which
root-level filenames (`README.md`, `CHANGELOG.md`, `CLAUDE.md`, `AGENTS.md`,
`SKILL.md`) are exempt from the `.md` block, and the segment-anchored matching
that prevents nested look-alike paths from bypassing the block.
"""

import json
import os
import sys

_BLOCKING_DIRECTORY = os.path.dirname(__file__)

if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)

from _md_to_html_blocker_test_support import (  # noqa: E402
    _run_hook,
)


def test_blocks_nested_packages_claude_dev_env_path():
    """`packages/claude-dev-env/` exemption is anchored to top-level use only;
    a nested directory like `notes/packages/claude-dev-env/docs/...` is NOT a
    Claude Code source path and must still be blocked. Substring matching let
    this bypass through; segment-anchored matching prevents it."""
    result = _run_hook(
        "Write",
        {"file_path": "notes/packages/claude-dev-env/docs/guide.md", "content": "# Hello"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
        f"Nested fake claude-dev-env path must still be blocked; got {output!r}"
    )


def test_passes_claude_dir():
    result = _run_hook(
        "Write",
        {"file_path": ".claude/rules/foo.md", "content": "# Rule"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_nested_claude_dir():
    result = _run_hook(
        "Write",
        {"file_path": "notes/.claude/plans/plan.md", "content": "# Plan"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_readme_at_root():
    result = _run_hook(
        "Write",
        {"file_path": "README.md", "content": "# README"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_changelog_at_root():
    result = _run_hook(
        "Write",
        {"file_path": "CHANGELOG.md", "content": "# Changelog"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_blocks_readme_not_at_root():
    result = _run_hook(
        "Write",
        {"file_path": "docs/README.md", "content": "# README"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_changelog_not_at_root():
    result = _run_hook(
        "Write",
        {"file_path": "sub/CHANGELOG.md", "content": "# Log"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_passes_claude_md_at_root():
    result = _run_hook(
        "Write",
        {"file_path": "CLAUDE.md", "content": "# CLAUDE"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_agents_md_at_root():
    result = _run_hook(
        "Write",
        {"file_path": "AGENTS.md", "content": "# AGENTS"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_blocks_claude_md_not_at_root():
    result = _run_hook(
        "Write",
        {"file_path": "docs/CLAUDE.md", "content": "# CLAUDE"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_agents_md_not_at_root():
    result = _run_hook(
        "Write",
        {"file_path": "sub/AGENTS.md", "content": "# AGENTS"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_passes_claude_md_file():
    result = _run_hook(
        "Write",
        {"file_path": ".claude/CLAUDE.md", "content": "# CLAUDE.md"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_windows_path_claude_exempt():
    result = _run_hook(
        "Write",
        {"file_path": "project\\.claude\\rules\\foo.md", "content": "# Rule"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_claude_dir_case_insensitive():
    result = _run_hook(
        "Write",
        {"file_path": ".Claude/rules/foo.md", "content": "# Rule"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_readme_lowercase_at_root():
    result = _run_hook(
        "Write",
        {"file_path": "readme.md", "content": "# readme"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_blocks_claude_path_traversal_bypass():
    result = _run_hook(
        "Write",
        {"file_path": ".claude/../docs/guide.md", "content": "# Bypass"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_passes_dot_claude_plugin_directory():
    result = _run_hook(
        "Write",
        {"file_path": ".claude-plugin/manifest.md", "content": "# Manifest"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_nested_dot_claude_plugin_directory():
    result = _run_hook(
        "Write",
        {
            "file_path": "Y:/repo/.claude-plugin/skills/foo/SKILL.md",
            "content": "# Skill",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_skill_md_at_any_depth():
    result = _run_hook(
        "Write",
        {
            "file_path": "packages/dev-env/skills/pr-converge/SKILL.md",
            "content": "# Skill",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_skill_md_uppercase():
    result = _run_hook(
        "Write",
        {"file_path": "any/path/SKILL.MD", "content": "# Skill"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_agents_directory_anywhere():
    result = _run_hook(
        "Write",
        {
            "file_path": "packages/dev-env/agents/pr-description-writer.md",
            "content": "# Agent",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_skills_reference_directory():
    result = _run_hook(
        "Write",
        {
            "file_path": "packages/dev-env/skills/pr-converge/reference/per-tick.md",
            "content": "# Reference",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_commands_directory_anywhere():
    result = _run_hook(
        "Write",
        {"file_path": "commands/pyguide-health.md", "content": "# Command"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_claude_dev_env_docs_dir():
    """A .md file under ``packages/claude-dev-env/docs/`` is exempt. The
    segment-anywhere rule does not list ``docs``; this exemption fires only
    via the anchored helper."""
    result = _run_hook(
        "Write",
        {
            "file_path": "packages/claude-dev-env/docs/PR_DESCRIPTION_GUIDE.md",
            "content": "# Guide",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_claude_dev_env_rules_dir():
    """A .md file under ``packages/claude-dev-env/rules/`` is exempt. The
    segment-anywhere rule does not list ``rules``; the anchored helper is
    the only path to this exemption."""
    result = _run_hook(
        "Write",
        {
            "file_path": "packages/claude-dev-env/rules/my-rule.md",
            "content": "# Rule",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_claude_dev_env_system_prompts_dir():
    """A .md file under ``packages/claude-dev-env/system-prompts/`` is
    exempt via the anchored helper."""
    result = _run_hook(
        "Write",
        {
            "file_path": "packages/claude-dev-env/system-prompts/new-prompt.md",
            "content": "# Prompt",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_claude_dev_env_windows_backslash_path():
    """A Windows-style backslash relative path under
    ``packages\\claude-dev-env\\<dir>\\`` is exempt."""
    result = _run_hook(
        "Write",
        {
            "file_path": "packages\\claude-dev-env\\docs\\windows-style.md",
            "content": "# Guide",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_claude_dev_env_absolute_drive_letter_path():
    """A Windows absolute drive-letter path containing the anchored
    ``packages\\claude-dev-env\\<dir>\\`` indicator at any depth is exempt."""
    result = _run_hook(
        "Write",
        {
            "file_path": "Y:\\repo\\packages\\claude-dev-env\\docs\\drive-letter.md",
            "content": "# Guide",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_blocks_md_under_packages_but_not_in_anchored_source_subdir():
    """A .md file inside the package but under a non-source subtree (e.g.
    ``packages/claude-dev-env/hooks/blocking/``) is blocked. The anchored
    helper accepts only the named source subdirectories (agents, docs,
    skills, rules, system-prompts, commands)."""
    result = _run_hook(
        "Write",
        {
            "file_path": "packages/claude-dev-env/hooks/blocking/notes.md",
            "content": "# Notes",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_nested_claude_dev_env_substring_does_not_bypass():
    """A path that contains the anchored prefix as a non-leading substring
    (e.g. ``notes/packages/claude-dev-env/docs/foo.md``) is blocked. The
    anchored helper matches only at the start of the path (relative) or at
    the root of an absolute path."""
    result = _run_hook(
        "Write",
        {
            "file_path": "notes/packages/claude-dev-env/docs/foo.md",
            "content": "# Notes",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_ordinary_docs_md_file():
    result = _run_hook(
        "Write",
        {"file_path": "docs/intro.md", "content": "# Intro"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_passes_claude_profile_memory_directory():
    """A Claude profile directory (`.claude-<name>/`, e.g. `.claude-mel/`)
    carries the same infrastructure as `.claude/`; per-project memory files
    under it accept .md writes."""
    result = _run_hook(
        "Write",
        {
            "file_path": (
                "C:/Users/sample/.claude-mel/projects"
                "/sample-project/memory/fact.md"
            ),
            "content": "# Fact",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_relative_claude_profile_directory():
    result = _run_hook(
        "Write",
        {
            "file_path": ".claude-mel/projects/sample/memory/fact.md",
            "content": "# Fact",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_claude_profile_directory_case_insensitive():
    result = _run_hook(
        "Write",
        {"file_path": "C:/Users/sample/.Claude-Mel/MEMORY.md", "content": "# Index"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_blocks_dot_directory_that_starts_with_claude_but_lacks_hyphen():
    """`.claudette/` is not Claude infrastructure: only a directory named
    exactly `.claude` or carrying the `.claude-` prefix is exempt."""
    result = _run_hook(
        "Write",
        {"file_path": "notes/.claudette/intro.md", "content": "# Intro"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_claude_prefixed_filename_in_plain_directory():
    """A file merely named with the `.claude-` prefix (e.g.
    `docs/.claude-notes.md`) is not Claude infrastructure: the exemption
    matches directory segments only, so a `.claude-*.md` basename inside
    an ordinary directory is blocked."""
    result = _run_hook(
        "Write",
        {"file_path": "docs/.claude-notes.md", "content": "# Notes"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
