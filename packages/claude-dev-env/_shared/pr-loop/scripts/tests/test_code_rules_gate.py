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
from collections.abc import Callable
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


def _load_duplicate_body_module() -> ModuleType:
    package_root = gate_module.resolve_claude_dev_env_root(
        Path(gate_module.__file__).resolve()
    )
    module_path = package_root / "hooks" / "blocking" / "code_rules_duplicate_body.py"
    spec = importlib.util.spec_from_file_location("code_rules_duplicate_body", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_duplicate_body_module = _load_duplicate_body_module()
check_duplicate_function_body_across_files = (
    _duplicate_body_module.check_duplicate_function_body_across_files
)
check_same_file_inline_duplicate_body = (
    _duplicate_body_module.check_same_file_inline_duplicate_body
)


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


def test_check_wrapper_plumb_through_exempts_test_files() -> None:
    source = (
        "def _helper(name, *, clean_name=None):\n"
        "    return (name, clean_name)\n"
        "\n"
        "def test_uses_helper():\n"
        "    return _helper('a', clean_name='b')\n"
    )
    shared_issues = gate_module.check_wrapper_plumb_through(source, "pkg/test_thing.py")
    bugteam_gate = _load_bugteam_gate_module()
    bugteam_issues = bugteam_gate.check_wrapper_plumb_through(source, "pkg/test_thing.py")
    assert shared_issues == [], (
        "a test_* function in a test-file path that calls a module-level helper "
        "exposing an optional kwarg is not a wrapper; the shared gate must exempt "
        "test files and emit zero findings"
    )
    assert bugteam_issues == [], (
        "the bugteam gate copy must apply the identical test-file exemption"
    )


def test_check_wrapper_plumb_through_still_flags_non_test_path_with_test_shape() -> None:
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
    ), (
        "the test-file exemption is scoped to test paths only; the same wrapper "
        "shape on a non-test path must still be flagged"
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
        "first_count = 1\nsecond_count = 2\n",
    )
    commit_all_files(temporary_git_repository, "initial")
    write_file(
        temporary_git_repository / "module.py",
        "first_count = 1\nsecond_count = 2  # added inline comment\n",
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
        "first_count = 1\nsecond_count = 2  # comment in new file\n",
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


def test_gate_defers_scope_to_the_gate() -> None:
    """The gate owns scope classification, so its per-file validation must call
    validate_content with ``defer_scope_to_caller=True``. Without that flag the
    enforcer scopes function-length, isolation, and banned-noun violations
    itself rather than returning them for the gate to classify by added line."""
    per_file_source = inspect.getsource(gate_module._scoped_violations_for_file)
    assert "defer_scope_to_caller=True" in per_file_source


def test_collect_partitioned_violations_returns_empty_maps_for_two_clean_files(
    temporary_git_repository: Path,
) -> None:
    """Two readable, violation-free files yield empty partitions and no skips."""
    first_clean = temporary_git_repository / "first_clean.py"
    second_clean = temporary_git_repository / "second_clean.py"
    first_clean.write_text("first_count = 1\n", encoding="utf-8")
    second_clean.write_text("second_count = 2\n", encoding="utf-8")

    def fake_validate(_content: str, _path: str, _prior: str = "", **_kwargs: object) -> list[str]:
        return []

    blocking_by_file, advisory_by_file, skipped_unreadable_count = (
        gate_module._collect_partitioned_violations(
            fake_validate,
            [first_clean, second_clean],
            temporary_git_repository,
            None,
        )
    )

    assert blocking_by_file == {}
    assert advisory_by_file == {}
    assert skipped_unreadable_count == 0


def test_collect_partitioned_violations_counts_unreadable_sibling_as_skip(
    temporary_git_repository: Path,
) -> None:
    """A clean file beside an unreadable file yields one skip and no violations."""
    clean_file = temporary_git_repository / "clean.py"
    clean_file.write_text("clean_count = 1\n", encoding="utf-8")
    unreadable_file = temporary_git_repository / "garbled.py"
    unreadable_file.write_bytes(b"\xff\xfe\x00bad")

    def fake_validate(_content: str, _path: str, _prior: str = "", **_kwargs: object) -> list[str]:
        return []

    blocking_by_file, advisory_by_file, skipped_unreadable_count = (
        gate_module._collect_partitioned_violations(
            fake_validate,
            [clean_file, unreadable_file],
            temporary_git_repository,
            None,
        )
    )

    assert blocking_by_file == {}
    assert advisory_by_file == {}
    assert skipped_unreadable_count == 1


_DUPLICATE_HELPER_SOURCE = (
    "import re\n"
    "\n"
    "def strip_code_and_quotes(text: str) -> str:\n"
    '    """Strip fences, inline code, and quoted lines from text.\n'
    "\n"
    "    Args:\n"
    "        text: The raw text to clean.\n"
    "\n"
    "    Returns:\n"
    "        The cleaned text.\n"
    '    """\n'
    "    without_fences = re.sub(r'```.*?```', '', text, flags=re.DOTALL)\n"
    "    without_inline = re.sub(r'`[^`]*`', '', without_fences)\n"
    "    without_quotes = re.sub(r'(?m)^>.*$', '', without_inline)\n"
    "    return without_quotes.strip()\n"
)


def test_run_gate_flags_copied_sibling_when_cwd_is_outside_repo_root(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The duplicate-body sibling scan must anchor to the repo, not process CWD.

    The duplicate-body check reads sibling modules from disk to flag a copied
    helper. When the gate runs with a working directory above the repository
    root, resolving the sibling directory against the process CWD points at the
    wrong place and the copied helper slips through. Driving the gate's per-file
    validation from a parent directory with a nested byte-identical sibling
    proves sibling resolution is anchored to the absolute file location rather
    than the inherited CWD — the duplicate message must appear in the blocking
    set.
    """
    package_directory = temporary_git_repository / "package"
    package_directory.mkdir()
    existing_file = package_directory / "existing_helper.py"
    copied_file = package_directory / "copied_helper.py"
    existing_file.write_text(_DUPLICATE_HELPER_SOURCE, encoding="utf-8")
    copied_file.write_text(_DUPLICATE_HELPER_SOURCE, encoding="utf-8")
    validate_content = gate_module.load_validate_content()

    monkeypatch.chdir(temporary_git_repository.parent)
    blocking_by_file, _advisory_by_file, _skipped = (
        gate_module._collect_partitioned_violations(
            validate_content,
            [copied_file],
            temporary_git_repository,
            None,
        )
    )

    all_blocking_messages = [
        each_message
        for each_file_messages in blocking_by_file.values()
        for each_message in each_file_messages
    ]
    assert any(
        "duplicates existing_helper.py" in each_message
        for each_message in all_blocking_messages
    ), (
        "A copied sibling helper must be flagged even when the gate runs from a "
        f"CWD above the repository root, got: {all_blocking_messages}"
    )


def _duplicate_body_issue_for_copied_sibling(base_directory: Path) -> str:
    """Return the enforcer's duplicate-body message for a copied sibling helper.

    Writes the shared helper into a ``blocking`` subdirectory of *base_directory*
    as an existing module, then validates a second module carrying the
    byte-identical body with scope deferred to the caller, so the returned message
    is exactly the one the commit/push gate re-scopes. The destination is passed as
    a neutral relative path with the sibling directory supplied explicitly, because
    any test marker anywhere in the path exempts the file from the duplicate scan
    and a pytest temporary directory carries one. The single duplicate-body
    violation is returned for span assertions.

    Args:
        base_directory: A directory under which the sibling module directory is
            created.

    Returns:
        The duplicate-body violation string the enforcer emits for the copy.
    """
    sibling_directory = base_directory / "blocking"
    sibling_directory.mkdir()
    (sibling_directory / "existing_helper.py").write_text(
        _DUPLICATE_HELPER_SOURCE, encoding="utf-8"
    )
    duplicate_body_issues = check_duplicate_function_body_across_files(
        _DUPLICATE_HELPER_SOURCE,
        "blocking/copied_helper.py",
        defer_scope_to_caller=True,
        sibling_directory=sibling_directory,
    )
    matching_issues = [
        each_issue
        for each_issue in duplicate_body_issues
        if "duplicates existing_helper.py" in each_issue
    ]
    assert matching_issues, f"expected a duplicate-body issue, got {duplicate_body_issues!r}"
    return matching_issues[0]


def test_duplicate_body_span_range_covers_the_definition_through_last_body_line(
    tmp_path: Path,
) -> None:
    """The reconstructed span starts at the copied function's definition line and
    covers its full body, so a changed-line set intersects the span only when the
    edit touches the duplicated function — mirroring the enforcer's own span."""
    duplicate_body_issue = _duplicate_body_issue_for_copied_sibling(tmp_path)
    definition_line = 3
    last_body_line = 15
    span = gate_module.duplicate_body_span_range(duplicate_body_issue)
    assert span == range(definition_line, last_body_line + 1)


def test_split_violations_blocks_duplicate_body_when_span_intersects_added_lines(
    tmp_path: Path,
) -> None:
    """A duplicate-body issue whose copied-function span overlaps the diff's added
    lines is blocking — this commit introduced or touched the copy, exactly the
    case the live Write/Edit hook flags."""
    duplicate_body_issue = _duplicate_body_issue_for_copied_sibling(tmp_path)
    inside_span_line = 4
    blocking, advisory = gate_module.split_violations_by_scope(
        [duplicate_body_issue],
        all_added_line_numbers={inside_span_line},
    )
    assert blocking == [duplicate_body_issue]
    assert advisory == []


def test_split_violations_advises_duplicate_body_when_span_misses_added_lines(
    tmp_path: Path,
) -> None:
    """A duplicate-body issue for an untouched pre-existing copy — whose span does
    not overlap any added line — is advisory, not blocking. Editing an unrelated
    region of a file that already carries a sibling-duplicate helper must not
    block the commit gate, matching the span-scoped Write/Edit behavior."""
    duplicate_body_issue = _duplicate_body_issue_for_copied_sibling(tmp_path)
    line_far_outside_span = 5000
    blocking, advisory = gate_module.split_violations_by_scope(
        [duplicate_body_issue],
        all_added_line_numbers={line_far_outside_span},
    )
    assert advisory == [duplicate_body_issue]
    assert blocking == []


_INLINE_DUPLICATE_MESSAGE_HELPER_FIRST = (
    "Function '_wait_for_render' duplicates an inline block in '_navigate_then_wait'"
    " — this function body is also present inline (Reuse before create / DRY) "
    "(inline duplicate body spans: helper at line 4 spanning 10 lines, "
    "enclosing at line 16 spanning 11 lines)"
)


def test_inline_duplicate_body_span_lines_unions_helper_and_enclosing_spans() -> None:
    """The same-file inline-duplicate message carries both spans, and the gate
    recovers their union as a line-number set so a touch of either function blocks —
    mirroring the live Write/Edit hook's union scoping."""
    span_lines = gate_module.inline_duplicate_body_span_lines(
        _INLINE_DUPLICATE_MESSAGE_HELPER_FIRST
    )
    assert span_lines == frozenset(range(4, 14)) | frozenset(range(16, 27))


def test_inline_duplicate_body_span_lines_returns_none_for_other_messages() -> None:
    """A cross-file duplicate-body message carries the single-span suffix, which the
    inline-duplicate extractor must not claim — so the gate routes it to the
    single-range extractor registry instead."""
    cross_file_message = (
        "Function 'strip' duplicates existing_helper.py::strip — extract a shared "
        "helper (duplicate body span at line 3, spanning 5 lines)"
    )
    assert gate_module.inline_duplicate_body_span_lines(cross_file_message) is None


def test_inline_duplicate_blocks_when_only_enclosing_copy_added() -> None:
    """The finding's real-world shape: the helper pre-exists (untouched) and a copy
    is added INTO a growing enclosing function. An added line in the enclosing span
    alone must block, because the live Write/Edit hook scopes by the union of both
    spans and blocks the same edit."""
    added_line_in_enclosing_only = 18
    blocking, advisory = gate_module.split_violations_by_scope(
        [_INLINE_DUPLICATE_MESSAGE_HELPER_FIRST],
        all_added_line_numbers={added_line_in_enclosing_only},
    )
    assert blocking == [_INLINE_DUPLICATE_MESSAGE_HELPER_FIRST]
    assert advisory == []


def test_inline_duplicate_blocks_when_only_helper_copy_added() -> None:
    """The mirror case: an edit touching only the helper span blocks too, since the
    union covers both functions."""
    added_line_in_helper_only = 5
    blocking, advisory = gate_module.split_violations_by_scope(
        [_INLINE_DUPLICATE_MESSAGE_HELPER_FIRST],
        all_added_line_numbers={added_line_in_helper_only},
    )
    assert blocking == [_INLINE_DUPLICATE_MESSAGE_HELPER_FIRST]
    assert advisory == []


def test_inline_duplicate_advises_when_gap_line_added() -> None:
    """An edit confined to an unrelated function that sits strictly between the
    helper (lines 4-13) and the enclosing copy (lines 16-26) — line 14, in the gap —
    must not block, matching the live hook that leaves such an edit unflagged. A
    single contiguous range over both spans would wrongly block this; the union set
    keeps the gap out of scope."""
    gap_line_between_spans = 14
    blocking, advisory = gate_module.split_violations_by_scope(
        [_INLINE_DUPLICATE_MESSAGE_HELPER_FIRST],
        all_added_line_numbers={gap_line_between_spans},
    )
    assert advisory == [_INLINE_DUPLICATE_MESSAGE_HELPER_FIRST]
    assert blocking == []


_INLINE_DUPLICATE_END_TO_END_SOURCE = (
    "import asyncio\n"
    "\n"
    "\n"
    "async def _wait_for_render(automation: object) -> None:\n"
    "    assert automation.detector is not None\n"
    "    try:\n"
    "        await automation.detector.wait_for_element(selector)\n"
    "    except (TimeoutError, RuntimeError) as render_error:\n"
    "        logger.warning('did not render: %s', render_error)\n"
    "\n"
    "\n"
    "async def _navigate_then_wait(automation: object) -> None:\n"
    "    await automation.cdp.navigate(url)\n"
    "    assert automation.detector is not None\n"
    "    try:\n"
    "        await automation.detector.wait_for_element(selector)\n"
    "    except (TimeoutError, RuntimeError) as render_error:\n"
    "        logger.warning('did not render: %s', render_error)\n"
)


def test_gate_blocks_inline_duplicate_when_only_enclosing_copy_is_added() -> None:
    """End-to-end parity check for the finding's real-world shape. The helper is
    defined first (pre-existing, untouched) and the inline copy lives in a later
    enclosing function; an edit that adds only the enclosing copy lines makes the
    live Write/Edit hook BLOCK. The deferred message the commit/push gate re-scopes
    must produce the same verdict — blocking, not advisory — so the two enforcement
    surfaces agree.
    """
    enclosing_definition_line = (
        _INLINE_DUPLICATE_END_TO_END_SOURCE.splitlines().index(
            "async def _navigate_then_wait(automation: object) -> None:"
        )
        + 1
    )
    enclosing_added_lines = set(range(enclosing_definition_line, enclosing_definition_line + 6))

    pretooluse_issues = check_same_file_inline_duplicate_body(
        _INLINE_DUPLICATE_END_TO_END_SOURCE,
        "account_switcher.py",
        all_changed_lines=enclosing_added_lines,
    )
    assert any("_wait_for_render" in each_issue for each_issue in pretooluse_issues), (
        "The live Write/Edit path must block when the enclosing copy is added, "
        f"got: {pretooluse_issues}"
    )

    deferred_issues = check_same_file_inline_duplicate_body(
        _INLINE_DUPLICATE_END_TO_END_SOURCE,
        "account_switcher.py",
        all_changed_lines=enclosing_added_lines,
        defer_scope_to_caller=True,
    )
    blocking, advisory = gate_module.split_violations_by_scope(
        deferred_issues, enclosing_added_lines
    )
    assert any("_wait_for_render" in each_issue for each_issue in blocking), (
        "The commit/push gate must reconstruct the union scope and BLOCK the same "
        f"enclosing-only edit the live hook blocks, got blocking: {blocking}, "
        f"advisory: {advisory}"
    )
    assert advisory == [], (
        "No inline-duplicate violation may land in advisory when the gate and the "
        f"live hook agree on blocking, got advisory: {advisory}"
    )


def test_collect_partitioned_violations_advises_pre_existing_sibling_duplicate(
    temporary_git_repository: Path,
) -> None:
    """A committed file already carrying a sibling-duplicate helper, edited only in
    an unrelated region, yields the duplicate-body violation as advisory — never
    blocking. Without a parseable span the gate forces every duplicate-body message
    into the blocking payload, which would wedge a convergence loop the author
    cannot clear by editing the touched lines.
    """
    package_directory = temporary_git_repository / "package"
    package_directory.mkdir()
    existing_file = package_directory / "existing_helper.py"
    existing_file.write_text(_DUPLICATE_HELPER_SOURCE, encoding="utf-8")
    copied_file = package_directory / "copied_helper.py"
    copied_file.write_text(
        _DUPLICATE_HELPER_SOURCE + "unrelated_constant = 1\n", encoding="utf-8"
    )
    unrelated_added_line = _DUPLICATE_HELPER_SOURCE.count("\n") + 1
    validate_content = gate_module.load_validate_content()

    resolved_copied = copied_file.resolve()
    blocking_by_file, advisory_by_file, _skipped = (
        gate_module._collect_partitioned_violations(
            validate_content,
            [copied_file],
            temporary_git_repository,
            {resolved_copied: {unrelated_added_line}},
        )
    )

    all_blocking_messages = [
        each_message
        for each_file_messages in blocking_by_file.values()
        for each_message in each_file_messages
    ]
    all_advisory_messages = [
        each_message
        for each_file_messages in advisory_by_file.values()
        for each_message in each_file_messages
    ]
    assert not any(
        "duplicates existing_helper.py" in each_message
        for each_message in all_blocking_messages
    ), (
        "An unrelated edit to a file carrying a pre-existing sibling-duplicate "
        f"helper must not block, got blocking: {all_blocking_messages}"
    )
    assert any(
        "duplicates existing_helper.py" in each_message
        for each_message in all_advisory_messages
    ), (
        "The untouched pre-existing duplicate must surface as advisory, got "
        f"advisory: {all_advisory_messages}"
    )


def test_collect_partitioned_violations_blocks_sibling_duplicate_in_added_region(
    temporary_git_repository: Path,
) -> None:
    """When the diff's added lines fall inside the copied function, the duplicate
    body is blocking — staging an edit that touches the copied helper still denies
    the commit, matching the live Write/Edit hook."""
    package_directory = temporary_git_repository / "package"
    package_directory.mkdir()
    existing_file = package_directory / "existing_helper.py"
    existing_file.write_text(_DUPLICATE_HELPER_SOURCE, encoding="utf-8")
    copied_file = package_directory / "copied_helper.py"
    copied_file.write_text(_DUPLICATE_HELPER_SOURCE, encoding="utf-8")
    definition_line = 3
    last_body_line = 15
    all_copied_function_lines = set(range(definition_line, last_body_line + 1))
    validate_content = gate_module.load_validate_content()

    resolved_copied = copied_file.resolve()
    blocking_by_file, _advisory_by_file, _skipped = (
        gate_module._collect_partitioned_violations(
            validate_content,
            [copied_file],
            temporary_git_repository,
            {resolved_copied: all_copied_function_lines},
        )
    )

    all_blocking_messages = [
        each_message
        for each_file_messages in blocking_by_file.values()
        for each_message in each_file_messages
    ]
    assert any(
        "duplicates existing_helper.py" in each_message
        for each_message in all_blocking_messages
    ), (
        "An edit whose added lines touch the copied helper must still block, got "
        f"blocking: {all_blocking_messages}"
    )


def test_run_gate_skips_non_utf8_source_without_crashing(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: run_gate must skip files that fail UTF-8 decoding.

    UnicodeDecodeError is a ValueError subclass, not OSError. A non-UTF-8
    source file in the staged set must be skipped (matching whole_file_line_set
    behavior) rather than crash the gate mid-audit, and the skip must fail
    closed: a changed file the gate could not validate must never be silently
    approved.
    """
    write_file(temporary_git_repository / "anchor.py", "anchor = 1\n")
    commit_all_files(temporary_git_repository, "baseline")
    non_utf8_path = temporary_git_repository / "non_utf8.py"
    non_utf8_path.parent.mkdir(parents=True, exist_ok=True)
    non_utf8_path.write_bytes(b"name = '\xff\xfe invalid utf8 bytes'\n")
    stage_file(temporary_git_repository, "non_utf8.py")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 1


def test_run_gate_fails_closed_when_only_changed_file_is_unreadable(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A changed file that cannot be validated must not be silently approved.

    When the only staged code file holds genuine non-UTF-8 bytes and no other
    blocking violation exists, the gate must fail closed (non-zero) rather than
    exit 0, because it never validated that file.
    """
    write_file(temporary_git_repository / "anchor.py", "anchor = 1\n")
    commit_all_files(temporary_git_repository, "baseline")
    non_utf8_path = temporary_git_repository / "non_utf8.py"
    non_utf8_path.parent.mkdir(parents=True, exist_ok=True)
    non_utf8_path.write_bytes(b"\xff\xfe\x00bad")
    stage_file(temporary_git_repository, "non_utf8.py")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code != 0


def test_run_gate_fails_closed_on_skipped_non_utf8_file_directly(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """run_gate must fail closed when a changed file is skipped for non-UTF-8.

    Mirrors the bugteam gate's parity test: a non-UTF-8 code file with no other
    violation must surface the skip and produce a non-zero exit so an
    unvalidated file is never silently approved.
    """
    non_utf8_file = tmp_path / "garbled.py"
    non_utf8_file.write_bytes(b"\xff\xfe\x00bad")

    def fake_validate(_content: str, _path: str, **_kwargs: object) -> list[str]:
        return []

    exit_code = gate_module.run_gate(
        fake_validate,
        [non_utf8_file],
        tmp_path,
        all_added_lines_by_path=None,
    )

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "skip unreadable" in captured.err


def test_run_gate_fails_closed_when_clean_file_accompanies_unreadable_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A clean readable file must not mask an unreadable sibling across files.

    run_gate aggregates per-file results: even when one staged file validates
    cleanly, an accompanying file that cannot be decoded must still surface the
    skip and force a non-zero exit so the unvalidated file is never approved.
    """
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("first_count = 1\nsecond_count = 2\n", encoding="utf-8")
    unreadable_file = tmp_path / "garbled.py"
    unreadable_file.write_bytes(b"\xff\xfe\x00bad")

    def fake_validate(
        _content: str, _path: str, _prior: str = "", **_kwargs: object
    ) -> list[str]:
        return []

    exit_code = gate_module.run_gate(
        fake_validate,
        [clean_file, unreadable_file],
        tmp_path,
        all_added_lines_by_path=None,
    )

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "skip unreadable" in captured.err


def test_check_wrapper_plumb_through_accepts_positional_or_keyword_forwarder() -> None:
    """Regression: positional-or-keyword forwarders with defaults must not be flagged.

    When a wrapper exposes the delegate's optional kwarg as a positional-or-keyword
    parameter with a default value and forwards it correctly, the check must produce
    zero findings. This mirrors a wrapper/delegate signature pairing
    where the wrapper exposes the delegate's optional kwarg.
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


def _build_function_module(
    function_name: str, body_line_count: int, leading_lines: int
) -> str:
    preamble = "".join("anchor_name\n" for _ in range(leading_lines))
    body = "\n".join("    keep_alive_name" for _ in range(body_line_count))
    return f"{preamble}def {function_name}() -> None:\n{body}\n"


def test_main_blocks_when_function_body_grows_past_threshold_with_def_line_untouched(
    temporary_git_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An existing function grown past the blocking threshold by editing its
    body must be classified blocking even when the ``def`` line is untouched.

    Anchoring the function-length violation to the ``def`` line let the gate
    treat it as advisory whenever body growth left the definition line
    outside the added-line set. The violation must surface as blocking
    regardless of which body line carries the edit.
    """
    short_body_count = 5
    baseline = _build_function_module(
        "grow_me", body_line_count=short_body_count, leading_lines=0
    )
    write_file(temporary_git_repository / "module.py", baseline)
    commit_all_files(temporary_git_repository, "baseline short function")

    grown_body_count = 70
    grown = _build_function_module(
        "grow_me", body_line_count=grown_body_count, leading_lines=0
    )
    write_file(temporary_git_repository / "module.py", grown)
    stage_file(temporary_git_repository, "module.py")

    monkeypatch.chdir(temporary_git_repository)
    exit_code = gate_module.main(["--staged"])

    assert exit_code == 1


def test_split_violations_blocks_function_length_when_span_intersects_added_lines() -> None:
    """A function-length issue whose declared span overlaps the diff's added
    lines is blocking — the body grew, which is exactly Finding B's intent."""
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
    This prevents the over-block regression where every pre-existing >=60-line
    function in a touched file was forced into the blocking payload."""
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
    lines must still block at the gate. The gate scopes by added lines, so the
    in-scope sixth violation blocks regardless of how many untouched ones
    precede it."""
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
    must still block at the gate. The gate scopes by added lines, so the
    in-scope sixth probe blocks regardless of how many untouched ones
    precede it."""
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
    must still block at the gate. The gate scopes by added lines, so the
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


def _load_bugteam_gate_module() -> ModuleType:
    bugteam_scripts_dir = (
        Path(__file__).resolve().parents[4]
        / "skills"
        / "bugteam"
        / "scripts"
    )
    if str(bugteam_scripts_dir) not in sys.path:
        sys.path.insert(0, str(bugteam_scripts_dir))
    module_path = bugteam_scripts_dir / "bugteam_code_rules_gate.py"
    spec = importlib.util.spec_from_file_location("bugteam_code_rules_gate", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_both_gates_classify_wrapper_plumb_through_identically() -> None:
    """The bugteam and _shared gate copies of check_wrapper_plumb_through must
    return identical findings. A class method calling a module-level delegate
    is not a wrapper; both gates must exclude it rather than one emitting a
    false positive the other does not."""
    bugteam_gate = _load_bugteam_gate_module()
    class_method_calling_delegate = (
        "def fetch(target, *, retries=3):\n"
        "    return target\n"
        "\n"
        "class MyService:\n"
        "    def public_method(self, target):\n"
        "        return fetch(target)\n"
    )
    nested_call_inside_delegate_argument = (
        "def delegate(value, *, retries=3):\n"
        "    return value\n"
        "\n"
        "def helper(value):\n"
        "    return value\n"
        "\n"
        "def public_caller(value):\n"
        "    return delegate(helper(value))\n"
    )
    name_call_dropping_kwarg = (
        "def delegate(value, *, retries=3):\n"
        "    return value\n"
        "\n"
        "def public_wrapper(value):\n"
        "    return delegate(value)\n"
    )
    for each_source in (
        class_method_calling_delegate,
        nested_call_inside_delegate_argument,
        name_call_dropping_kwarg,
    ):
        shared_issues = gate_module.check_wrapper_plumb_through(each_source, "module.py")
        bugteam_issues = bugteam_gate.check_wrapper_plumb_through(each_source, "module.py")
        assert shared_issues == bugteam_issues, (
            "both gate copies of check_wrapper_plumb_through must classify "
            f"identically; shared={shared_issues!r} bugteam={bugteam_issues!r}"
        )


def test_check_wrapper_plumb_through_stays_under_function_length_threshold() -> None:
    """check_wrapper_plumb_through must stay under the enforcer's function-length
    blocking threshold so editing it (e.g. aligning the two gate copies) does
    not itself trip the gate; its signature-index and class-method-id collection
    are extracted into helpers."""
    enforcer_span = inspect.getsource(gate_module.check_wrapper_plumb_through)
    declared_line_count = len(enforcer_span.splitlines())
    blocking_threshold = 60
    assert declared_line_count < blocking_threshold, (
        f"check_wrapper_plumb_through is {declared_line_count} lines; extract "
        "helpers to keep it under the function-length blocking threshold"
    )


def _banned_noun_parameter_issues() -> list[str]:
    validate_content = gate_module.load_validate_content()
    source = (
        "def aggregate(canned_results: int) -> int:\n"
        "    doubled = canned_results * 2\n"
        "    return doubled\n"
    )
    issues = validate_content(source, "src/module.py", "")
    return [each_issue for each_issue in issues if "banned noun" in each_issue]


def test_split_violations_blocks_banned_noun_when_binding_line_is_added() -> None:
    """A banned-noun binding is blocking when its own binding line is among the
    added lines. The gate reconstructs the one-line binding span through the
    same shared extractor registry it uses for function-length and isolation,
    rather than relying on the bare ``Line N:`` prefix branch."""
    banned_noun_issues = _banned_noun_parameter_issues()
    assert banned_noun_issues, "expected a banned-noun parameter issue"
    parameter_binding_line = 1
    blocking, advisory = gate_module.split_violations_by_scope(
        banned_noun_issues,
        all_added_line_numbers={parameter_binding_line},
    )
    assert blocking == banned_noun_issues
    assert advisory == []


def test_split_violations_advises_banned_noun_when_binding_line_untouched() -> None:
    """A banned-noun binding whose own line is not among the added lines is
    advisory — editing an unrelated body line does not pull a pre-existing
    binding into scope, mirroring the companion exact-match identifier check."""
    banned_noun_issues = _banned_noun_parameter_issues()
    assert banned_noun_issues, "expected a banned-noun parameter issue"
    unrelated_body_line = 2
    blocking, advisory = gate_module.split_violations_by_scope(
        banned_noun_issues,
        all_added_line_numbers={unrelated_body_line},
    )
    assert advisory == banned_noun_issues
    assert blocking == []


def test_banned_noun_span_range_covers_only_the_binding_line() -> None:
    """The reconstructed span is the binding line alone — one line, never the
    enclosing function span. A parameter declared on a ``def`` line yields a
    range covering only that line, so an unrelated body edit cannot pull the
    pre-existing binding into scope."""
    banned_noun_issues = _banned_noun_parameter_issues()
    assert banned_noun_issues, "expected a banned-noun parameter issue"
    parameter_binding_line = 1
    span = gate_module.banned_noun_span_range(banned_noun_issues[0])
    assert span == range(parameter_binding_line, parameter_binding_line + 1)
    assert len(span) == 1


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
