"""Behavior tests for md_to_html_blocker_constants module."""

from __future__ import annotations

import sys
from pathlib import Path

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants import md_to_html_blocker_constants as constants_module


def test_indicator_path_segments_are_named_constants() -> None:
    """The two leading segments of the Claude Code source indicator
    (`packages/claude-dev-env`) must live as named constants so
    `_is_exempt_path` references symbols, not inline literals. Bugbot flagged
    these as magic strings even though the third segment was already a named
    constant; align all three."""
    assert constants_module.PACKAGES_TOP_LEVEL_SEGMENT == "packages"
    assert constants_module.CLAUDE_DEV_ENV_REPO_NAME_SEGMENT == "claude-dev-env"
    for each_name in ("PACKAGES_TOP_LEVEL_SEGMENT", "CLAUDE_DEV_ENV_REPO_NAME_SEGMENT"):
        assert each_name in constants_module.__all__


def test_claude_code_source_top_directories_enumerates_six_canonical_dirs() -> None:
    """The exempt top-level directory set must match the six canonical Claude
    Code source directories (agents, docs, skills, rules, system-prompts,
    commands). Drift in either direction silently changes the exemption
    surface."""
    expected_directories = frozenset(
        {"agents", "docs", "skills", "rules", "system-prompts", "commands"}
    )
    assert constants_module.ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES == expected_directories
    assert "ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES" in constants_module.__all__


def test_minimum_segment_count_to_match_indicator_is_four() -> None:
    """Matching `packages/claude-dev-env/<dir>/<file>` requires at least 4
    consecutive path segments from the starting index. The constant documents
    that requirement explicitly."""
    assert constants_module.MINIMUM_SEGMENT_COUNT_TO_MATCH_INDICATOR == 4
    assert "MINIMUM_SEGMENT_COUNT_TO_MATCH_INDICATOR" in constants_module.__all__


def test_exempt_anywhere_filenames_include_skill_md() -> None:
    """`SKILL.md` files are exempt anywhere in the tree. The constant stores
    the display-case spelling; the lookup at use sites lowercases the
    candidate basename, so casing here documents the human-facing form."""
    assert "SKILL.md" in constants_module.ALL_EXEMPT_ANYWHERE_FILENAMES
    assert "ALL_EXEMPT_ANYWHERE_FILENAMES" in constants_module.__all__


def test_exempt_plugin_directory_segments_match_claude_code_layout() -> None:
    """The three plugin-layout directory names recognized anywhere in a path:
    agents/, skills/, commands/. Drift in either direction silently changes
    the exemption surface."""
    expected_segments = ("agents", "skills", "commands")
    assert constants_module.ALL_EXEMPT_PLUGIN_DIRECTORY_SEGMENTS == expected_segments
    assert "ALL_EXEMPT_PLUGIN_DIRECTORY_SEGMENTS" in constants_module.__all__


def test_exempt_plugin_segments_subset_of_claude_code_source_top_directories() -> None:
    """ALL_EXEMPT_PLUGIN_DIRECTORY_SEGMENTS (matched anywhere in the path)
    must be a subset of ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES (matched
    only at the anchored claude-dev-env source root). If a future change
    adds a segment to the anywhere list that is not in the anchored set,
    the anywhere rule would let writes through that the anchored rule
    would still block — surprising and asymmetric."""
    anywhere_segments = set(constants_module.ALL_EXEMPT_PLUGIN_DIRECTORY_SEGMENTS)
    anchored_source_directories = set(
        constants_module.ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES
    )
    assert anywhere_segments.issubset(anchored_source_directories)


def test_exempt_home_relative_directories_include_session_log() -> None:
    """SessionLog/ under the user's home directory is the canonical Obsidian
    vault entrypoint and must be writable as .md."""
    assert "SessionLog" in constants_module.ALL_EXEMPT_HOME_RELATIVE_DIRECTORIES
    assert "ALL_EXEMPT_HOME_RELATIVE_DIRECTORIES" in constants_module.__all__


def test_exempt_root_filenames_cover_readme_changelog_claude_and_agents() -> None:
    """README.md, CHANGELOG.md, CLAUDE.md, and AGENTS.md at a repo root are
    universally exempt; every repo with a `.git` marker satisfies the root
    check. CLAUDE.md and AGENTS.md are functional agent-instruction files that
    Claude Code loads by name and must stay Markdown."""
    assert constants_module.ALL_EXEMPT_ROOT_FILENAMES == (
        "readme.md",
        "changelog.md",
        "claude.md",
        "agents.md",
    )
    assert "ALL_EXEMPT_ROOT_FILENAMES" in constants_module.__all__


def test_repo_root_marker_name_is_dot_git() -> None:
    """A directory containing `.git` (file or directory) is treated as a repo
    root for the README/CHANGELOG exemption."""
    assert constants_module.REPO_ROOT_MARKER_NAME == ".git"
    assert "REPO_ROOT_MARKER_NAME" in constants_module.__all__


def test_claude_directory_name_is_dot_claude() -> None:
    """Any path containing a `.claude/` segment bypasses the .md block
    (project-level Claude Code infrastructure)."""
    assert constants_module.CLAUDE_DIRECTORY_NAME == ".claude"
    assert "CLAUDE_DIRECTORY_NAME" in constants_module.__all__


def test_plugin_root_marker_directory_name_is_dot_claude_plugin() -> None:
    """Any directory whose ancestor contains `.claude-plugin/` is treated as
    a plugin repo root and exempted."""
    assert constants_module.PLUGIN_ROOT_MARKER_DIRECTORY_NAME == ".claude-plugin"
    assert "PLUGIN_ROOT_MARKER_DIRECTORY_NAME" in constants_module.__all__
