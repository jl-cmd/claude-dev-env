"""Behavioral tests for the git_file_sets parts module."""

import subprocess
from pathlib import Path
from unittest.mock import patch

from code_rules_gate_parts import git_file_sets


def _init_repository(repository_root: Path) -> None:
    def run(*arguments: str) -> None:
        subprocess.run(
            ["git", *arguments],
            cwd=str(repository_root),
            check=True,
            capture_output=True,
            env=git_file_sets.repository_environment(),
        )

    run("init", "--initial-branch=main")
    run("config", "user.email", "test@example.com")
    run("config", "user.name", "Test")
    run("config", "commit.gpgsign", "false")
    (repository_root / "seed.txt").write_text("seed\n", encoding="utf-8")
    run("add", "-A")
    run("commit", "-m", "seed")


def test_paths_from_git_untracked_lists_only_untracked(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_repository(repository_root)
    (repository_root / "fresh.py").write_text("value = 1\n", encoding="utf-8")

    resolved_paths = git_file_sets.paths_from_git_untracked(repository_root)

    resolved_names = {each_path.name for each_path in resolved_paths}
    assert "fresh.py" in resolved_names
    assert "seed.txt" not in resolved_names


def test_paths_from_git_staged_lists_the_staged_file(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_repository(repository_root)
    (repository_root / "staged_module.py").write_text("value = 2\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "staged_module.py"],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
        env=git_file_sets.repository_environment(),
    )

    resolved_names = {
        each_path.name for each_path in git_file_sets.paths_from_git_staged(repository_root)
    }

    assert "staged_module.py" in resolved_names


def test_filter_paths_under_prefixes_keeps_only_matching_prefix(tmp_path: Path) -> None:
    kept = tmp_path / "keep" / "module.py"
    dropped = tmp_path / "other" / "module.py"
    kept.parent.mkdir(parents=True)
    dropped.parent.mkdir(parents=True)
    kept.write_text("value = 3\n", encoding="utf-8")
    dropped.write_text("value = 4\n", encoding="utf-8")

    filtered = git_file_sets.filter_paths_under_prefixes([kept, dropped], tmp_path, ["keep"])

    assert filtered == [kept]


def _staged_repository_with(repository_root: Path, filename: str, content: str) -> None:
    _init_repository(repository_root)
    (repository_root / filename).write_text(content, encoding="utf-8")
    subprocess.run(
        ["git", "add", filename],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
        env=git_file_sets.repository_environment(),
    )


def test_resolve_merge_base_of_head_with_itself_is_head_sha(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_repository(repository_root)

    merge_base = git_file_sets.resolve_merge_base(repository_root, "HEAD")

    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
        text=True,
        env=git_file_sets.repository_environment(),
    ).stdout.strip()
    assert merge_base == head_sha


def test_paths_from_git_diff_is_empty_when_head_matches_base(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_repository(repository_root)

    changed_paths = git_file_sets.paths_from_git_diff(repository_root, "HEAD")

    assert changed_paths == []


def test_paths_from_git_diff_uses_pre_resolved_merge_base_without_resolve_call(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_repository(repository_root)
    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
        text=True,
        env=git_file_sets.repository_environment(),
    ).stdout.strip()

    with patch.object(
        git_file_sets,
        "resolve_merge_base",
        side_effect=AssertionError("merge-base resolved again"),
    ) as mock_resolve_merge_base:
        changed_paths = git_file_sets.paths_from_git_diff(
            repository_root,
            "HEAD",
            resolved_merge_base=head_sha,
        )

    assert changed_paths == []
    mock_resolve_merge_base.assert_not_called()


def test_is_staged_file_newly_added_true_for_new_staged_file(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _staged_repository_with(repository_root, "added.py", "value = 5\n")

    assert git_file_sets.is_staged_file_newly_added(repository_root, "added.py")


def test_staged_file_line_count_reports_blob_line_count(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _staged_repository_with(repository_root, "three.py", "a = 1\nb = 2\nc = 3\n")

    assert git_file_sets.staged_file_line_count(repository_root, "three.py") == 3


def test_staged_unified_diff_text_carries_hunk_header(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _staged_repository_with(repository_root, "hunk.py", "a = 1\n")

    diff_text = git_file_sets.staged_unified_diff_text(repository_root, "hunk.py")

    assert "@@" in diff_text
