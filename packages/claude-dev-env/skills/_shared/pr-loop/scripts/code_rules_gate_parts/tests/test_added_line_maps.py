"""Behavioral tests for the added_line_maps parts module."""

import subprocess
from pathlib import Path

from code_rules_gate_parts import added_line_maps, git_file_sets


def _run(repository_root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", *arguments],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
        env=git_file_sets.repository_environment(),
    )


def _base_repository(repository_root: Path) -> None:
    _run(repository_root, "init", "--initial-branch=main")
    _run(repository_root, "config", "user.email", "test@example.com")
    _run(repository_root, "config", "user.name", "Test")
    _run(repository_root, "config", "commit.gpgsign", "false")
    disabled_hooks = repository_root / "disabled-git-hooks"
    disabled_hooks.mkdir()
    _run(repository_root, "config", "core.hooksPath", str(disabled_hooks))
    (repository_root / "base.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
    _run(repository_root, "add", "-A")
    _run(repository_root, "commit", "-m", "base")


def _head_sha(repository_root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
        text=True,
        env=git_file_sets.repository_environment(),
    ).stdout.strip()


def test_whole_file_line_set_covers_every_line(tmp_path: Path) -> None:
    module_path = tmp_path / "three.py"
    module_path.write_text("a\nb\nc\n", encoding="utf-8")
    assert added_line_maps.whole_file_line_set(module_path) == {1, 2, 3}


def test_is_file_new_at_base_distinguishes_added_and_existing(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _base_repository(repository_root)
    base_sha = _head_sha(repository_root)
    (repository_root / "fresh.py").write_text("x = 1\n", encoding="utf-8")
    _run(repository_root, "add", "-A")
    _run(repository_root, "commit", "-m", "add fresh")

    assert added_line_maps.is_file_new_at_base(repository_root, base_sha, "fresh.py")
    assert not added_line_maps.is_file_new_at_base(repository_root, base_sha, "base.py")


def test_added_lines_for_file_reports_new_lines(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _base_repository(repository_root)
    base_sha = _head_sha(repository_root)
    (repository_root / "base.py").write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
    _run(repository_root, "add", "-A")
    _run(repository_root, "commit", "-m", "extend")

    added = added_line_maps.added_lines_for_file(repository_root, base_sha, "base.py")

    assert added == {3}


def test_renamed_file_source_map_since_maps_destination_to_source(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _base_repository(repository_root)
    base_sha = _head_sha(repository_root)
    _run(repository_root, "mv", "base.py", "moved.py")
    _run(repository_root, "commit", "-m", "rename")

    rename_map = added_line_maps.renamed_file_source_map_since(repository_root, base_sha)

    assert rename_map == {"moved.py": "base.py"}


def test_added_lines_by_file_marks_new_file_whole(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _base_repository(repository_root)
    base_sha = _head_sha(repository_root)
    fresh = repository_root / "fresh.py"
    fresh.write_text("x = 1\ny = 2\n", encoding="utf-8")
    _run(repository_root, "add", "-A")
    _run(repository_root, "commit", "-m", "add fresh")

    added_by_path = added_line_maps.added_lines_by_file(repository_root, base_sha, [fresh])

    assert added_by_path[fresh.resolve()] == {1, 2}


def test_added_lines_for_renamed_file_reports_only_new_lines(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _base_repository(repository_root)
    base_sha = _head_sha(repository_root)
    _run(repository_root, "mv", "base.py", "moved.py")
    (repository_root / "moved.py").write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
    _run(repository_root, "add", "-A")
    _run(repository_root, "commit", "-m", "rename and extend")

    added = added_line_maps.added_lines_for_renamed_file(
        repository_root, base_sha, "base.py", "moved.py"
    )

    assert added == {3}


def test_renamed_file_source_map_staged_maps_destination_to_source(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _base_repository(repository_root)
    _run(repository_root, "mv", "base.py", "moved.py")

    rename_map = added_line_maps.renamed_file_source_map_staged(repository_root)

    assert rename_map == {"moved.py": "base.py"}


def test_added_lines_for_staged_renamed_file_is_empty_on_pure_move(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _base_repository(repository_root)
    _run(repository_root, "mv", "base.py", "moved.py")

    added = added_line_maps.added_lines_for_staged_renamed_file(
        repository_root, "base.py", "moved.py"
    )

    assert added == set()


def test_added_lines_for_staged_renamed_file_reports_only_new_lines(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _base_repository(repository_root)
    _run(repository_root, "mv", "base.py", "moved.py")
    (repository_root / "moved.py").write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
    _run(repository_root, "add", "--", "moved.py")

    added = added_line_maps.added_lines_for_staged_renamed_file(
        repository_root, "base.py", "moved.py"
    )

    assert added == {3}
