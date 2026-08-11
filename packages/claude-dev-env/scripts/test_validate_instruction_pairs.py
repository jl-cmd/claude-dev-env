import subprocess
from pathlib import Path

from validate_instruction_pairs import validate_repository


def initialize_repository(repository_root: Path) -> None:
    subprocess.run(["git", "init", "--quiet"], cwd=repository_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "tests@example.com"],
        cwd=repository_root,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Instruction tests"],
        cwd=repository_root,
        check=True,
    )


def stage_instruction_files(repository_root: Path) -> None:
    subprocess.run(["git", "add", "AGENTS.md", "CLAUDE.md"], cwd=repository_root, check=True)


def test_exact_import_passes(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    (tmp_path / "AGENTS.md").write_bytes(b"# Canonical guidance\n")
    (tmp_path / "CLAUDE.md").write_bytes(b"@AGENTS.md\n")
    stage_instruction_files(tmp_path)

    assert validate_repository(tmp_path) == []


def test_claude_context_fails_exact_import_check(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    (tmp_path / "AGENTS.md").write_bytes(b"# Canonical guidance\n")
    (tmp_path / "CLAUDE.md").write_bytes(b"@AGENTS.md\n\nExtra context\n")
    stage_instruction_files(tmp_path)

    all_errors = validate_repository(tmp_path)

    assert any("exactly import" in each_error for each_error in all_errors)


def test_nearest_ancestor_import_passes(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    nested_directory = tmp_path / ".claude"
    nested_directory.mkdir()
    (tmp_path / "AGENTS.md").write_bytes(b"# Canonical guidance\n")
    (nested_directory / "CLAUDE.md").write_bytes(b"@../AGENTS.md\n")
    subprocess.run(["git", "add", "AGENTS.md", ".claude/CLAUDE.md"], cwd=tmp_path, check=True)

    assert validate_repository(tmp_path) == []


def test_crlf_import_fails_line_ending_check(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    (tmp_path / "AGENTS.md").write_bytes(b"# Canonical guidance\n")
    (tmp_path / "CLAUDE.md").write_bytes(b"@AGENTS.md\r\n")
    stage_instruction_files(tmp_path)

    all_errors = validate_repository(tmp_path)

    assert any("exactly import" in each_error for each_error in all_errors)


def test_executable_import_fails_git_mode_check(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    (tmp_path / "AGENTS.md").write_bytes(b"# Canonical guidance\n")
    (tmp_path / "CLAUDE.md").write_bytes(b"@AGENTS.md\n")
    stage_instruction_files(tmp_path)
    subprocess.run(
        ["git", "update-index", "--chmod=+x", "CLAUDE.md"],
        cwd=tmp_path,
        check=True,
    )

    all_errors = validate_repository(tmp_path)

    assert any("Git mode 100644" in each_error for each_error in all_errors)


def test_untracked_import_fails_tracking_check(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    (tmp_path / "AGENTS.md").write_bytes(b"# Canonical guidance\n")
    (tmp_path / "CLAUDE.md").write_bytes(b"@AGENTS.md\n")

    all_errors = validate_repository(tmp_path)

    assert any("Git mode 100644" in each_error for each_error in all_errors)
