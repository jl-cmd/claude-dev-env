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
from unittest.mock import MagicMock, patch

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

from config.preflight_constants import PYTEST_NO_TESTS_COLLECTED_EXIT_CODE  # noqa: E402


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
    assert "for each_path in" in discover_tests_source
    assert "for each_part in" in discover_tests_source


def test_preflight_uses_extracted_directory_marker_constants() -> None:
    """preflight.py must reference extracted constants instead of inline string literals.

    The CODE_RULES magic-values rule treats inline ``.git`` and ``.venv``
    string literals in production function bodies as violations. Confirm
    preflight.py imports them (or a frozenset that contains ``.venv``) from
    config.preflight_constants instead.
    """
    preflight_source = inspect.getsource(preflight)
    assert "GIT_DIRECTORY_NAME" in preflight_source
    assert "ALL_TESTS_DIRECTORY_IGNORE_PARTS" in preflight_source
    find_root_source = inspect.getsource(preflight.find_repository_root)
    assert "'.git'" not in find_root_source
    assert '".git"' not in find_root_source
    discover_tests_source = inspect.getsource(preflight.has_discoverable_tests)
    assert "'.venv'" not in discover_tests_source
    assert '".venv"' not in discover_tests_source


def test_preflight_does_not_import_unused_venv_directory_name_constant() -> None:
    """The ``VENV_DIRECTORY_NAME`` constant is not consumed by preflight.py
    (``.venv`` reaches the function body via ``ALL_TESTS_DIRECTORY_IGNORE_PARTS``).
    Importing the standalone name is dead code per the unused-imports rule."""
    preflight_source = inspect.getsource(preflight)
    assert "VENV_DIRECTORY_NAME" not in preflight_source, (
        "Dead import must be removed; preflight.py reaches `.venv` via "
        "ALL_TESTS_DIRECTORY_IGNORE_PARTS instead"
    )


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
