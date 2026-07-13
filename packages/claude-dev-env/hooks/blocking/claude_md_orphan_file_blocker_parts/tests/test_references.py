"""Tests for the CLAUDE.md reference-extraction parts module."""

from claude_md_orphan_file_blocker_parts.references import (
    find_referenced_filenames,
    find_run_command_filenames,
    is_claude_md_file,
)


def test_is_claude_md_file_matches_basename() -> None:
    assert is_claude_md_file("/pkg/CLAUDE.md") is True
    assert is_claude_md_file("/pkg/README.md") is False


def test_find_referenced_filenames_reads_table_cell() -> None:
    content = "# t\n\n| File | Note |\n|---|---|\n| `alpha.py` | a |\n"
    assert find_referenced_filenames(content) == ["alpha.py"]


def test_find_referenced_filenames_skips_fenced_table() -> None:
    content = "# t\n\n```\n| File | Note |\n|---|---|\n| `ghost.py` | a |\n```\n"
    assert find_referenced_filenames(content) == []


def test_find_referenced_filenames_skips_relative_path_block() -> None:
    content = "# t\n\nSourced from `../shared`:\n\n| File | Note |\n|---|---|\n| `alpha.py` | a |\n"
    assert find_referenced_filenames(content) == []


def test_find_run_command_filenames_reads_fenced_command() -> None:
    content = "# t\n\n```bash\npython tools/verify.py --flag\n```\n"
    assert find_run_command_filenames(content) == ["verify.py"]


def test_find_run_command_filenames_ignores_prose_command() -> None:
    content = "# t\n\nJust run python outside.py somewhere in prose.\n"
    assert find_run_command_filenames(content) == []


def test_find_run_command_filenames_drops_trailing_comment() -> None:
    content = "# t\n\n```bash\npython real.py  # was python old.py\n```\n"
    assert find_run_command_filenames(content) == ["real.py"]
