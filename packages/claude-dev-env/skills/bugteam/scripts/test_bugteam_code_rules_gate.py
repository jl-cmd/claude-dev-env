from __future__ import annotations

import subprocess
import sys
import unittest.mock
from pathlib import Path
import pytest

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import bugteam_code_rules_gate as gate_module


def run_git_in_repository(repository_root: Path, *arguments: str) -> str:
    completion = subprocess.run(
        ["git", *arguments],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return completion.stdout


def initialize_git_repository(repository_root: Path) -> None:
    run_git_in_repository(repository_root, "init")
    run_git_in_repository(repository_root, "symbolic-ref", "HEAD", "refs/heads/main")
    run_git_in_repository(repository_root, "config", "user.email", "test@example.com")
    run_git_in_repository(repository_root, "config", "user.name", "Test")
    run_git_in_repository(repository_root, "config", "commit.gpgsign", "false")


def commit_all_files(repository_root: Path, commit_message: str) -> None:
    run_git_in_repository(repository_root, "add", "-A")
    run_git_in_repository(repository_root, "commit", "-m", commit_message)


def write_file(file_path: Path, content: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def stage_file(repository_root: Path, relative_path: str) -> None:
    run_git_in_repository(repository_root, "add", "--", relative_path)


@pytest.fixture()
def temporary_git_repository(tmp_path: Path) -> Path:
    repository_root = tmp_path / "repository_under_test"
    repository_root.mkdir()
    initialize_git_repository(repository_root)
    return repository_root


def test_paths_from_git_staged_returns_staged_files(
    temporary_git_repository: Path,
) -> None:
    write_file(temporary_git_repository / "committed_file.py", "one = 1\n")
    commit_all_files(temporary_git_repository, "initial")
    write_file(temporary_git_repository / "newly_staged_file.py", "two = 2\n")
    write_file(temporary_git_repository / "unstaged_file.py", "three = 3\n")
    stage_file(temporary_git_repository, "newly_staged_file.py")

    staged_paths = gate_module.paths_from_git_staged(temporary_git_repository)

    staged_names = {path.name for path in staged_paths}
    assert "newly_staged_file.py" in staged_names
    assert "unstaged_file.py" not in staged_names
    assert "committed_file.py" not in staged_names


def test_added_lines_for_staged_file_reports_new_lines(
    temporary_git_repository: Path,
) -> None:
    write_file(temporary_git_repository / "target.py", "first = 1\nsecond = 2\n")
    commit_all_files(temporary_git_repository, "baseline")
    write_file(
        temporary_git_repository / "target.py",
        "first = 1\nsecond = 2\nthird = 3\nfourth = 4\n",
    )
    stage_file(temporary_git_repository, "target.py")

    added_line_numbers = gate_module.added_lines_for_staged_file(
        temporary_git_repository,
        "target.py",
    )

    assert 3 in added_line_numbers
    assert 4 in added_line_numbers
    assert 1 not in added_line_numbers
    assert 2 not in added_line_numbers


def test_added_lines_for_staged_file_treats_new_file_as_fully_added(
    temporary_git_repository: Path,
) -> None:
    write_file(temporary_git_repository / "existing.py", "ignored = 0\n")
    commit_all_files(temporary_git_repository, "baseline")
    write_file(
        temporary_git_repository / "brand_new.py",
        "alpha = 1\nbeta = 2\ngamma = 3\n",
    )
    stage_file(temporary_git_repository, "brand_new.py")

    added_line_numbers = gate_module.added_lines_for_staged_file(
        temporary_git_repository,
        "brand_new.py",
    )

    assert added_line_numbers == {1, 2, 3}


def test_paths_from_git_staged_uses_null_delimiter(
    temporary_git_repository: Path,
) -> None:
    write_file(temporary_git_repository / "first.py", "a = 1\n")
    write_file(temporary_git_repository / "second.py", "b = 2\n")
    commit_all_files(temporary_git_repository, "baseline")
    write_file(temporary_git_repository / "first.py", "a = 10\n")
    write_file(temporary_git_repository / "second.py", "b = 20\n")
    stage_file(temporary_git_repository, "first.py")
    stage_file(temporary_git_repository, "second.py")

    staged_paths = gate_module.paths_from_git_staged(temporary_git_repository)

    staged_names = {path.name for path in staged_paths}
    assert staged_names == {"first.py", "second.py"}


def test_paths_from_git_staged_warns_and_skips_non_utf8_filename(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    non_utf8_raw = b"valid.py\x00\xff\xfe_bad.py\x00"
    mock_completed = unittest.mock.MagicMock()
    mock_completed.returncode = 0
    mock_completed.stdout = non_utf8_raw

    with unittest.mock.patch("subprocess.run", return_value=mock_completed):
        result_paths = gate_module.paths_from_git_staged(tmp_path)

    captured = capsys.readouterr()
    assert "non-UTF-8" in captured.err
    assert len(result_paths) == 1
    assert result_paths[0].name == "valid.py"


def test_staged_added_lines_by_file_maps_every_staged_code_file(
    temporary_git_repository: Path,
) -> None:
    write_file(temporary_git_repository / "already_committed.py", "zero = 0\n")
    commit_all_files(temporary_git_repository, "initial")
    write_file(
        temporary_git_repository / "already_committed.py",
        "zero = 0\nappended = 1\n",
    )
    write_file(temporary_git_repository / "added_file.py", "only = 1\n")
    stage_file(temporary_git_repository, "already_committed.py")
    stage_file(temporary_git_repository, "added_file.py")

    staged_paths = gate_module.paths_from_git_staged(temporary_git_repository)
    added_lines_map = gate_module.added_lines_by_file_staged(
        temporary_git_repository,
        staged_paths,
    )

    resolved_repository_root = temporary_git_repository.resolve()
    assert added_lines_map[resolved_repository_root / "already_committed.py"] == {2}
    assert added_lines_map[resolved_repository_root / "added_file.py"] == {1}


def test_main_staged_mode_blocks_when_staged_lines_introduce_violations(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_file(temporary_git_repository / "module.py", "first_value = 1\n")
    commit_all_files(temporary_git_repository, "initial")
    staged_content_with_banned_identifier = (
        "first_value = 1\n"
        "def compute_total(operand):\n"
        "    result = operand + 1\n"
        "    return result\n"
    )
    write_file(
        temporary_git_repository / "module.py",
        staged_content_with_banned_identifier,
    )
    stage_file(temporary_git_repository, "module.py")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 1


def test_main_staged_mode_passes_when_no_staged_violations(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_file(temporary_git_repository / "module.py", "first_value = 1\n")
    commit_all_files(temporary_git_repository, "initial")
    write_file(
        temporary_git_repository / "module.py", "first_value = 1\nsecond_value = 2\n"
    )
    stage_file(temporary_git_repository, "module.py")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 0


def test_main_staged_mode_exits_zero_when_nothing_staged(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_file(temporary_git_repository / "module.py", "first_value = 1\n")
    commit_all_files(temporary_git_repository, "initial")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 0


def test_added_lines_for_staged_file_returns_empty_for_modified_file_with_no_additions(
    temporary_git_repository: Path,
) -> None:
    write_file(
        temporary_git_repository / "existing.py",
        "alpha = 1\nbeta = 2\ngamma = 3\n",
    )
    commit_all_files(temporary_git_repository, "baseline")
    write_file(temporary_git_repository / "existing.py", "alpha = 1\nbeta = 2\n")
    stage_file(temporary_git_repository, "existing.py")

    added_line_numbers = gate_module.added_lines_for_staged_file(
        temporary_git_repository,
        "existing.py",
    )

    assert added_line_numbers == set()


def test_is_file_absent_in_index_head_does_not_exist_in_module() -> None:
    assert not hasattr(gate_module, "is_file_absent_in_index_head")


def test_staged_file_line_count_raises_on_git_show_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """git show failure must surface as SystemExit + stderr, never silent 0."""
    failing_completed = unittest.mock.MagicMock()
    failing_completed.returncode = 128
    failing_completed.stdout = ""
    failing_completed.stderr = "fatal: bad object :missing\n"
    with unittest.mock.patch("subprocess.run", return_value=failing_completed):
        with pytest.raises(SystemExit):
            gate_module.staged_file_line_count(tmp_path, "missing.py")
    captured = capsys.readouterr()
    assert "git show" in captured.err
    assert "fatal: bad object" in captured.err


def test_is_staged_file_newly_added_raises_on_git_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """git diff --name-status failure must surface as SystemExit + stderr."""
    failing_completed = unittest.mock.MagicMock()
    failing_completed.returncode = 128
    failing_completed.stdout = ""
    failing_completed.stderr = "fatal: not a git repository\n"
    with unittest.mock.patch("subprocess.run", return_value=failing_completed):
        with pytest.raises(SystemExit):
            gate_module.is_staged_file_newly_added(tmp_path, "anything.py")
    captured = capsys.readouterr()
    assert "git diff --cached --name-status" in captured.err


def test_whole_file_line_set_raises_system_exit_on_oserror(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """OSError reading a file must propagate as SystemExit, not silently return ``set()``.

    Regression for loop1-7: returning an empty set on OSError caused the gate
    to route every violation to the advisory bucket and exit 0 — silently
    downgrading blocking violations to non-blocking on a read failure.
    """
    unreadable_path = tmp_path / "broken.py"
    with unittest.mock.patch.object(
        Path, "read_text", side_effect=PermissionError("denied")
    ):
        with pytest.raises(SystemExit):
            gate_module.whole_file_line_set(unreadable_path)
    captured = capsys.readouterr()
    assert str(unreadable_path) in captured.err
    assert "denied" in captured.err or "PermissionError" in captured.err


def test_check_database_column_string_magic_signals_cap_exit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When the issue cap is hit, a 'cap reached' note must reach stderr."""
    source_with_many_column_tuples = "\n".join(
        [
            "def write_rows():",
            "    rows = [",
            *[
                f"        ('column_name_{each_index}', {each_index}),"
                for each_index in range(10)
            ],
            "    ]",
            "    return rows",
        ]
    )
    issues = gate_module.check_database_column_string_magic(
        source_with_many_column_tuples,
        "production/file.py",
    )
    assert len(issues) == 3
    captured = capsys.readouterr()
    assert "cap reached" in captured.err.lower()


def test_check_wrapper_plumb_through_signals_cap_exit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """check_wrapper_plumb_through must signal when MAXIMUM_ISSUES_TO_REPORT trims."""
    delegate_definition = (
        "def delegate(*, optional_one=1, optional_two=2, optional_three=3,"
        " optional_four=4): return 0\n"
    )
    wrappers_block = "\n".join(
        f"def wrapper_{each_index}():\n    return self.delegate()"
        for each_index in range(5)
    )
    source_with_many_wrappers = delegate_definition + wrappers_block + "\n"
    issues = gate_module.check_wrapper_plumb_through(
        source_with_many_wrappers,
        "production/wrappers.py",
    )
    assert len(issues) == 3
    captured = capsys.readouterr()
    assert "cap reached" in captured.err.lower()


def test_run_gate_exits_nonzero_when_a_file_is_unreadable(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Skipping an unreadable file during run_gate must cause a non-zero exit."""
    target_file = tmp_path / "sample.py"
    target_file.write_text("clean = 1\n", encoding="utf-8")

    def fake_validate(_content: str, _path: str, **_kwargs: object) -> list[str]:
        return []

    with unittest.mock.patch.object(
        Path, "read_text", side_effect=PermissionError("denied")
    ):
        exit_code = gate_module.run_gate(
            fake_validate,
            [target_file],
            tmp_path,
            all_added_lines_map=None,
        )
    captured = capsys.readouterr()
    assert exit_code != 0, (
        "Files skipped due to read errors must produce a non-zero gate exit"
    )
    assert "skip unreadable" in captured.err


def test_added_lines_for_staged_file_returns_parsed_result_when_diff_is_non_empty_even_if_parse_returns_empty(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_file(
        temporary_git_repository / "sample.py",
        "alpha = 1\nbeta = 2\n",
    )
    commit_all_files(temporary_git_repository, "baseline")
    write_file(temporary_git_repository / "sample.py", "alpha = 1\nbeta = 2\ngamma = 3\n")
    stage_file(temporary_git_repository, "sample.py")

    monkeypatch.setattr(gate_module, "parse_added_line_numbers", lambda _text: set())

    added_line_numbers = gate_module.added_lines_for_staged_file(
        temporary_git_repository,
        "sample.py",
    )

    assert added_line_numbers == set()
