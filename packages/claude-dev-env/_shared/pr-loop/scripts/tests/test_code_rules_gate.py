"""Tests for shared code_rules_gate.py extracted from skills/bugteam/scripts/.

Covers:
- Module loads from _shared/pr-loop/scripts/ location
- resolve_claude_dev_env_root walks up to find code_rules_enforcer.py
- Path-resolution remains correct in both source layout and ~/.claude install layout
- Behavioral parity with the bugteam source: staged paths, added line maps, gate exit codes
"""

import importlib.util
import inspect
import subprocess
import sys
import unittest.mock
from pathlib import Path
from types import ModuleType

import pytest


def _load_gate_module() -> ModuleType:
    module_path = Path(__file__).parent.parent / "code_rules_gate.py"
    spec = importlib.util.spec_from_file_location("code_rules_gate", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate_module = _load_gate_module()


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
    run_git_in_repository(repository_root, "init", "--initial-branch=main")
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


def test_resolve_claude_dev_env_root_walks_up_to_find_enforcer(tmp_path: Path) -> None:
    fake_root = tmp_path / "fake_claude"
    enforcer_path = fake_root / "hooks" / "blocking" / "code_rules_enforcer.py"
    enforcer_path.parent.mkdir(parents=True)
    enforcer_path.write_text("# fake enforcer\n", encoding="utf-8")
    deep_script = fake_root / "_shared" / "pr-loop" / "scripts" / "code_rules_gate.py"
    deep_script.parent.mkdir(parents=True)
    deep_script.write_text("# stub\n", encoding="utf-8")

    resolved_root = gate_module.resolve_claude_dev_env_root(deep_script)

    assert resolved_root == fake_root.resolve()


def test_resolve_claude_dev_env_root_supports_legacy_skills_layout(
    tmp_path: Path,
) -> None:
    fake_root = tmp_path / "fake_dev_env"
    enforcer_path = fake_root / "hooks" / "blocking" / "code_rules_enforcer.py"
    enforcer_path.parent.mkdir(parents=True)
    enforcer_path.write_text("# fake enforcer\n", encoding="utf-8")
    legacy_script = fake_root / "skills" / "bugteam" / "scripts" / "code_rules_gate.py"
    legacy_script.parent.mkdir(parents=True)
    legacy_script.write_text("# stub\n", encoding="utf-8")

    resolved_root = gate_module.resolve_claude_dev_env_root(legacy_script)

    assert resolved_root == fake_root.resolve()


def test_resolve_claude_dev_env_root_raises_when_enforcer_missing(
    tmp_path: Path,
) -> None:
    deep_script = tmp_path / "_shared" / "pr-loop" / "scripts" / "code_rules_gate.py"
    deep_script.parent.mkdir(parents=True)
    deep_script.write_text("# stub\n", encoding="utf-8")

    with pytest.raises(SystemExit):
        gate_module.resolve_claude_dev_env_root(deep_script)


def test_resolve_claude_dev_env_root_from_module_path_finds_real_enforcer() -> None:
    module_path = Path(gate_module.__file__).resolve()
    resolved_root = gate_module.resolve_claude_dev_env_root(module_path)
    expected_enforcer = resolved_root / "hooks" / "blocking" / "code_rules_enforcer.py"
    assert expected_enforcer.is_file()


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


def test_added_lines_for_staged_file_returns_parsed_result_when_diff_is_non_empty_even_if_parse_returns_empty(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_file(
        temporary_git_repository / "sample.py",
        "alpha = 1\nbeta = 2\n",
    )
    commit_all_files(temporary_git_repository, "baseline")
    write_file(
        temporary_git_repository / "sample.py", "alpha = 1\nbeta = 2\ngamma = 3\n"
    )
    stage_file(temporary_git_repository, "sample.py")

    monkeypatch.setattr(gate_module, "parse_added_line_numbers", lambda _text: set())

    added_line_numbers = gate_module.added_lines_for_staged_file(
        temporary_git_repository,
        "sample.py",
    )

    assert added_line_numbers == set()


def test_staged_file_line_count_escalates_on_git_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    failing_completed = unittest.mock.MagicMock()
    failing_completed.returncode = 128
    failing_completed.stdout = ""
    failing_completed.stderr = "fatal: bad object HEAD"

    with unittest.mock.patch("subprocess.run", return_value=failing_completed):
        with pytest.raises(SystemExit) as exit_info:
            gate_module.staged_file_line_count(tmp_path, "missing.py")

    assert exit_info.value.code == 2
    captured = capsys.readouterr()
    assert "fatal: bad object HEAD" in captured.err


def test_is_staged_file_newly_added_escalates_on_git_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    failing_completed = unittest.mock.MagicMock()
    failing_completed.returncode = 128
    failing_completed.stdout = ""
    failing_completed.stderr = "fatal: not a git repository"

    with unittest.mock.patch("subprocess.run", return_value=failing_completed):
        with pytest.raises(SystemExit) as exit_info:
            gate_module.is_staged_file_newly_added(tmp_path, "missing.py")

    assert exit_info.value.code == 2
    captured = capsys.readouterr()
    assert "fatal: not a git repository" in captured.err


def test_check_wrapper_plumb_through_flags_direct_same_file_call() -> None:
    source = (
        "def fetch(target, *, retries=3):\n"
        "    return target\n"
        "\n"
        "def public_fetch(target):\n"
        "    return fetch(target)\n"
    )
    issues = gate_module.check_wrapper_plumb_through(source, "module.py")
    assert any(
        "public_fetch" in each_issue and "retries" in each_issue
        for each_issue in issues
    ), (
        "Direct same-file call (ast.Name) must be detected as a wrapper that "
        "drops optional kwargs of its delegate"
    )


def test_check_wrapper_plumb_through_still_flags_attribute_call() -> None:
    source = (
        "def fetch(target, *, retries=3):\n"
        "    return target\n"
        "\n"
        "def public_fetch(target):\n"
        "    return self.fetch(target)\n"
    )
    issues = gate_module.check_wrapper_plumb_through(source, "module.py")
    assert any(
        "public_fetch" in each_issue and "retries" in each_issue
        for each_issue in issues
    )


def test_split_violations_by_scope_accepts_all_added_line_numbers_param_name() -> None:
    blocking_issues, advisory_issues = gate_module.split_violations_by_scope(
        ["Line 5: violation"],
        all_added_line_numbers={5},
    )
    assert blocking_issues == ["Line 5: violation"]
    assert advisory_issues == []


def test_run_gate_accepts_all_added_lines_by_path_param_name(tmp_path: Path) -> None:
    gate_module.run_gate(
        validate_content=lambda _content, _path, **_kwargs: [],
        all_file_paths=[],
        repository_root=tmp_path,
        all_added_lines_by_path=None,
    )


def test_whole_file_line_set_handles_non_cp1252_utf8(tmp_path: Path) -> None:
    utf8_only_path = tmp_path / "utf8_only.py"
    cp1252_invalid_codepoint = chr(0x81)
    utf8_only_path.write_bytes(
        f"control = '{cp1252_invalid_codepoint}'\nname = 'café'\n".encode("utf-8")
    )

    line_numbers = gate_module.whole_file_line_set(utf8_only_path)

    assert line_numbers == {1, 2}


def test_run_gate_detects_new_inline_comment_in_touched_file(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: run_gate must pass prior file content as old_content.

    When old_content is incorrectly set to the new content, check_comment_changes
    reads identical sets and never flags a newly added inline comment. This test
    proves run_gate now reads the prior content from HEAD so newly added inline
    comments in touched files surface as violations.
    """
    write_file(
        temporary_git_repository / "module.py",
        "first_value = 1\nsecond_value = 2\n",
    )
    commit_all_files(temporary_git_repository, "initial")
    write_file(
        temporary_git_repository / "module.py",
        "first_value = 1\nsecond_value = 2  # added inline comment\n",
    )
    stage_file(temporary_git_repository, "module.py")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 1


def test_run_gate_treats_new_files_prior_content_as_empty(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_file(temporary_git_repository / "existing.py", "alpha = 1\n")
    commit_all_files(temporary_git_repository, "baseline")
    write_file(
        temporary_git_repository / "brand_new.py",
        "first_value = 1\nsecond_value = 2  # comment in new file\n",
    )
    stage_file(temporary_git_repository, "brand_new.py")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 1


def test_is_test_path_helper_matches_code_rules_patterns() -> None:
    assert gate_module.is_test_path("packages/foo/test_bar.py")
    assert gate_module.is_test_path("packages/foo/bar_test.py")
    assert gate_module.is_test_path("packages/foo/bar.test.ts")
    assert gate_module.is_test_path("packages/foo/bar.spec.js")
    assert gate_module.is_test_path("packages/foo/conftest.py")
    assert gate_module.is_test_path("packages/foo/tests/something.py")
    assert not gate_module.is_test_path("packages/foo/regular_module.py")


def test_validate_content_callable_signature_is_explicit() -> None:
    callable_alias_source = inspect.getsource(gate_module).split("\n")
    matching_lines = [
        each_line
        for each_line in callable_alias_source
        if "ValidateContentCallable" in each_line and "Callable[" in each_line
    ]
    assert any("[str, str, str]" in each_line for each_line in matching_lines)


def test_run_gate_uses_each_path_loop_variable() -> None:
    run_gate_source = inspect.getsource(gate_module.run_gate)
    assert "for each_path in" in run_gate_source


def test_run_gate_skips_non_utf8_source_without_crashing(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: run_gate must skip files that fail UTF-8 decoding.

    UnicodeDecodeError is a ValueError subclass, not OSError. A non-UTF-8
    source file in the staged set must be skipped (matching whole_file_line_set
    behavior), not crash the gate mid-audit.
    """
    write_file(temporary_git_repository / "anchor.py", "anchor = 1\n")
    commit_all_files(temporary_git_repository, "baseline")
    non_utf8_path = temporary_git_repository / "non_utf8.py"
    non_utf8_path.parent.mkdir(parents=True, exist_ok=True)
    non_utf8_path.write_bytes(b"name = '\xff\xfe invalid utf8 bytes'\n")
    stage_file(temporary_git_repository, "non_utf8.py")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code in {0, 1}


def test_check_wrapper_plumb_through_accepts_positional_or_keyword_forwarder() -> None:
    """Regression: positional-or-keyword forwarders with defaults must not be flagged.

    When a wrapper exposes the delegate's optional kwarg as a positional-or-keyword
    parameter with a default value and forwards it correctly, the check must produce
    zero findings. This mirrors the live gh_util.fetch_inline_review_comments →
    run_gh signature pairing on this PR.
    """
    source = (
        "def run_gh(all_command, *, timeout_seconds=30):\n"
        "    return all_command\n"
        "\n"
        "def fetch_inline_review_comments(owner, repo, pull_number, "
        "timeout_seconds=30):\n"
        "    return run_gh(['gh'], timeout_seconds=timeout_seconds)\n"
    )
    issues = gate_module.check_wrapper_plumb_through(source, "module.py")
    assert issues == []


def test_check_database_column_string_magic_dedupes_nested_function_tuples() -> None:
    """Regression: tuples inside nested FunctionDefs must produce one finding, not many.

    The outer ast.walk previously enumerated every FunctionDef including nested
    ones, then the inner ast.walk(each_node) walked the full subtree, so a tuple
    inside a nested function was visited via every enclosing function. This must
    surface exactly one finding per tuple site.
    """
    source = (
        "def outer():\n"
        "    def inner():\n"
        '        x = ("some_column_name", 42)\n'
        "        return x\n"
        "    return inner\n"
    )
    issues = gate_module.check_database_column_string_magic(source, "module.py")
    assert len(issues) == 1, f"expected 1 finding, got {len(issues)}: {issues!r}"


def test_check_wrapper_plumb_through_skips_uppercase_js_extension() -> None:
    """Regression: case-insensitive filesystem (Windows, macOS) can yield
    file paths like 'Foo.JS'. The skip predicate must normalize case so
    files matching the non-Python extension set are skipped and never
    fed to the Python AST analyzer.
    """
    valid_python_with_wrapper_violation = (
        "def fetch(target, *, retries=3):\n"
        "    return target\n"
        "\n"
        "def public_fetch(target):\n"
        "    return fetch(target)\n"
    )
    issues_for_uppercase_js = gate_module.check_wrapper_plumb_through(
        valid_python_with_wrapper_violation, "Foo.JS"
    )
    issues_for_lowercase_js = gate_module.check_wrapper_plumb_through(
        valid_python_with_wrapper_violation, "foo.js"
    )
    assert issues_for_uppercase_js == issues_for_lowercase_js
    assert issues_for_uppercase_js == []


def test_paths_from_git_diff_uses_null_delimiter(
    tmp_path: Path,
) -> None:
    """Regression: paths_from_git_diff must use -z + null-byte split.

    Mirrors paths_from_git_staged semantics so filenames containing newlines
    or special characters are not silently mangled.
    """
    null_terminated_stdout = b"first.py\x00second.py\x00name with\nnewline.py\x00"
    mock_completed_run = unittest.mock.MagicMock()
    mock_completed_run.returncode = 0
    mock_completed_run.stdout = null_terminated_stdout

    with unittest.mock.patch.object(
        gate_module, "resolve_merge_base", return_value="abcdef0"
    ):
        with unittest.mock.patch("subprocess.run", return_value=mock_completed_run) as mocked_run:
            resolved_paths = gate_module.paths_from_git_diff(tmp_path, "origin/main")

    invocation_arguments = mocked_run.call_args.args[0]
    assert "-z" in invocation_arguments

    resolved_names = {each_path.name for each_path in resolved_paths}
    assert "first.py" in resolved_names
    assert "second.py" in resolved_names
    assert "name with\nnewline.py" in resolved_names


def test_check_wrapper_plumb_through_dedupes_nested_public_function_calls() -> None:
    """Regression: delegate calls inside nested public functions must produce one finding.

    Same nested-walk pathology as the column-magic check: a delegate call inside
    a nested public function was flagged once for the inner FunctionDef and again
    for any enclosing public FunctionDef. Apply consistent de-dup strategy.
    """
    source = (
        "def fetch(target, *, retries=3):\n"
        "    return target\n"
        "\n"
        "def public_outer():\n"
        "    def public_inner():\n"
        "        return fetch(target=None)\n"
        "    return public_inner\n"
    )
    issues = gate_module.check_wrapper_plumb_through(source, "module.py")
    assert len(issues) == 1, f"expected 1 finding, got {len(issues)}: {issues!r}"




def test_check_wrapper_plumb_through_ignores_calls_nested_inside_delegate_arguments() -> None:
    """Regression: nested callees inside another call's arguments are not wrapper sites.

    Cursor Bugbot: `_iter_calls_excluding_nested_functions`
    used to recurse into `ast.Call` children, so `delegate(helper(x))` yielded
    both the outer `delegate` call and the inner `helper` call. The inner call
    must not attribute dropped optional kwargs of `helper` to the enclosing
    public function when `helper` is only a sub-expression argument.
    """
    source = (
        "def helper(x, *, opt=1):\n"
        "    return x\n"
        "\n"
        "def delegate(a):\n"
        "    return a\n"
        "\n"
        "def public_outer():\n"
        "    return delegate(helper(1))\n"
    )
    issues = gate_module.check_wrapper_plumb_through(source, "module.py")
    assert issues == [], (
        "nested helper inside delegate arguments must not false-flag the outer "
        f"public function; got {issues!r}"
    )


def test_check_wrapper_plumb_through_ignores_calls_in_nested_functions() -> None:
    """Calls inside a nested FunctionDef must not be attributed to the outer function.

    The outer public function does not call the delegate itself; only its
    private nested helper does. Because the nested call lives in a separate
    lexical scope, the outer must NOT be flagged for missing kwargs the inner
    drops. Walking the outer with ast.walk would incorrectly descend into the
    nested body and produce a false positive against the outer.
    """
    source = (
        "def fetch(target, *, retries=3):\n"
        "    return target\n"
        "\n"
        "def public_outer(target):\n"
        "    def _inner_helper():\n"
        "        return fetch(target)\n"
        "    return _inner_helper()\n"
    )
    issues = gate_module.check_wrapper_plumb_through(source, "module.py")
    assert issues == [], (
        f"outer must not be flagged for kwargs dropped by a nested helper; got {issues!r}"
    )


def test_check_wrapper_plumb_through_ignores_class_method_signatures() -> None:
    """Regression: methods sharing a name across classes must not collide.

    `function_signatures` previously keyed on `each_node.name` regardless of
    enclosing class, so `Foo.serialize(*, indent=2)` and `Bar.serialize(target)`
    both became dict entry `"serialize"` and the second overwrote the first.
    A module-level wrapper that calls `serialize(...)` was then incorrectly
    matched against whichever class won the race. Restrict signature
    collection to module-level functions so cross-class same-name methods
    cannot pollute the wrapper-detection index.
    """
    source = (
        "class Foo:\n"
        "    def serialize(self, target, *, indent=2):\n"
        "        return target\n"
        "\n"
        "class Bar:\n"
        "    def serialize(self, target):\n"
        "        return target\n"
        "\n"
        "def public_serialize(target):\n"
        "    return serialize(target)\n"
    )
    issues = gate_module.check_wrapper_plumb_through(source, "module.py")
    assert issues == [], (
        f"class-method same-name collision must not pollute the signature index; got {issues!r}"
    )


def test_added_lines_by_file_does_not_flag_pure_rename_as_whole_file_added(
    temporary_git_repository: Path,
) -> None:
    """Regression: a file renamed without content edits must not appear as
    a whole-file add. `git diff --unified=0 base..HEAD -- <newpath>` returns
    an empty diff for the new path, and the absent-at-base check would
    misclassify the renamed file as new and flag every line.
    """
    write_file(
        temporary_git_repository / "original_name.py",
        "alpha = 1\nbeta = 2\ngamma = 3\n",
    )
    commit_all_files(temporary_git_repository, "baseline")
    run_git_in_repository(
        temporary_git_repository,
        "mv",
        "original_name.py",
        "new_name.py",
    )
    commit_all_files(temporary_git_repository, "rename only")

    renamed_path = temporary_git_repository / "new_name.py"
    added_lines_map = gate_module.added_lines_by_file(
        temporary_git_repository,
        "HEAD~1",
        [renamed_path],
    )
    assert added_lines_map[renamed_path.resolve()] == set()


def test_renamed_file_source_map_since_maps_destination_to_source(
    temporary_git_repository: Path,
) -> None:
    """renamed_file_source_map_since returns dest->source dict for renamed files."""
    write_file(
        temporary_git_repository / "source_file.py",
        "x = 1\n",
    )
    commit_all_files(temporary_git_repository, "baseline")
    run_git_in_repository(
        temporary_git_repository,
        "mv",
        "source_file.py",
        "dest_file.py",
    )
    commit_all_files(temporary_git_repository, "rename")

    merge_base = gate_module.resolve_merge_base(temporary_git_repository, "HEAD~1")
    rename_map = gate_module.renamed_file_source_map_since(
        temporary_git_repository.resolve(), merge_base
    )
    assert rename_map == {"dest_file.py": "source_file.py"}


def test_added_lines_for_renamed_file_returns_empty_for_pure_rename(
    temporary_git_repository: Path,
) -> None:
    """Blob comparison of a pure rename yields zero added lines."""
    write_file(
        temporary_git_repository / "old.py",
        "a = 1\nb = 2\n",
    )
    commit_all_files(temporary_git_repository, "baseline")
    run_git_in_repository(temporary_git_repository, "mv", "old.py", "new.py")
    commit_all_files(temporary_git_repository, "rename")

    merge_base = gate_module.resolve_merge_base(temporary_git_repository, "HEAD~1")
    added = gate_module.added_lines_for_renamed_file(
        temporary_git_repository.resolve(), merge_base, "old.py", "new.py"
    )
    assert added == set()


def test_added_lines_for_renamed_file_returns_empty_when_git_diff_fails(
    temporary_git_repository: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: transient git diff failure must not treat the file as all-new lines."""
    write_file(
        temporary_git_repository / "old.py",
        "a = 1\nb = 2\n",
    )
    commit_all_files(temporary_git_repository, "baseline")
    run_git_in_repository(temporary_git_repository, "mv", "old.py", "new.py")
    commit_all_files(temporary_git_repository, "rename")
    merge_base = gate_module.resolve_merge_base(temporary_git_repository, "HEAD~1")

    failing = subprocess.CompletedProcess(
        args=["git", "diff"],
        returncode=1,
        stdout="",
        stderr="simulated git failure\n",
    )
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: failing)

    added = gate_module.added_lines_for_renamed_file(
        temporary_git_repository.resolve(), merge_base, "old.py", "new.py"
    )
    assert added == set()
    err = capsys.readouterr().err
    assert "simulated git failure" in err.lower()


def test_whole_file_line_set_logs_decode_failure_to_stderr(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Regression: silent UnicodeDecodeError swallow loses scope.

    A non-UTF-8 newly-added file would return an empty set with no signal
    to the operator. The function must emit a stderr line naming the file
    and the decode error so the operator knows scope was lost.
    """
    non_utf8_path = tmp_path / "non_utf8.py"
    non_utf8_path.write_bytes(b"name = '\xff\xfe invalid utf8 bytes'\n")

    line_numbers = gate_module.whole_file_line_set(non_utf8_path)

    assert line_numbers == set()
    captured = capsys.readouterr()
    assert "non_utf8.py" in captured.err
    assert "decode" in captured.err.lower() or "utf" in captured.err.lower()


def test_check_wrapper_plumb_through_skips_class_methods_calling_module_delegate() -> None:
    """Regression: class methods must not be wrongly flagged as wrappers.

    Wrapper detection walked every FunctionDef including methods inside a
    ClassDef body, but the signature index only contained module-level
    functions. A class method calling a module-level delegate with optional
    kwargs received an empty wrapper_kwargs set and was flagged as dropping
    the delegate's optional kwargs even though the class method's signature
    is unrelated to wrapper-style forwarding. Class methods must be ignored
    by wrapper-candidate enumeration.
    """
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


def test_renamed_file_source_map_since_uses_null_byte_separator(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: rename parsing must invoke git diff with -z.

    `git diff --name-status -M` without -z separates columns with tab and
    rows with newline. Filenames containing a literal tab or newline byte
    break column detection and silently misclassify the rename. The -z
    flag asks git for null-terminated, unquoted output so embedded tabs
    and newlines round-trip correctly. This test asserts the function
    invokes git with -z and parses the null-terminated stream emitted by
    that flag.
    """
    captured_arguments: dict[str, list[str]] = {}

    null_terminated_stream = (
        "R100\x00source_with\ttab.py\x00destination_with\ttab.py\x00"
    ).encode("utf-8")

    class _FakeCompletedProcess:
        returncode = 0
        stdout = null_terminated_stream
        stderr = b""

    def _fake_subprocess_run(all_command, **_keyword_arguments):
        captured_arguments["all_command"] = list(all_command)
        return _FakeCompletedProcess()

    monkeypatch.setattr(gate_module.subprocess, "run", _fake_subprocess_run)

    rename_map = gate_module.renamed_file_source_map_since(
        temporary_git_repository.resolve(), "deadbeef"
    )

    assert "-z" in captured_arguments["all_command"], (
        "git diff --name-status -M must include -z so embedded tabs/newlines "
        "in filenames are not misparsed as column or row separators"
    )
    assert rename_map == {
        "destination_with\ttab.py": "source_with\ttab.py",
    }
