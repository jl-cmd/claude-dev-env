"""Tests for preflight git hooks path verification.

Covers:
- core.hooksPath unset: exits non-zero with correction message
- core.hooksPath pointing to the correct claude hooks dir: exits zero
- core.hooksPath pointing elsewhere (husky override): exits non-zero
- core.hooksPath with trailing slash: must still pass after normalization
"""

import importlib.util
import inspect
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import ANY, MagicMock, patch

import pytest


def _load_preflight_module() -> ModuleType:
    module_path = Path(__file__).parent.parent / "preflight.py"
    spec = importlib.util.spec_from_file_location("preflight", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


preflight = _load_preflight_module()

from config.preflight_constants import (  # noqa: E402
    PYTEST_INI_FILENAME,
    PYTEST_NO_TESTS_COLLECTED_EXIT_CODE,
)


def _make_completed_process(
    stdout: str, returncode: int
) -> subprocess.CompletedProcess:
    process = MagicMock(spec=subprocess.CompletedProcess)
    process.stdout = stdout
    process.returncode = returncode
    return process


def test_should_exit_nonzero_when_core_hooks_path_unset(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process("", returncode=1)
        exit_code = preflight.verify_git_hooks_path()
    assert exit_code != 0
    captured = capsys.readouterr()
    assert "core.hooksPath" in captured.err
    assert "npx claude-dev-env" in captured.err or "git config" in captured.err


def test_should_exit_zero_when_core_hooks_path_points_to_claude_hooks(
    tmp_path: Path,
) -> None:
    claude_hooks_path = tmp_path / ".claude" / "hooks" / "git-hooks"
    claude_hooks_path.mkdir(parents=True)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            str(claude_hooks_path) + "\n", returncode=0
        )
        exit_code = preflight.verify_git_hooks_path()
    assert exit_code == 0


def test_should_exit_nonzero_when_core_hooks_path_points_elsewhere(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            "/some/other/path/.husky\n", returncode=0
        )
        exit_code = preflight.verify_git_hooks_path()
    assert exit_code != 0
    captured = capsys.readouterr()
    assert "core.hooksPath" in captured.err


def test_should_include_correction_commands_in_error_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process("", returncode=1)
        preflight.verify_git_hooks_path()
    captured = capsys.readouterr()
    assert (
        "npx claude-dev-env" in captured.err
        or "git config --global core.hooksPath" in captured.err
    )


def test_main_should_exit_nonzero_when_hooks_path_unset() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process("", returncode=1)
        exit_code = preflight.main(["--no-pytest"])
    assert exit_code != 0


def test_main_should_continue_when_hooks_path_valid(tmp_path: Path) -> None:
    claude_hooks_path = tmp_path / ".claude" / "hooks" / "git-hooks"
    claude_hooks_path.mkdir(parents=True)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            str(claude_hooks_path) + "\n", returncode=0
        )
        exit_code = preflight.main(["--no-pytest"])
    assert exit_code == 0


def test_should_accept_hooks_path_with_trailing_slash() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            "/home/user/.claude/hooks/git-hooks/\n", returncode=0
        )
        exit_code = preflight.verify_git_hooks_path()
    assert exit_code == 0, (
        "hooksPath with trailing slash must pass verification after normalization"
    )


def test_should_exit_zero_when_hooks_path_set_at_repo_scope(tmp_path: Path) -> None:
    claude_hooks_path = tmp_path / ".claude" / "hooks" / "git-hooks"
    claude_hooks_path.mkdir(parents=True)
    repo_root = tmp_path / "my-repo"
    repo_root.mkdir()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            str(claude_hooks_path) + "\n", returncode=0
        )
        exit_code = preflight.verify_git_hooks_path(repo_root)
    assert exit_code == 0, (
        "verify_git_hooks_path must accept a valid path returned by effective "
        "config query (not restricted to --global scope)"
    )
    called_command = mock_run.call_args[0][0]
    assert "--global" not in called_command, (
        "verify_git_hooks_path must query effective config, not --global only"
    )
    assert "-C" in called_command, (
        "verify_git_hooks_path must use git -C <repo_root> for repo-effective config"
    )
    dash_c_index = called_command.index("-C")
    assert called_command[dash_c_index + 1] == str(repo_root), (
        "git -C must receive the resolved repository root path"
    )


