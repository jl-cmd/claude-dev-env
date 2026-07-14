"""Tests for the CLAUDE.md subtree-scan parts module."""

from pathlib import Path

from claude_md_orphan_file_blocker_parts.subtree_scan import find_missing_filenames


def test_find_missing_filenames_reports_absent_reference(tmp_path: Path) -> None:
    package_directory = tmp_path / "package"
    package_directory.mkdir()
    content = "# t\n\n| File | Note |\n|---|---|\n| `absent.py` | a |\n"
    assert find_missing_filenames(content, package_directory) == ["absent.py"]


def test_find_missing_filenames_allows_present_reference(tmp_path: Path) -> None:
    package_directory = tmp_path / "package"
    package_directory.mkdir()
    (package_directory / "present.py").write_text("x = 1\n", encoding="utf-8")
    content = "# t\n\n| File | Note |\n|---|---|\n| `present.py` | a |\n"
    assert find_missing_filenames(content, package_directory) == []


def test_find_missing_filenames_finds_sibling_under_parent(tmp_path: Path) -> None:
    package_directory = tmp_path / "package"
    package_directory.mkdir()
    sibling_directory = tmp_path / "sibling"
    sibling_directory.mkdir()
    (sibling_directory / "neighbor.py").write_text("x = 1\n", encoding="utf-8")
    content = "# t\n\n| File | Note |\n|---|---|\n| `neighbor.py` | a |\n"
    assert find_missing_filenames(content, package_directory) == []
