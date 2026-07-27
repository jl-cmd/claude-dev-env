"""Behavioral tests for the added_line_maps parts module."""

import subprocess
from pathlib import Path
from unittest.mock import patch

from code_rules_gate_parts import added_line_maps, git_file_sets, violation_scoping


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


def test_added_lines_by_file_uses_pre_resolved_merge_base_without_resolve_call(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _base_repository(repository_root)
    base_sha = _head_sha(repository_root)
    fresh = repository_root / "fresh.py"
    fresh.write_text("x = 1\ny = 2\n", encoding="utf-8")
    _run(repository_root, "add", "-A")
    _run(repository_root, "commit", "-m", "add fresh")

    with patch.object(
        added_line_maps,
        "resolve_merge_base",
        side_effect=AssertionError("merge-base resolved again"),
    ) as mock_resolve_merge_base:
        added_by_path = added_line_maps.added_lines_by_file(
            repository_root,
            base_sha,
            [fresh],
            resolved_merge_base=base_sha,
        )

    assert added_by_path[fresh.resolve()] == {1, 2}
    mock_resolve_merge_base.assert_not_called()


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


def test_parse_combined_diff_added_line_map_splits_by_file_header() -> None:
    combined_diff_text = (
        "diff --git a/first.py b/first.py\n"
        "--- a/first.py\n"
        "+++ b/first.py\n"
        "@@ -1,0 +2 @@\n"
        "+second = 2\n"
        "diff --git a/second.py b/second.py\n"
        "--- a/second.py\n"
        "+++ b/second.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+alpha = 1\n"
        "+beta = 2\n"
    )

    added_by_relative_path = added_line_maps.parse_combined_diff_added_line_map(
        combined_diff_text
    )

    assert added_by_relative_path == {
        "first.py": {2},
        "second.py": {1, 2},
    }


def test_parse_combined_diff_added_line_map_handles_binary_stanza() -> None:
    combined_diff_text = (
        "diff --git a/payload.bin b/payload.bin\n"
        "new file mode 100644\n"
        "index 0000000..f971a5e\n"
        "Binary files /dev/null and b/payload.bin differ\n"
    )

    added_by_relative_path = added_line_maps.parse_combined_diff_added_line_map(
        combined_diff_text
    )

    assert added_by_relative_path == {"payload.bin": set()}


def test_parse_combined_diff_added_line_map_unquotes_core_quotepath_header() -> None:
    combined_diff_text = (
        'diff --git "a/\\303\\251.py" "b/\\303\\251.py"\n'
        "new file mode 100644\n"
        "index 0000000..281738e\n"
        "--- /dev/null\n"
        '+++ "b/\\303\\251.py"\n'
        "@@ -0,0 +1,2 @@\n"
        "+x = 1\n"
        "+\n"
    )

    added_by_relative_path = added_line_maps.parse_combined_diff_added_line_map(
        combined_diff_text
    )

    assert added_by_relative_path == {"é.py": {1, 2}}


def test_parse_combined_diff_added_line_map_keeps_space_path_from_plain_sibling() -> None:
    combined_diff_text = (
        "diff --git a/b.py b/b.py\n"
        "--- a/b.py\n"
        "+++ b/b.py\n"
        "@@ -0,0 +1 @@\n"
        "+one = 1\n"
        "diff --git a/z b.py b/z b.py\n"
        "--- a/z b.py\n"
        "+++ b/z b.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+two = 1\n"
        "+two = 2\n"
    )

    added_by_relative_path = added_line_maps.parse_combined_diff_added_line_map(
        combined_diff_text
    )

    assert added_by_relative_path == {
        "b.py": {1},
        "z b.py": {1, 2},
    }


def test_combined_added_line_map_staged_keeps_space_path_from_plain_sibling(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _base_repository(repository_root)
    plain_sibling_path = "b.py"
    space_path = "z b.py"
    (repository_root / plain_sibling_path).write_text("one = 1\n", encoding="utf-8")
    (repository_root / space_path).write_text("two = 1\ntwo = 2\n", encoding="utf-8")
    _run(repository_root, "add", plain_sibling_path, space_path)

    combined_map = added_line_maps.combined_added_line_map_staged(
        repository_root,
        [plain_sibling_path, space_path],
    )
    per_file_plain = violation_scoping.parse_added_line_numbers(
        git_file_sets.staged_unified_diff_text(repository_root, plain_sibling_path)
    )
    per_file_space = violation_scoping.parse_added_line_numbers(
        git_file_sets.staged_unified_diff_text(repository_root, space_path)
    )

    assert combined_map[plain_sibling_path] == per_file_plain == {1}
    assert combined_map[space_path] == per_file_space == {1, 2}


def test_combined_added_line_map_since_keeps_space_path_from_plain_sibling(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _base_repository(repository_root)
    plain_sibling_path = "b.py"
    space_path = "z b.py"
    (repository_root / plain_sibling_path).write_text("one = 0\n", encoding="utf-8")
    (repository_root / space_path).write_text("two = 0\n", encoding="utf-8")
    _run(repository_root, "add", plain_sibling_path, space_path)
    _run(repository_root, "commit", "-m", "add plain and space paths")
    base_sha = _head_sha(repository_root)
    (repository_root / plain_sibling_path).write_text(
        "one = 0\none = 1\n", encoding="utf-8"
    )
    (repository_root / space_path).write_text(
        "two = 0\ntwo = 1\ntwo = 2\n", encoding="utf-8"
    )
    _run(repository_root, "add", "-A")
    _run(repository_root, "commit", "-m", "edit plain and space paths")

    combined_map = added_line_maps.combined_added_line_map_since(
        repository_root, base_sha
    )
    per_file_plain = added_line_maps.added_lines_for_file(
        repository_root, base_sha, plain_sibling_path
    )
    per_file_space = added_line_maps.added_lines_for_file(
        repository_root, base_sha, space_path
    )

    assert combined_map[plain_sibling_path] == per_file_plain == {2}
    assert combined_map[space_path] == per_file_space == {2, 3}


def test_combined_added_line_map_since_matches_per_file_under_renames_true(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _base_repository(repository_root)
    (repository_root / "keep.py").write_text("keep = 1\n", encoding="utf-8")
    _run(repository_root, "add", "keep.py")
    _run(repository_root, "commit", "-m", "add keep")
    _run(repository_root, "config", "diff.renames", "true")
    base_sha = _head_sha(repository_root)
    _run(repository_root, "mv", "base.py", "moved.py")
    (repository_root / "moved.py").write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
    (repository_root / "keep.py").write_text("keep = 1\nextra = 2\n", encoding="utf-8")
    _run(repository_root, "add", "-A")
    _run(repository_root, "commit", "-m", "rename and edit")

    combined_map = added_line_maps.combined_added_line_map_since(
        repository_root, base_sha
    )
    per_file_map = {
        "moved.py": added_line_maps.added_lines_for_file(
            repository_root, base_sha, "moved.py"
        ),
        "keep.py": added_line_maps.added_lines_for_file(
            repository_root, base_sha, "keep.py"
        ),
    }

    assert combined_map["moved.py"] == per_file_map["moved.py"]
    assert combined_map["keep.py"] == per_file_map["keep.py"]
    assert combined_map["moved.py"] == {1, 2, 3}
    assert combined_map["keep.py"] == {2}


def test_combined_added_line_map_staged_matches_new_and_empty_files(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _base_repository(repository_root)
    (repository_root / "brand_new.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
    (repository_root / "empty_new.py").write_bytes(b"")
    _run(repository_root, "add", "brand_new.py", "empty_new.py")

    combined_map = added_line_maps.combined_added_line_map_staged(
        repository_root,
        ["brand_new.py", "empty_new.py"],
    )
    per_file_brand_new = violation_scoping.parse_added_line_numbers(
        git_file_sets.staged_unified_diff_text(repository_root, "brand_new.py")
    )
    per_file_empty = violation_scoping.parse_added_line_numbers(
        git_file_sets.staged_unified_diff_text(repository_root, "empty_new.py")
    )

    assert combined_map["brand_new.py"] == per_file_brand_new == {1, 2}
    assert combined_map["empty_new.py"] == per_file_empty == set()


def test_combined_added_line_map_staged_handles_binary_and_quoted_path(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _base_repository(repository_root)
    _run(repository_root, "config", "core.quotepath", "true")
    non_ascii_name = "é.py"
    (repository_root / non_ascii_name).write_text("x = 1\n", encoding="utf-8")
    (repository_root / "payload.bin").write_bytes(bytes([0, 1, 2, 255]))
    _run(repository_root, "add", non_ascii_name, "payload.bin")

    combined_map = added_line_maps.combined_added_line_map_staged(repository_root)

    assert combined_map[non_ascii_name] == {1}
    assert combined_map["payload.bin"] == set()


def test_added_lines_by_file_issues_one_combined_diff(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _base_repository(repository_root)
    first = repository_root / "first.py"
    second = repository_root / "second.py"
    first.write_text("a = 1\n", encoding="utf-8")
    second.write_text("b = 1\n", encoding="utf-8")
    _run(repository_root, "add", "-A")
    _run(repository_root, "commit", "-m", "two files")
    base_sha = _head_sha(repository_root)
    first.write_text("a = 1\na = 2\n", encoding="utf-8")
    second.write_text("b = 1\nb = 2\n", encoding="utf-8")
    _run(repository_root, "add", "-A")
    _run(repository_root, "commit", "-m", "edit both")

    original_git_text = added_line_maps._git_text_or_exit
    all_diff_commands: list[list[str]] = []

    def tracking_git_text(
        repository_root_argument: Path,
        all_git_arguments: list[str],
        failure_prefix: str,
    ) -> str:
        if (
            len(all_git_arguments) >= 3
            and all_git_arguments[0] == "git"
            and "diff" in all_git_arguments
            and "--unified=0" in all_git_arguments
        ):
            all_diff_commands.append(list(all_git_arguments))
        return original_git_text(
            repository_root_argument, all_git_arguments, failure_prefix
        )

    with patch.object(added_line_maps, "_git_text_or_exit", side_effect=tracking_git_text):
        added_by_path = added_line_maps.added_lines_by_file(
            repository_root, base_sha, [first, second], resolved_merge_base=base_sha
        )

    unified_zero_commands = [
        each_command
        for each_command in all_diff_commands
        if "--unified=0" in each_command and "--no-renames" in each_command
    ]
    assert len(unified_zero_commands) == 1
    assert added_by_path[first.resolve()] == {2}
    assert added_by_path[second.resolve()] == {2}


def test_combined_added_line_map_staged_overrides_diff_noprefix_true(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _base_repository(repository_root)
    _run(repository_root, "config", "diff.noprefix", "true")
    changed_path = "changed.py"
    (repository_root / changed_path).write_text("changed = 1\n", encoding="utf-8")
    _run(repository_root, "add", changed_path)

    combined_map = added_line_maps.combined_added_line_map_staged(
        repository_root,
        [changed_path],
    )
    per_file_changed = violation_scoping.parse_added_line_numbers(
        git_file_sets.staged_unified_diff_text(repository_root, changed_path)
    )

    assert combined_map[changed_path] == per_file_changed == {1}


def test_combined_added_line_map_staged_overrides_diff_mnemonic_prefix_true(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _base_repository(repository_root)
    _run(repository_root, "config", "diff.mnemonicPrefix", "true")
    changed_path = "changed.py"
    (repository_root / changed_path).write_text("changed = 1\n", encoding="utf-8")
    _run(repository_root, "add", changed_path)

    combined_map = added_line_maps.combined_added_line_map_staged(
        repository_root,
        [changed_path],
    )
    per_file_changed = violation_scoping.parse_added_line_numbers(
        git_file_sets.staged_unified_diff_text(repository_root, changed_path)
    )

    assert combined_map[changed_path] == per_file_changed == {1}


def test_combined_added_line_map_since_overrides_diff_noprefix_true(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _base_repository(repository_root)
    _run(repository_root, "config", "diff.noprefix", "true")
    changed_path = "changed.py"
    (repository_root / changed_path).write_text("changed = 0\n", encoding="utf-8")
    _run(repository_root, "add", changed_path)
    _run(repository_root, "commit", "-m", "add changed")
    base_sha = _head_sha(repository_root)
    (repository_root / changed_path).write_text(
        "changed = 0\nchanged = 1\n", encoding="utf-8"
    )
    _run(repository_root, "add", "-A")
    _run(repository_root, "commit", "-m", "edit changed")

    combined_map = added_line_maps.combined_added_line_map_since(
        repository_root, base_sha
    )
    per_file_changed = added_line_maps.added_lines_for_file(
        repository_root, base_sha, changed_path
    )

    assert combined_map[changed_path] == per_file_changed == {2}


def test_parse_combined_diff_added_line_map_keeps_quoted_space_and_non_ascii_path() -> None:
    combined_diff_text = (
        'diff --git "a/z \\303\\274.py" "b/z \\303\\274.py"\n'
        "new file mode 100644\n"
        "index 0000000..281738e\n"
        "--- /dev/null\n"
        '+++ "b/z \\303\\274.py"\n'
        "@@ -0,0 +1,2 @@\n"
        "+x = 1\n"
        "+y = 2\n"
    )

    added_by_relative_path = added_line_maps.parse_combined_diff_added_line_map(
        combined_diff_text
    )

    assert added_by_relative_path == {"z ü.py": {1, 2}}


def test_combined_added_line_map_staged_keeps_quoted_space_and_non_ascii_path(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _base_repository(repository_root)
    _run(repository_root, "config", "core.quotepath", "true")
    quoted_space_path = "z ü.py"
    (repository_root / quoted_space_path).write_text("x = 1\ny = 2\n", encoding="utf-8")
    _run(repository_root, "add", quoted_space_path)

    combined_map = added_line_maps.combined_added_line_map_staged(
        repository_root,
        [quoted_space_path],
    )
    per_file_quoted = violation_scoping.parse_added_line_numbers(
        git_file_sets.staged_unified_diff_text(repository_root, quoted_space_path)
    )

    assert combined_map[quoted_space_path] == per_file_quoted == {1, 2}


def test_parse_combined_diff_added_line_map_keeps_path_with_b_slash_substring() -> None:
    combined_diff_text = (
        "diff --git a/d b/e.py b/d b/e.py\n"
        "new file mode 100644\n"
        "index 0000000..281738e\n"
        "--- /dev/null\n"
        "+++ b/d b/e.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+x = 1\n"
        "+y = 2\n"
    )

    added_by_relative_path = added_line_maps.parse_combined_diff_added_line_map(
        combined_diff_text
    )

    assert added_by_relative_path == {"d b/e.py": {1, 2}}


def test_combined_added_line_map_staged_keeps_path_with_b_slash_substring(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _base_repository(repository_root)
    nested_directory = repository_root / "d b"
    nested_directory.mkdir()
    b_slash_path = "d b/e.py"
    (nested_directory / "e.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    _run(repository_root, "add", b_slash_path)

    combined_map = added_line_maps.combined_added_line_map_staged(
        repository_root,
        [b_slash_path],
    )
    per_file_nested = violation_scoping.parse_added_line_numbers(
        git_file_sets.staged_unified_diff_text(repository_root, b_slash_path)
    )

    assert combined_map[b_slash_path] == per_file_nested == {1, 2}