def test_should_accept_hooks_path_with_backslash_and_trailing_slash() -> None:
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            "C:\\Users\\user\\.claude\\hooks\\git-hooks\\\n", returncode=0
        )
        exit_code = preflight.verify_git_hooks_path()
    assert exit_code == 0, (
        "Windows hooksPath with trailing backslash must pass after normalization"
    )


def test_should_exit_nonzero_when_git_executable_not_found(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Preflight must not crash with a traceback when git is missing from PATH."""
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        exit_code = preflight.verify_git_hooks_path()
    assert exit_code != 0, (
        "FileNotFoundError from subprocess.run must produce a non-zero exit, "
        "not a propagated traceback"
    )
    captured = capsys.readouterr()
    assert "git" in captured.err.lower(), (
        "Error message must mention git so the user knows what is missing"
    )
    assert (
        "npx claude-dev-env" in captured.err
        or "git config --global core.hooksPath" in captured.err
    ), "Error message must include the enforcement-absent remediation hints"


def test_should_exit_nonzero_when_subprocess_run_raises_os_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Preflight must surface a clean error for other OS-level git launch failures."""
    with patch("subprocess.run", side_effect=OSError("permission denied")):
        exit_code = preflight.verify_git_hooks_path()
    assert exit_code != 0, (
        "OSError from subprocess.run must produce a non-zero exit, "
        "not a propagated traceback"
    )
    captured = capsys.readouterr()
    assert "preflight" in captured.err, (
        "Error message must be prefixed with the preflight tool name for context"
    )
    assert "permission denied" in captured.err, (
        "Error message must include the underlying OSError detail for diagnosis"
    )


def test_preflight_uses_shared_hooks_path_suffix_constant() -> None:
    """Preflight's expected suffix must come from config.fix_hookspath_constants
    so the canonical hooks directory is defined in exactly one place."""
    scripts_directory = str(Path(__file__).parent.parent.resolve())
    if scripts_directory not in sys.path:
        sys.path.insert(0, scripts_directory)
    constants_module_path = (
        Path(__file__).parent.parent / "config" / "fix_hookspath_constants.py"
    )
    constants_specification = importlib.util.spec_from_file_location(
        "config.fix_hookspath_constants",
        constants_module_path,
    )
    assert constants_specification is not None
    assert constants_specification.loader is not None
    constants_module = importlib.util.module_from_spec(constants_specification)
    constants_specification.loader.exec_module(constants_module)
    expected_suffix = constants_module.HOOKS_PATH_VERIFICATION_SUFFIX

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            f"/some/where/{expected_suffix}\n", returncode=0
        )
        exit_code = preflight.verify_git_hooks_path()
    assert exit_code == 0


