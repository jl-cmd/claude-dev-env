from __future__ import annotations

import inspect
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
    disabled_hooks_directory = repository_root / "disabled-git-hooks"
    disabled_hooks_directory.mkdir()
    run_git_in_repository(
        repository_root, "config", "core.hooksPath", str(disabled_hooks_directory)
    )


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
    write_file(temporary_git_repository / "module.py", "first_count = 1\n")
    commit_all_files(temporary_git_repository, "initial")
    staged_content_with_banned_identifier = (
        "first_count = 1\n"
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
    write_file(temporary_git_repository / "module.py", "first_count = 1\n")
    commit_all_files(temporary_git_repository, "initial")
    write_file(
        temporary_git_repository / "module.py", "first_count = 1\nsecond_count = 2\n"
    )
    stage_file(temporary_git_repository, "module.py")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 0


def test_main_staged_mode_exits_zero_when_nothing_staged(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_file(temporary_git_repository / "module.py", "first_count = 1\n")
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


def test_whole_file_line_set_raises_system_exit_on_non_utf8_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A genuine non-UTF-8 file must fail closed as SystemExit, never crash.

    ``read_text(encoding="utf-8")`` on undecodable bytes raises
    UnicodeDecodeError, a ValueError subclass that ``OSError`` does not catch.
    The fail-closed contract that holds for read failures holds equally here:
    returning an empty set would route every violation to the advisory bucket,
    so an undecodable file must propagate as SystemExit rather than escape as
    an unhandled UnicodeDecodeError.
    """
    non_utf8_path = tmp_path / "garbled.py"
    non_utf8_path.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(SystemExit):
        gate_module.whole_file_line_set(non_utf8_path)
    captured = capsys.readouterr()
    assert str(non_utf8_path) in captured.err


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


def test_check_wrapper_plumb_through_caps_findings_at_max_per_check() -> None:
    """check_wrapper_plumb_through stops emitting at MAX_VIOLATIONS_PER_CHECK
    findings — the cap bounds the blocking payload silently, matching the
    _shared gate copy."""
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
    assert len(issues) == gate_module.MAX_VIOLATIONS_PER_CHECK


def _bugteam_banned_noun_parameter_issues() -> list[str]:
    validate_content = gate_module.load_validate_content()
    source = (
        "def aggregate(canned_results: int) -> int:\n"
        "    doubled = canned_results * 2\n"
        "    return doubled\n"
    )
    issues = validate_content(source, "src/module.py", "")
    return [each_issue for each_issue in issues if "banned noun" in each_issue]


def test_bugteam_split_violations_blocks_banned_noun_when_binding_line_is_added() -> None:
    """The bugteam gate reconstructs a banned-noun binding's one-line span the
    same way the _shared gate does: the violation is blocking when its own
    binding line is among the added lines."""
    banned_noun_issues = _bugteam_banned_noun_parameter_issues()
    assert banned_noun_issues, "expected a banned-noun parameter issue"
    parameter_binding_line = 1
    blocking, advisory = gate_module.split_violations_by_scope(
        banned_noun_issues,
        {parameter_binding_line},
    )
    assert blocking == banned_noun_issues
    assert advisory == []


def test_bugteam_split_violations_advises_banned_noun_when_binding_line_untouched() -> None:
    """A banned-noun binding whose own line is untouched is advisory at the
    bugteam gate, so editing an unrelated body line does not pull a pre-existing
    binding into scope."""
    banned_noun_issues = _bugteam_banned_noun_parameter_issues()
    assert banned_noun_issues, "expected a banned-noun parameter issue"
    unrelated_body_line = 2
    blocking, advisory = gate_module.split_violations_by_scope(
        banned_noun_issues,
        {unrelated_body_line},
    )
    assert advisory == banned_noun_issues
    assert blocking == []


def test_bugteam_banned_noun_span_range_covers_only_the_binding_line() -> None:
    """The reconstructed span is the binding line alone — one line, never the
    enclosing function span. A parameter declared on a ``def`` line yields a
    range covering only that line, so an unrelated body edit cannot pull the
    pre-existing binding into scope."""
    banned_noun_issues = _bugteam_banned_noun_parameter_issues()
    assert banned_noun_issues, "expected a banned-noun parameter issue"
    parameter_binding_line = 1
    span = gate_module.banned_noun_span_range(banned_noun_issues[0])
    assert span == range(parameter_binding_line, parameter_binding_line + 1)
    assert len(span) == 1


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


def test_run_gate_skips_non_utf8_file_without_crashing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A non-UTF-8 code file is skipped, not crashed on, and forces a non-zero exit."""
    non_utf8_file = tmp_path / "garbled.py"
    non_utf8_file.write_bytes(b"\xff\xfe\x00bad bytes")

    def fake_validate(_content: str, _path: str, **_kwargs: object) -> list[str]:
        return []

    exit_code = gate_module.run_gate(
        fake_validate,
        [non_utf8_file],
        tmp_path,
        all_added_lines_map=None,
    )

    captured = capsys.readouterr()
    assert exit_code != 0, (
        "A file skipped for non-UTF-8 content must produce a non-zero gate exit"
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


def _build_function_module(
    function_name: str, body_line_count: int, leading_lines: int
) -> str:
    preamble = "".join("anchor_name\n" for _ in range(leading_lines))
    body = "\n".join("    keep_alive_name" for _ in range(body_line_count))
    return f"{preamble}def {function_name}() -> None:\n{body}\n"


def test_split_violations_blocks_function_length_when_span_intersects_added_lines() -> None:
    """A function-length issue whose declared span overlaps the diff's added
    lines is blocking — the body grew, which is the regression intent."""
    validate_content = gate_module.load_validate_content()
    long_function = _build_function_module(
        "oversized", body_line_count=70, leading_lines=3
    )
    issues = validate_content(long_function, "src/long_module.py", "")
    function_length_issues = [
        each_issue for each_issue in issues if "blocking threshold" in each_issue
    ]
    assert function_length_issues, f"expected a function-length issue, got {issues!r}"
    span_def_line = 4
    inside_span_line = span_def_line + 10
    blocking, advisory = gate_module.split_violations_by_scope(
        function_length_issues,
        all_added_line_numbers={inside_span_line},
    )
    assert blocking == function_length_issues
    assert advisory == []


def test_split_violations_advises_function_length_when_span_misses_added_lines() -> None:
    """A function-length issue for an untouched pre-existing function — whose
    declared span does not overlap any added line — is advisory, not blocking.
    Prevents the over-block regression where every pre-existing long function
    in a touched file was forced into the blocking payload."""
    validate_content = gate_module.load_validate_content()
    long_function = _build_function_module(
        "oversized", body_line_count=70, leading_lines=3
    )
    issues = validate_content(long_function, "src/long_module.py", "")
    function_length_issues = [
        each_issue for each_issue in issues if "blocking threshold" in each_issue
    ]
    assert function_length_issues, f"expected a function-length issue, got {issues!r}"
    line_far_outside_span = 5000
    blocking, advisory = gate_module.split_violations_by_scope(
        function_length_issues,
        all_added_line_numbers={line_far_outside_span},
    )
    assert advisory == function_length_issues
    assert blocking == []


def _isolation_issues_for_home_probe_test() -> list[str]:
    validate_content = gate_module.load_validate_content()
    header = "from pathlib import Path\n"
    test_body = (
        "def test_reads_home() -> None:\n"
        "    target_path = Path.home()\n"
        "    assert target_path\n"
    )
    issues = validate_content(header + test_body, "src/test_module.py", "")
    return [each_issue for each_issue in issues if "probes" in each_issue]


def test_split_violations_blocks_isolation_when_function_span_intersects_added_lines() -> None:
    """An isolation issue whose enclosing test-function span overlaps the diff's
    added lines is blocking — a signature-line change that un-isolates an
    unchanged-body probe must block, matching the enforcer's terminal path."""
    isolation_issues = _isolation_issues_for_home_probe_test()
    assert isolation_issues, "expected an isolation issue from the HOME probe test"
    signature_line = 2
    blocking, advisory = gate_module.split_violations_by_scope(
        isolation_issues,
        all_added_line_numbers={signature_line},
    )
    assert blocking == isolation_issues
    assert advisory == []


def test_split_violations_advises_isolation_when_function_span_misses_added_lines() -> None:
    """An isolation issue for an untouched pre-existing probe — whose enclosing
    test-function span does not overlap any added line — is advisory, not
    blocking, mirroring the function-length scope contract."""
    isolation_issues = _isolation_issues_for_home_probe_test()
    assert isolation_issues, "expected an isolation issue from the HOME probe test"
    line_far_outside_span = 5000
    blocking, advisory = gate_module.split_violations_by_scope(
        isolation_issues,
        all_added_line_numbers={line_far_outside_span},
    )
    assert advisory == isolation_issues
    assert blocking == []


def _oversized_function_text(function_name: str) -> str:
    body = "\n".join("    keep_alive_name" for _ in range(70))
    return f"def {function_name}() -> None:\n{body}\n"


def _short_function_text(function_name: str) -> str:
    return f"def {function_name}() -> None:\n    keep_alive_name\n"


def test_main_blocks_sixth_long_function_on_added_lines_past_document_order(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bugbot-2: with five pre-existing untouched long functions ahead of it in
    document order, growing the sixth function past the threshold on staged
    lines must still block at the bugteam gate. The gate scopes by added lines,
    so the in-scope sixth violation blocks regardless of how many untouched
    ones precede it."""
    leading_long_functions = "".join(
        _oversized_function_text(f"leading_long_{each_index}")
        for each_index in range(5)
    )
    baseline = leading_long_functions + _short_function_text("target_function")
    write_file(temporary_git_repository / "module.py", baseline)
    commit_all_files(temporary_git_repository, "five long functions plus a short sixth")

    grown = leading_long_functions + _oversized_function_text("target_function")
    write_file(temporary_git_repository / "module.py", grown)
    stage_file(temporary_git_repository, "module.py")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 1, (
        "the sixth long function — the only one on staged lines — must block "
        "even though five untouched long functions precede it in document order"
    )


def _home_probe_test_text(test_name: str) -> str:
    return (
        f"def {test_name}() -> None:\n"
        "    target_path = Path.home()\n"
        "    assert target_path\n"
    )


def _clean_test_text(test_name: str) -> str:
    return f"def {test_name}() -> None:\n    assert 1 + 1 == 2\n"


def test_main_blocks_sixth_isolation_probe_on_added_lines_past_document_order(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """bugbot-2 mirror: with five pre-existing untouched HOME probes ahead of it
    in document order, adding a HOME probe to the sixth test on staged lines
    must still block at the bugteam gate. The gate scopes by added lines, so the
    in-scope sixth probe blocks regardless of how many untouched ones precede
    it."""
    header = "from pathlib import Path\n"
    leading_probe_tests = "".join(
        _home_probe_test_text(f"test_leading_probe_{each_index}")
        for each_index in range(5)
    )
    baseline = header + leading_probe_tests + _clean_test_text("test_target_probe")
    write_file(temporary_git_repository / "test_module.py", baseline)
    commit_all_files(temporary_git_repository, "five probe tests plus a clean sixth")

    grown = header + leading_probe_tests + _home_probe_test_text("test_target_probe")
    write_file(temporary_git_repository / "test_module.py", grown)
    stage_file(temporary_git_repository, "test_module.py")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 1, (
        "the sixth HOME probe — the only one on staged lines — must block even "
        "though five untouched probes precede it in document order"
    )


def _banned_noun_function_text(index: int) -> str:
    return (
        f"def leading_{index}(canned_results: int) -> int:\n"
        f"    return canned_results\n"
    )


def test_main_blocks_banned_noun_on_added_lines_past_document_order(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """loop7-P1: with three pre-existing untouched banned-noun identifiers ahead
    of it in document order, introducing a fourth banned-noun on a staged line
    must still block at the bugteam gate. The gate scopes by added lines, so the
    in-scope identifier blocks regardless of how many untouched ones precede
    it."""
    leading_count = 3
    leading_functions = "".join(
        _banned_noun_function_text(each_index) for each_index in range(leading_count)
    )
    baseline = leading_functions + "def placeholder() -> int:\n    return 0\n"
    write_file(temporary_git_repository / "module.py", baseline)
    commit_all_files(temporary_git_repository, "three banned nouns plus a clean function")

    grown = leading_functions + "def aggregate(holiday_result: int) -> int:\n    return holiday_result\n"
    write_file(temporary_git_repository / "module.py", grown)
    stage_file(temporary_git_repository, "module.py")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 1, (
        "the fourth banned-noun identifier — the only one on staged lines — must "
        "block even though three untouched ones precede it in document order"
    )


def test_report_partitioned_violations_returns_zero_when_clean(tmp_path: Path) -> None:
    """No blocking violations and no skipped files yields a zero exit code."""
    exit_code = gate_module._report_partitioned_violations(
        blocking_by_file={},
        advisory_by_file={tmp_path / "a.py": ["Line 1: advisory only"]},
        repository_root=tmp_path,
        is_whole_file_scope=False,
        skipped_unreadable_count=0,
    )
    assert exit_code == 0


def test_report_partitioned_violations_returns_one_on_blocking(tmp_path: Path) -> None:
    """A blocking violation yields a non-zero exit code."""
    exit_code = gate_module._report_partitioned_violations(
        blocking_by_file={tmp_path / "a.py": ["Line 1: blocking violation"]},
        advisory_by_file={},
        repository_root=tmp_path,
        is_whole_file_scope=False,
        skipped_unreadable_count=0,
    )
    assert exit_code == 1


def test_report_partitioned_violations_returns_one_when_file_skipped(tmp_path: Path) -> None:
    """A skipped unreadable file forces a non-zero exit even with no blocking
    violations, because the gate cannot vouch for the file it could not read."""
    exit_code = gate_module._report_partitioned_violations(
        blocking_by_file={},
        advisory_by_file={},
        repository_root=tmp_path,
        is_whole_file_scope=False,
        skipped_unreadable_count=1,
    )
    assert exit_code == 1


def test_check_wrapper_plumb_through_skips_class_methods_calling_module_delegate() -> None:
    """A class method calling a module-level delegate is not a wrapper; its
    signature is unrelated to the delegate's keyword surface, so it must not be
    flagged — matching the _shared gate copy."""
    source = (
        "def fetch(target, *, retries=3):\n"
        "    return target\n"
        "\n"
        "class MyService:\n"
        "    def public_method(self, target):\n"
        "        return fetch(target)\n"
    )
    issues = gate_module.check_wrapper_plumb_through(source, "module.py")
    assert issues == [], (
        f"class methods must not be treated as module-level wrappers; got {issues!r}"
    )


def test_check_wrapper_plumb_through_flags_name_call_dropping_kwarg() -> None:
    """A bare-name call (``delegate(value)``) to a same-file delegate that
    exposes an optional kwarg the public wrapper omits must be flagged — the
    bugteam copy must handle ``ast.Name`` targets, not only ``ast.Attribute``."""
    source = (
        "def delegate(value, *, retries=3):\n"
        "    return value\n"
        "\n"
        "def public_wrapper(value):\n"
        "    return delegate(value)\n"
    )
    issues = gate_module.check_wrapper_plumb_through(source, "module.py")
    assert any("retries" in each_issue for each_issue in issues), (
        f"a bare-name delegate call dropping an optional kwarg must flag; got {issues!r}"
    )


def test_check_wrapper_plumb_through_exempts_test_files() -> None:
    """A test_* function in a test-file path that calls a module-level helper
    exposing an optional kwarg is an ordinary pytest case, not a wrapper; the
    bugteam gate must exempt test files and emit zero findings."""
    source = (
        "def _helper(name, *, clean_name=None):\n"
        "    return (name, clean_name)\n"
        "\n"
        "def test_uses_helper():\n"
        "    return _helper('a', clean_name='b')\n"
    )
    issues = gate_module.check_wrapper_plumb_through(source, "pkg/test_thing.py")
    assert issues == [], (
        f"a wrapper shape in a test file must yield no findings; got {issues!r}"
    )


def test_check_wrapper_plumb_through_still_flags_non_test_path_with_test_shape() -> None:
    """The test-file exemption is scoped to test paths only; the same wrapper
    shape on a non-test path must still be flagged."""
    source = (
        "def _helper(name, *, clean_name=None):\n"
        "    return (name, clean_name)\n"
        "\n"
        "def test_uses_helper():\n"
        "    return _helper('a', clean_name='b')\n"
    )
    issues = gate_module.check_wrapper_plumb_through(source, "pkg/module.py")
    assert any(
        "test_uses_helper" in each_issue and "clean_name" in each_issue
        for each_issue in issues
    ), f"the same wrapper shape on a non-test path must still flag; got {issues!r}"


def test_check_wrapper_plumb_through_ignores_calls_nested_inside_delegate_arguments() -> None:
    """A callee nested as an argument (``delegate(helper(x))``) is not a
    separate call site; only the enclosing call is inspected, matching the
    _shared gate copy."""
    source = (
        "def delegate(value, *, retries=3):\n"
        "    return value\n"
        "\n"
        "def helper(value):\n"
        "    return value\n"
        "\n"
        "def public_caller(value):\n"
        "    return delegate(helper(value))\n"
    )
    issues = gate_module.check_wrapper_plumb_through(source, "module.py")
    assert all("helper" not in each_issue for each_issue in issues), (
        f"nested-argument callee must not be a separate call site; got {issues!r}"
    )


def test_main_staged_mode_blocks_newly_staged_inline_comment(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A NEWLY STAGED inline comment must be detected as a new comment in
    ``--staged`` mode. This proves the gate passes the HEAD-committed content as
    ``old_content`` to the comparison validators (the prior base), not the
    current working-tree content. When the current file content is reused as
    ``old_content``, ``check_comment_changes`` sees identical old/new text and
    misses the staged comment entirely, so the gate exits 0 — the regression."""
    write_file(
        temporary_git_repository / "module.py",
        'def describe_state() -> str:\n    return "ready"\n',
    )
    commit_all_files(temporary_git_repository, "initial without comment")
    staged_content_with_new_comment = (
        "def describe_state() -> str:\n"
        '    label = "ready"  # newly staged inline comment\n'
        "    return label\n"
    )
    write_file(
        temporary_git_repository / "module.py",
        staged_content_with_new_comment,
    )
    stage_file(temporary_git_repository, "module.py")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 1, (
        "a newly staged inline comment must block; if it does not, the gate is "
        "passing the current file content as old_content instead of the "
        "HEAD-committed prior base, so check_comment_changes sees identical "
        "old/new text and misses the staged comment"
    )


def test_check_wrapper_plumb_through_stays_under_function_length_threshold() -> None:
    """check_wrapper_plumb_through must stay under the enforcer's function-length
    blocking threshold so its signature-index, class-method-id, and per-wrapper
    finding logic live in extracted helpers, matching the _shared gate copy."""
    declared_line_count = len(
        inspect.getsource(gate_module.check_wrapper_plumb_through).splitlines()
    )
    blocking_threshold = 60
    assert declared_line_count < blocking_threshold, (
        f"check_wrapper_plumb_through is {declared_line_count} lines; extract "
        "helpers to keep it under the function-length blocking threshold"
    )


def test_read_prior_committed_content_returns_head_content_for_tracked_path(
    temporary_git_repository: Path,
) -> None:
    """A tracked path returns its HEAD-committed content, not the working copy."""
    committed_text = "alpha = 1\nbeta = 2\n"
    write_file(temporary_git_repository / "tracked.py", committed_text)
    commit_all_files(temporary_git_repository, "commit tracked file")
    write_file(
        temporary_git_repository / "tracked.py",
        committed_text + "gamma = 3\n",
    )

    prior_content = gate_module.read_prior_committed_content(
        temporary_git_repository.resolve(), "tracked.py"
    )

    assert prior_content == committed_text


def test_read_prior_committed_content_returns_empty_for_untracked_path(
    temporary_git_repository: Path,
) -> None:
    """An untracked path yields an empty string because git show returns non-zero."""
    write_file(temporary_git_repository / "anchor.py", "anchor = 1\n")
    commit_all_files(temporary_git_repository, "anchor commit")

    prior_content = gate_module.read_prior_committed_content(
        temporary_git_repository.resolve(), "never_committed.py"
    )

    assert prior_content == ""


def test_main_staged_mode_validates_staged_blob_not_working_tree(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Staged mode validates the staged blob, not the working tree.

    A blocking violation lives in the staged blob, but the working tree has
    been edited afterward to remove it. The gate must still block because it
    scopes added lines from the staged index and must read its content from
    the same staged source rather than the diverged working tree.
    """
    write_file(temporary_git_repository / "module.py", "first_count = 1\n")
    commit_all_files(temporary_git_repository, "initial")
    staged_content_with_banned_identifier = (
        "first_count = 1\n"
        "def compute_total(operand):\n"
        "    result = operand + 1\n"
        "    return result\n"
    )
    write_file(
        temporary_git_repository / "module.py",
        staged_content_with_banned_identifier,
    )
    stage_file(temporary_git_repository, "module.py")
    clean_working_tree_content = (
        "first_count = 1\n"
        "def compute_total(operand: int) -> int:\n"
        "    return operand + 1\n"
    )
    write_file(
        temporary_git_repository / "module.py",
        clean_working_tree_content,
    )

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 1, (
        "the staged blob carries a blocking violation; the gate must block "
        "even though the working tree was edited clean afterward"
    )


def test_main_staged_mode_blocks_when_staged_file_absent_from_working_tree(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A staged blocking violation must block even when the working tree file
    is gone. Staging a violating file and then deleting it from the working
    tree leaves the violation only in the staged blob; the gate must validate
    that blob rather than skip the path for failing a working-tree existence
    check."""
    write_file(temporary_git_repository / "baseline.py", "first_count = 1\n")
    commit_all_files(temporary_git_repository, "initial")
    staged_content_with_banned_identifier = (
        "def compute_total(operand):\n"
        "    result = operand + 1\n"
        "    return result\n"
    )
    write_file(
        temporary_git_repository / "module.py",
        staged_content_with_banned_identifier,
    )
    stage_file(temporary_git_repository, "module.py")
    (temporary_git_repository / "module.py").unlink()

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 1, (
        "the staged blob carries a blocking violation; the gate must block "
        "even though the file was deleted from the working tree after staging"
    )


def test_main_staged_mode_passes_on_staged_deletion_of_clean_file(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A staged deletion is not in the index, so its staged blob cannot be read.
    The gate must skip such a path cleanly rather than counting it as an
    unreadable file and failing closed. With no other staged violation, the
    gate must exit zero."""
    write_file(temporary_git_repository / "removable.py", "first_count = 1\n")
    commit_all_files(temporary_git_repository, "initial")
    run_git_in_repository(temporary_git_repository, "rm", "--", "removable.py")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 0, (
        "a staged deletion has no staged blob; the gate must skip it cleanly "
        "rather than fail closed as if the file were unreadable"
    )


_INLINE_DUPLICATE_MESSAGE = (
    "Function '_wait_for_render' duplicates an inline block in '_navigate_then_wait'"
    " — this function body is also present inline (Reuse before create / DRY) "
    "(inline duplicate body spans: helper at line 4 spanning 10 lines, "
    "enclosing at line 16 spanning 11 lines)"
)


def test_inline_duplicate_body_span_lines_unions_helper_and_enclosing_spans() -> None:
    """The same-file inline-duplicate message carries both spans, and the gate
    recovers their union as a line-number set so a touch of either function blocks —
    mirroring the live Write/Edit hook's union scoping."""
    span_lines = gate_module.inline_duplicate_body_span_lines(_INLINE_DUPLICATE_MESSAGE)
    assert span_lines == frozenset(range(4, 14)) | frozenset(range(16, 27))


def test_inline_duplicate_blocks_when_only_enclosing_copy_added() -> None:
    """An added line in the enclosing span alone blocks, because the live hook scopes
    by the union of both spans and blocks the same edit — the common shape where a
    block is copied INTO a growing enclosing function, leaving the helper untouched."""
    added_line_in_enclosing_only = 18
    blocking, advisory = gate_module.split_violations_by_scope(
        [_INLINE_DUPLICATE_MESSAGE],
        all_added_line_numbers={added_line_in_enclosing_only},
    )
    assert blocking == [_INLINE_DUPLICATE_MESSAGE]
    assert advisory == []


def test_inline_duplicate_advises_when_gap_line_added() -> None:
    """An edit confined to the gap between the helper span (4-13) and the enclosing
    span (16-26) must not block, matching the live hook. The union set keeps the gap
    out of scope where a single contiguous range would wrongly block it."""
    gap_line_between_spans = 14
    blocking, advisory = gate_module.split_violations_by_scope(
        [_INLINE_DUPLICATE_MESSAGE],
        all_added_line_numbers={gap_line_between_spans},
    )
    assert advisory == [_INLINE_DUPLICATE_MESSAGE]
    assert blocking == []
