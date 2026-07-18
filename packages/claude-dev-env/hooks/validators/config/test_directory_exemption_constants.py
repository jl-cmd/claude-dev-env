"""Tests for the derived directory-exemption segment set."""

from hooks_constants.code_rules_path_utils_constants import ALL_CONFIG_DIRECTORY_NAMES

from .directory_exemption_constants import ALL_DIRECTORY_EXEMPTION_SEGMENT_NAMES


def test_exemption_set_covers_every_config_directory_name() -> None:
    missing_names = ALL_CONFIG_DIRECTORY_NAMES - ALL_DIRECTORY_EXEMPTION_SEGMENT_NAMES
    assert missing_names == frozenset()


def test_exemption_set_covers_constants_package_directories() -> None:
    assert "hooks_constants" in ALL_DIRECTORY_EXEMPTION_SEGMENT_NAMES
    assert "pr_loop_shared_constants" in ALL_DIRECTORY_EXEMPTION_SEGMENT_NAMES
    assert "git_hooks_constants" in ALL_DIRECTORY_EXEMPTION_SEGMENT_NAMES


def test_exemption_set_keeps_path_marker_segments() -> None:
    for each_marker in ("scripts", "tests", "migrations", "workflow", "hooks"):
        assert each_marker in ALL_DIRECTORY_EXEMPTION_SEGMENT_NAMES
