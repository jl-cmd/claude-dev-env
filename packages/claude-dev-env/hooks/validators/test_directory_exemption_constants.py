"""Tests for directory-exemption segment derivation.

Proves segment names come from authoritative path-exemption patterns and CLI
markers rather than hand-copied directory-name literals.
"""

from __future__ import annotations

from pathlib import Path

from hooks_constants.code_rules_enforcer_constants import ALL_CLI_FILE_PATH_MARKERS
from hooks_constants.code_rules_path_utils_constants import ALL_CONFIG_DIRECTORY_NAMES
from validators.config.directory_exemption_constants import (
    ALL_DIRECTORY_EXEMPTION_SEGMENT_NAMES,
    ALL_DIRECTORY_EXEMPTION_SUBSTRING_PATTERNS,
    ALL_DIRECTORY_SEGMENTS_FROM_PATH_PATTERNS,
    all_directory_segments_in_path_pattern,
    directory_segment_names_from_path_patterns,
    is_filename_like_path_segment,
    substring_patterns_from_path_patterns,
)
from validators.exempt_paths import (
    HOOK_INFRASTRUCTURE_PATTERNS,
    MIGRATION_PATH_PATTERNS,
    TEST_PATH_PATTERNS,
    WORKFLOW_REGISTRY_PATTERNS,
)
from validators.run_all_validators import _temporary_path_preserving_directory_signal

ALL_KNOWN_DIRECTORY_EXEMPTION_SEGMENTS = frozenset(
    {"scripts", "tests", "migrations", "workflow", "hooks"}
)
ALL_SYNTHETIC_DIRECTORY_PATTERNS = frozenset(
    {"/foo/", "\\bar\\", "/baz.py", "plain", "/.hidden/qux/"}
)
ALL_EXPECTED_SYNTHETIC_SEGMENTS = frozenset({"foo", "bar", ".hidden", "qux"})


def test_is_filename_like_path_segment_detects_extensions() -> None:
    assert is_filename_like_path_segment("states.py") is True
    assert is_filename_like_path_segment("cli.py") is True
    assert is_filename_like_path_segment("tests") is False
    assert is_filename_like_path_segment(".claude") is False


def test_all_directory_segments_in_path_pattern_keeps_directory_tokens_only() -> None:
    assert all_directory_segments_in_path_pattern("/.claude/hooks/") == [
        ".claude",
        "hooks",
    ]
    assert all_directory_segments_in_path_pattern("\\tests\\") == ["tests"]
    assert all_directory_segments_in_path_pattern("/tests.py") == []
    assert all_directory_segments_in_path_pattern("conftest") == []
    assert all_directory_segments_in_path_pattern("_tab.py") == []


def test_directory_segment_names_from_path_patterns_extracts_new_directory_token() -> None:
    all_segment_names = directory_segment_names_from_path_patterns(
        ALL_SYNTHETIC_DIRECTORY_PATTERNS
    )
    assert all_segment_names == ALL_EXPECTED_SYNTHETIC_SEGMENTS


def test_derived_segments_cover_authoritative_directory_patterns() -> None:
    all_authoritative_patterns = (
        set(TEST_PATH_PATTERNS)
        | set(WORKFLOW_REGISTRY_PATTERNS)
        | set(MIGRATION_PATH_PATTERNS)
        | set(HOOK_INFRASTRUCTURE_PATTERNS)
        | set(ALL_CLI_FILE_PATH_MARKERS)
    )
    all_expected_segments = directory_segment_names_from_path_patterns(
        all_authoritative_patterns
    )
    assert all_expected_segments == ALL_DIRECTORY_SEGMENTS_FROM_PATH_PATTERNS
    assert all_expected_segments <= ALL_DIRECTORY_EXEMPTION_SEGMENT_NAMES
    assert ALL_CONFIG_DIRECTORY_NAMES <= ALL_DIRECTORY_EXEMPTION_SEGMENT_NAMES
    assert ALL_KNOWN_DIRECTORY_EXEMPTION_SEGMENTS <= ALL_DIRECTORY_EXEMPTION_SEGMENT_NAMES


def test_temporary_path_preserves_scripts_directory_segment(tmp_path: Path) -> None:
    staged_path = _temporary_path_preserving_directory_signal(
        tmp_path, "packages/demo/scripts/run_job.py"
    )
    assert staged_path == tmp_path / "scripts" / "run_job.py"


def test_temporary_path_preserves_claude_hooks_parent_and_child(tmp_path: Path) -> None:
    staged_hooks_path = _temporary_path_preserving_directory_signal(
        tmp_path, "home/.claude/hooks/blocking/gate.py"
    )
    assert staged_hooks_path == (
        tmp_path / ".claude" / "hooks" / "blocking" / "gate.py"
    )


def test_temporary_path_preserves_tests_directory_segment(tmp_path: Path) -> None:
    staged_path = _temporary_path_preserving_directory_signal(
        tmp_path, "packages/demo/tests/helper_functions.py"
    )
    assert staged_path == tmp_path / "tests" / "helper_functions.py"


def test_substring_patterns_from_path_patterns_skips_directory_tokens() -> None:
    all_substring_patterns = substring_patterns_from_path_patterns(
        {"test_", "/tests/", "conftest", "\\tests\\"}
    )
    assert all_substring_patterns == frozenset({"test_", "conftest"})


def test_directory_exemption_substring_patterns_are_non_empty_and_separator_free() -> None:
    assert ALL_DIRECTORY_EXEMPTION_SUBSTRING_PATTERNS
    for each_pattern in ALL_DIRECTORY_EXEMPTION_SUBSTRING_PATTERNS:
        assert "/" not in each_pattern
        assert "\\" not in each_pattern


def test_directory_exemption_substring_patterns_include_test_fragments() -> None:
    assert "test_" in ALL_DIRECTORY_EXEMPTION_SUBSTRING_PATTERNS
    assert "conftest" in ALL_DIRECTORY_EXEMPTION_SUBSTRING_PATTERNS
