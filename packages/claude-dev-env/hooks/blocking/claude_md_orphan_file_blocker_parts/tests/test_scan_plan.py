"""Tests for the CLAUDE.md scan-plan parts module."""

from pathlib import Path

from claude_md_orphan_file_blocker_parts.scan_plan import (
    build_orphan_scan_plan,
    collect_missing_filenames,
)


def test_build_orphan_scan_plan_uses_write_content(tmp_path: Path) -> None:
    content = "# t\n\n| File | Note |\n|---|---|\n| `absent.py` | a |\n"
    scan_plan = build_orphan_scan_plan(
        "Write", {"content": content}, str(tmp_path / "CLAUDE.md"), tmp_path
    )
    assert scan_plan.candidate_contents == [content]
    assert scan_plan.baseline_missing_filenames == set()


def test_collect_missing_filenames_reports_write_orphan(tmp_path: Path) -> None:
    package_directory = tmp_path / "package"
    package_directory.mkdir()
    content = "# t\n\n| File | Note |\n|---|---|\n| `absent.py` | a |\n"
    scan_plan = build_orphan_scan_plan(
        "Write", {"content": content}, str(package_directory / "CLAUDE.md"), package_directory
    )
    assert collect_missing_filenames(scan_plan, package_directory) == ["absent.py"]