def test_preflight_skip_uses_shared_env_var_constant(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The preflight skip env-var name must come from config/preflight_constants.py."""
    scripts_directory = str(Path(__file__).parent.parent.resolve())
    if scripts_directory not in sys.path:
        sys.path.insert(0, scripts_directory)
    constants_module_path = (
        Path(__file__).parent.parent / "config" / "preflight_constants.py"
    )
    constants_specification = importlib.util.spec_from_file_location(
        "config.preflight_constants",
        constants_module_path,
    )
    assert constants_specification is not None
    assert constants_specification.loader is not None
    constants_module = importlib.util.module_from_spec(constants_specification)
    constants_specification.loader.exec_module(constants_module)
    skip_env_var_name = constants_module.BUGTEAM_PREFLIGHT_SKIP_ENV_VAR_NAME

    monkeypatch.setenv(skip_env_var_name, "1")
    exit_code = preflight.main(["--no-pytest"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert skip_env_var_name in captured.err


def test_loop_variables_use_each_prefix_in_preflight_module() -> None:
    find_root_source = inspect.getsource(preflight.find_repository_root)
    assert "for each_candidate in" in find_root_source

    discover_tests_source = inspect.getsource(preflight.has_discoverable_tests)
    assert "ALL_GIT_LS_FILES_TEST_DISCOVERY_SUBCOMMAND" in discover_tests_source


def test_preflight_uses_extracted_directory_marker_constants() -> None:
    preflight_source = inspect.getsource(preflight)
    assert "GIT_DIRECTORY_NAME" in preflight_source
    assert "ALL_GIT_LS_FILES_TEST_DISCOVERY_SUBCOMMAND" in preflight_source
    find_root_source = inspect.getsource(preflight.find_repository_root)
    assert "'.git'" not in find_root_source
    assert '".git"' not in find_root_source
    discover_tests_source = inspect.getsource(preflight.has_discoverable_tests)
    assert "ALL_GIT_LS_FILES_TEST_DISCOVERY_SUBCOMMAND" in discover_tests_source


def test_preflight_stderr_uses_bugteam_preflight_prefix(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Preflight's stderr prefix must remain ``bugteam_preflight:`` so the bugteam
    SKILL.md auto-remediation pattern (`bugteam_preflight: core.hooksPath is`)
    keeps matching when Phase 2 wires bugteam to import this shared script."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process(
            "/some/other/path/.husky\n", returncode=0
        )
        preflight.verify_git_hooks_path()
    captured = capsys.readouterr()
    assert "bugteam_preflight: core.hooksPath is" in captured.err, (
        "Stderr prefix must preserve the bugteam SKILL.md auto-remediation contract"
    )


def test_preflight_does_not_import_unused_repository_root_marker_constant() -> None:
    """The ``ALL_REPOSITORY_ROOT_MARKER_FILENAMES`` constant is not consumed by
    preflight.py. Importing it is dead code per the unused-imports rule."""
    preflight_source = inspect.getsource(preflight)
    assert "ALL_REPOSITORY_ROOT_MARKER_FILENAMES" not in preflight_source, (
        "Dead import must be removed; preflight.py uses individual marker "
        "filename constants directly"
    )


def test_pytest_no_tests_collected_helper_returns_named_constant() -> None:
    """The pytest "no tests collected" exit code must be sourced from the
    named constant in config/preflight_constants.py rather than the bare
    literal 5 inside the function body (CODE_RULES magic-values rule)."""
    assert preflight._pytest_exit_code_no_tests_collected() == (
        PYTEST_NO_TESTS_COLLECTED_EXIT_CODE
    )
    helper_source = inspect.getsource(preflight._pytest_exit_code_no_tests_collected)
    assert "PYTEST_NO_TESTS_COLLECTED_EXIT_CODE" in helper_source, (
        "Helper body must return the named constant, not the bare literal 5"
    )


def test_preflight_bootstrap_moves_script_directory_to_front() -> None:
    """Import bootstrap keeps exactly one script directory entry at the front."""
    module_path = Path(__file__).parent.parent / "preflight.py"
    script_directory_resolved = str(module_path.parent.resolve())
    script_directory_absolute = str(module_path.parent.absolute())
    original_sys_path = list(sys.path)
    try:
        sys.path.insert(0, script_directory_resolved)
        sys.path.insert(0, script_directory_resolved)
        sys.path.insert(0, str(module_path.parents[4]))
        _load_preflight_module()
        assert os.path.samefile(sys.path[0], script_directory_resolved)
        equivalent_count = sum(
            1
            for each_entry in sys.path
            if os.path.exists(each_entry)
            and os.path.samefile(each_entry, script_directory_resolved)
        )
        assert equivalent_count == 1
        assert sys.path[0] == script_directory_absolute
    finally:
        sys.path[:] = original_sys_path


def test_main_uses_correct_changed_files_function_name() -> None:
    """main() must call get_changed_files, not the undefined get_all_changed_files."""
    main_source = inspect.getsource(preflight.main)
    assert "get_all_changed_files(" not in main_source


def test_should_not_return_nonexistent_test_file(tmp_path: Path) -> None:
    """A deleted test file path from git diff --name-only must not be returned.
    Before the fix, _find_related_test_files returned paths without checking
    whether the file exists on disk, which caused pytest to receive
    nonexistent paths for deleted files.
    """
    repo_root = tmp_path
    deleted_test_path = Path("test_deleted_module.py")
    result = preflight._find_related_test_files(deleted_test_path, repo_root)
    assert result == []


def test_should_not_return_test_files_for_non_python_file(tmp_path: Path) -> None:
    """A non-.py file must return an empty list regardless of file existence."""
    repo_root = tmp_path
    non_python_path = Path("readme.txt")
    (repo_root / non_python_path).touch()
    result = preflight._find_related_test_files(non_python_path, repo_root)
    assert result == []


def test_should_find_test_file_in_adjacent_tests_directory(tmp_path: Path) -> None:
    """A source file with a matching test in the adjacent tests/ directory
    must return that test file path."""
    repo_root = tmp_path
    source_path = Path("src/module.py")
    (repo_root / source_path).parent.mkdir(parents=True)
    (repo_root / source_path).touch()
    adjacent_tests = repo_root / "src" / "tests"
    adjacent_tests.mkdir(parents=True)
    expected_test = adjacent_tests / "test_module.py"
    expected_test.touch()
    result = preflight._find_related_test_files(source_path, repo_root)
    assert expected_test in result


def test_should_find_test_file_in_top_level_tests_directory(tmp_path: Path) -> None:
    """A source file with a matching test in the top-level tests/ directory
    must return that test file path."""
    repo_root = tmp_path
    source_path = Path("src/module.py")
    (repo_root / source_path).parent.mkdir(parents=True)
    (repo_root / source_path).touch()
    top_tests = repo_root / "tests" / "src"
    top_tests.mkdir(parents=True)
    expected_test = top_tests / "test_module.py"
    expected_test.touch()
    result = preflight._find_related_test_files(source_path, repo_root)
    assert expected_test in result


def test_main_should_warn_when_scope_changed_without_base_ref(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--scope changed with no --base-ref must warn and fall back to full suite."""
    with (
        patch.object(preflight, "verify_git_hooks_path", return_value=0),
        patch.object(preflight, "has_pytest_configuration", return_value=True),
        patch.object(preflight, "has_discoverable_tests", return_value=True),
        patch.object(preflight, "run_pytest", return_value=0),
    ):
        exit_code = preflight.main(["--scope", "changed"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "requires --base-ref" in captured.err, (
        "Missing warning when --scope changed is used without --base-ref"
    )


def test_has_discoverable_tests_should_not_re_raise_on_git_failure(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """has_discoverable_tests must return None instead of re-raising on git failure."""
    (tmp_path / ".git").mkdir()
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(128, ["git"])):
        result = preflight.has_discoverable_tests(tmp_path)
    captured = capsys.readouterr()
    assert result is None, (
        "Should return None instead of propagating the exception"
    )
    assert "bugteam_preflight:" in captured.err
    assert "git ls-files failed" in captured.err


def test_main_should_not_double_print_when_git_ls_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When git ls-files fails, main() must print a distinct failure warning and
    run the full pytest suite instead of silently skipping tests."""
    mock_hooks_result = _make_completed_process(
        "/home/user/.claude/hooks/git-hooks\n", returncode=0
    )
    with (
        patch("subprocess.run") as mock_run,
        patch.object(preflight, "run_pytest", return_value=0) as mock_pytest,
    ):
        mock_run.side_effect = [
            mock_hooks_result,
            subprocess.CalledProcessError(128, ["git", "ls-files"]),
        ]
        exit_code = preflight.main([])
    captured = capsys.readouterr()
    assert "bugteam_preflight: test discovery failed" in captured.err, (
        "Must print a distinct warning when discovery fails, not the 'no tests found' message"
    )
    assert "bugteam_preflight: pytest configured but no tests found" not in captured.err, (
        "Must not print the 'no tests found' skip message when discovery fails"
    )
    mock_pytest.assert_called_once_with(ANY, False)


def test_should_default_to_changed_scope_when_base_ref_provided() -> None:
    """--base-ref without --scope must default to 'changed', not 'all'.

    The help text says 'Defaults to changed when --base-ref is provided'.
    Before the fix, the None -> PYTEST_SCOPE_ALL conversion ran before
    checking --base-ref, so providing --base-ref without --scope still
    ran the full suite without calling get_changed_files.
    """
    with (
        patch.object(preflight, "verify_git_hooks_path", return_value=0),
        patch.object(preflight, "has_pytest_configuration", return_value=True),
        patch.object(preflight, "has_discoverable_tests", return_value=True),
        patch.object(preflight, "get_changed_files") as mock_get_changed,
        patch.object(preflight, "discover_related_tests", return_value=[]),
        patch.object(preflight, "run_pytest", return_value=0),
    ):
        exit_code = preflight.main(["--base-ref", "origin/main"])
    assert exit_code == 0
    mock_get_changed.assert_called_once_with(
        ANY, "origin/main"
    )


def test_should_default_to_all_scope_when_no_base_ref_no_scope(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Omitting both --scope and --base-ref must default to 'all'."""
    with (
        patch.object(preflight, "verify_git_hooks_path", return_value=0),
        patch.object(preflight, "has_pytest_configuration", return_value=True),
        patch.object(preflight, "has_discoverable_tests", return_value=True),
        patch.object(preflight, "run_pytest", return_value=0),
    ):
        exit_code = preflight.main([])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "running full suite" not in captured.err, (
        "Default scope=all should run directly without changed-scope messages"
    )


def test_explicit_scope_all_with_base_ref_should_not_call_get_changed_files(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Explicit --scope all with --base-ref must not auto-convert to 'changed'.

    Before the fix, ``argparse`` defaulted ``--scope`` to ``PYTEST_SCOPE_ALL``
    (``"all"``), making it impossible to distinguish "user typed --scope all"
    versus "user omitted --scope". The code then auto-converted
    ``effective_scope == "all"`` to ``"changed"`` whenever ``--base-ref`` was
    present, silently overriding an explicit ``--scope all``.

    After the fix, ``--scope`` defaults to ``None`` and is resolved to ``"all"``
    only after argparse, so the user's explicit ``--scope all`` stays ``"all"``
    and the full suite runs regardless of ``--base-ref``.
    """
    with (
        patch.object(preflight, "verify_git_hooks_path", return_value=0),
        patch.object(preflight, "has_pytest_configuration", return_value=True),
        patch.object(preflight, "has_discoverable_tests", return_value=True),
        patch.object(preflight, "get_changed_files") as mock_get_changed,
        patch.object(preflight, "discover_related_tests", return_value=[]),
        patch.object(preflight, "run_pytest", return_value=0),
    ):
        exit_code = preflight.main(["--scope", "all", "--base-ref", "origin/main"])
    assert exit_code == 0
    mock_get_changed.assert_not_called()


def test_preflight_bootstrap_matches_code_rules_sys_path_pattern() -> None:
    """Bootstrap must clear duplicate script_directory entries, then guard insert."""
    module_path = Path(__file__).parent.parent / "preflight.py"
    source = module_path.read_text(encoding="utf-8")
    assert "_entry_points_at_preflight_script_directory" in source, (
        "Bootstrap must remove script_directory entries using path equivalence"
    )
    assert "for each_index in range(len(sys.path) - 1, -1, -1):" in source, (
        "Bootstrap must walk sys.path to drop duplicate script directory entries"
    )
    assert "_preflight_scripts_path_entry not in sys.path:" in source, (
        "Bootstrap insert must be guarded for code_rules_gate compliance"
    )
    assert "sys.path.insert(0, _preflight_scripts_path_entry)" in source, (
        "Bootstrap must insert the absolute script directory at index 0"
    )


def test_has_discoverable_tests_should_include_untracked_test_files(
    tmp_path: Path,
) -> None:
    """has_discoverable_tests must include --others --exclude-standard
    to discover untracked test files not yet in the git index."""
    (tmp_path / ".git").mkdir()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process("untracked_test.py\n", returncode=0)
        preflight.has_discoverable_tests(tmp_path)
    called_command = mock_run.call_args[0][0]
    assert "--others" in called_command, (
        "--others flag required to include untracked files in ls-files output"
    )
    assert "--exclude-standard" in called_command, (
        "--exclude-standard flag required to respect .gitignore for untracked files"
    )


def test_run_pytest_should_use_positional_separator_before_test_paths() -> None:
    """run_pytest must pass '--' before test paths so pytest does not misinterpret
    paths starting with '-' as command-line options."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_completed_process("", returncode=0)
        preflight.run_pytest(
            Path("/fake/repository"),
            verbose=False,
            all_test_paths=[Path("test_copilot_finding.py")],
        )
    called_command = mock_run.call_args[0][0]
    separator_index = called_command.index("--")
    assert called_command[separator_index + 1:] == ["test_copilot_finding.py"], (
        "All test paths must follow the '--' positional separator"
    )


# ---- Copilot finding 1: has_discoverable_tests in non-git directories ----


def test_has_discoverable_tests_returns_true_when_no_git_marker(
    tmp_path: Path,
) -> None:
    """has_discoverable_tests must return True without running git when the root
    has no .git marker (e.g., repo root found via pytest.ini)."""
    (tmp_path / PYTEST_INI_FILENAME).touch()
    result = preflight.has_discoverable_tests(tmp_path)
    assert result is True


# ---- Copilot finding 2: base_ref command injection ----


def test_get_changed_files_returns_none_when_base_ref_starts_with_hyphen(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """get_changed_files must return None and print a warning when base_ref
    starts with '-', preventing option injection into git diff."""
    result = preflight.get_changed_files(Path("/fake"), "-oMalicious")
    assert result is None
    captured = capsys.readouterr()
    assert "base_ref" in captured.err
    assert "hyphen" in captured.err


# ---- Copilot finding 3: duplicate git failures when discovery_result is None ----


def test_main_skips_changed_scope_when_discovery_result_is_none(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When has_discoverable_tests returns None (git unavailable), main must
    not call get_changed_files even when --base-ref is provided."""
    with (
        patch.object(preflight, "verify_git_hooks_path", return_value=0),
        patch.object(preflight, "has_pytest_configuration", return_value=True),
        patch.object(preflight, "has_discoverable_tests", return_value=None),
        patch.object(preflight, "get_changed_files") as mock_get_changed,
        patch.object(preflight, "run_pytest", return_value=0),
    ):
        exit_code = preflight.main(["--base-ref", "origin/main"])
    assert exit_code == 0
    mock_get_changed.assert_not_called()


# ---- Copilot finding 4: misleading no-related-tests message on git diff failure ----


def test_main_does_not_print_no_related_tests_when_get_changed_files_returns_none(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When get_changed_files returns None (git diff failed), main must not
    print the misleading 'no related tests found' message."""
    with (
        patch.object(preflight, "verify_git_hooks_path", return_value=0),
        patch.object(preflight, "has_pytest_configuration", return_value=True),
        patch.object(preflight, "has_discoverable_tests", return_value=True),
        patch.object(preflight, "get_changed_files", return_value=None),
        patch.object(preflight, "discover_related_tests", return_value=[]),
        patch.object(preflight, "run_pytest", return_value=0),
    ):
        exit_code = preflight.main(["--scope", "changed", "--base-ref", "origin/main"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "no related tests found" not in captured.err


def test_main_should_not_print_no_pytest_config_when_pytest_configured_but_no_tests(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When pytest is configured but no tests are found, main must not print
    the misleading 'no pytest configuration found' message."""
    with (
        patch.object(preflight, "verify_git_hooks_path", return_value=0),
        patch.object(preflight, "has_pytest_configuration", return_value=True),
        patch.object(preflight, "has_discoverable_tests", return_value=False),
    ):
        exit_code = preflight.main([])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "bugteam_preflight: pytest configured but no tests found" in captured.err, (
        "Must print the correct message about configured pytest with no tests"
    )
    assert "bugteam_preflight: no pytest configuration found" not in captured.err, (
        "Must not print the misleading 'no pytest configuration found' message "
        "when pytest IS configured"
    )


def test_main_prints_no_related_tests_when_get_changed_files_returns_empty(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When get_changed_files returns [] (no changed files, git succeeded),
    main must print the 'no related tests found' message and run full suite."""
    with (
        patch.object(preflight, "verify_git_hooks_path", return_value=0),
        patch.object(preflight, "has_pytest_configuration", return_value=True),
        patch.object(preflight, "has_discoverable_tests", return_value=True),
        patch.object(preflight, "get_changed_files", return_value=[]),
        patch.object(preflight, "discover_related_tests", return_value=[]),
        patch.object(preflight, "run_pytest", return_value=0),
    ):
        exit_code = preflight.main(["--scope", "changed", "--base-ref", "origin/main"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "no related tests found" in captured.err
