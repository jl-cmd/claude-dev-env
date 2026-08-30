"""Tests for mypy integration module."""

import logging
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from . import mypy_integration as mypy_integration_module
from .mypy_integration import (
    MypyResult,
    check_mypy_available,
    find_module_resolution_root,
    find_pyproject_with_mypy_config,
    run_mypy_check,
)


def _write_config_package(package_parent: Path, constants_body: str) -> None:
    config_package = package_parent / "config"
    config_package.mkdir(parents=True)
    (config_package / "__init__.py").write_text("", encoding="utf-8")
    (config_package / "constants.py").write_text(constants_body, encoding="utf-8")


def _write_config_importer(script_path: Path) -> None:
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(
        "from config.constants import SERIALIZED_INDENT_WIDTH\n\n"
        "indent_width: int = SERIALIZED_INDENT_WIDTH\n",
        encoding="utf-8",
    )


def test_find_module_resolution_root_ignores_git_above_system_temp(
    tmp_path: Path,
) -> None:
    """A temp staging file does not inherit ``.git`` from a parent of ``%TEMP%``.

    ::

        %TEMP%/pytest-.../detached/module.py
        C:/Users/<you>/.git exists above %TEMP%
        flag: walk returns the home repo -> mypy cwd=home, torch stubs, 30s timeout
        ok:   walk stops at the temp root -> None
    """
    nested_file = tmp_path / "detached" / "module.py"
    nested_file.parent.mkdir()
    nested_file.write_text("sample_number: int = 1\n", encoding="utf-8")
    assert find_module_resolution_root(nested_file) is None


def test_find_module_resolution_root_still_sees_git_inside_temp(tmp_path: Path) -> None:
    """A repo created inside the temp tree is still a project root."""
    nested_repo = tmp_path / "inner_repo"
    nested_file = nested_repo / "pkg" / "module.py"
    nested_file.parent.mkdir(parents=True)
    (nested_repo / ".git").mkdir()
    nested_file.write_text("sample_number: int = 1\n", encoding="utf-8")
    assert find_module_resolution_root(nested_file) == nested_repo


def test_find_module_resolution_root_stops_at_runner_temp_when_gettempdir_differs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A RUNNER_TEMP staging file does not inherit ``.git`` above that root.

    ::

        RUNNER_TEMP/detached/module.py, gettempdir -> sibling os_gettemp
        tmp_path/.git sits above RUNNER_TEMP
        flag: gettempdir-only walk returns tmp_path
        ok:   walk stops at RUNNER_TEMP -> None
    """
    runner_temp_root = tmp_path / "runner_temp"
    os_gettemp = tmp_path / "os_gettemp"
    runner_temp_root.mkdir()
    os_gettemp.mkdir()
    (tmp_path / ".git").mkdir()
    monkeypatch.setenv("RUNNER_TEMP", str(runner_temp_root))
    monkeypatch.setattr(
        "validators.system_temporary_roots.tempfile.gettempdir",
        lambda: str(os_gettemp),
    )
    nested_file = runner_temp_root / "detached" / "module.py"
    nested_file.parent.mkdir()
    nested_file.write_text("sample_number: int = 1\n", encoding="utf-8")

    assert find_module_resolution_root(nested_file) is None


def test_find_module_resolution_root_returns_git_marked_ancestor(tmp_path: Path) -> None:
    target_repo = tmp_path / "git_repo"
    nested_directory = target_repo / "src" / "deep"
    nested_directory.mkdir(parents=True)
    (target_repo / ".git").mkdir()
    nested_file = nested_directory / "module.py"
    nested_file.write_text("sample_number: int = 1\n", encoding="utf-8")
    assert find_module_resolution_root(nested_file) == target_repo


def test_find_module_resolution_root_returns_nearest_pyproject_ancestor(
    tmp_path: Path,
) -> None:
    outer_repo = tmp_path / "outer"
    inner_project = outer_repo / "inner"
    inner_project.mkdir(parents=True)
    (outer_repo / ".git").mkdir()
    (inner_project / "pyproject.toml").write_text(
        "[project]\nname = 'inner'\n", encoding="utf-8"
    )
    nested_file = inner_project / "module.py"
    nested_file.write_text("sample_number: int = 1\n", encoding="utf-8")
    assert find_module_resolution_root(nested_file) == inner_project


def test_run_mypy_check_resolves_config_against_target_repo_not_session_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A target file's ``config`` import binds to its own repo, not the session cwd.

    ::

        cwd=session_worktree, whose config/ lacks SERIALIZED_INDENT_WIDTH
        target_repo/tools/serialize_tool.py imports it from target_repo/config/
        flag (defect): binds config to session_worktree -> attr-defined denial
        ok  (fixed):   binds config to target_repo       -> passes
    """
    session_worktree = tmp_path / "session_worktree"
    _write_config_package(session_worktree, "UNRELATED_SESSION_SETTING: int = 9\n")

    target_repo = tmp_path / "target_repo"
    _write_config_package(target_repo, "SERIALIZED_INDENT_WIDTH: int = 4\n")
    (target_repo / "pyproject.toml").write_text(
        "[project]\nname = 'synthetic-target'\n", encoding="utf-8"
    )
    target_script = target_repo / "tools" / "serialize_tool.py"
    _write_config_importer(target_script)

    monkeypatch.chdir(session_worktree)
    mypy_result = run_mypy_check([target_script])

    assert mypy_result.passed, mypy_result.output


def test_run_mypy_check_ignores_session_config_for_detached_gate_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A detached gate temp file does not bind ``config`` to the session cwd.

    ::

        cwd=session_worktree, whose config/ lacks SERIALIZED_INDENT_WIDTH
        detached_gate_dir/serialize_tool.py (no repo ancestor) imports it
        flag (defect): binds config to session_worktree -> attr-defined denial
        ok  (fixed):   isolated cwd -> import ignored    -> passes
    """
    session_worktree = tmp_path / "session_worktree"
    _write_config_package(session_worktree, "UNRELATED_SESSION_SETTING: int = 9\n")

    detached_file = tmp_path / "detached_gate_dir" / "serialize_tool.py"
    _write_config_importer(detached_file)

    monkeypatch.chdir(session_worktree)
    mypy_result = run_mypy_check([detached_file])

    assert mypy_result.passed, mypy_result.output


def test_run_mypy_check_still_flags_genuine_type_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real type error inside the target file is still reported.

    ::

        typed_repo/pkg/widths.py -> wrong_width: int = 'not an integer'
        flag: assigning str to an int annotation -> mypy error, passed is False
    """
    typed_repo = tmp_path / "typed_repo"
    package_directory = typed_repo / "pkg"
    package_directory.mkdir(parents=True)
    (typed_repo / "pyproject.toml").write_text(
        "[project]\nname = 'typed-target'\n", encoding="utf-8"
    )
    faulty_script = package_directory / "widths.py"
    faulty_script.write_text("wrong_width: int = 'not an integer'\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    mypy_result = run_mypy_check([faulty_script])

    assert not mypy_result.passed
    assert mypy_result.error_count >= 1


def test_run_mypy_check_accepts_relative_path_under_nested_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A repo-relative target under a nested project root is still readable.

    ::

        cwd=repo_root; changed file listed as repo-relative pkg/tool.py
        pkg/ holds its own pyproject.toml -> resolution root is repo_root/pkg
        flag (defect): mypy runs from repo_root/pkg with the repo-relative arg
                       -> "can't read file", spurious failure
        ok  (fixed):   arg resolved to an absolute path -> mypy reads it
    """
    repo_root = tmp_path / "repo_root"
    nested_package = repo_root / "pkg"
    nested_package.mkdir(parents=True)
    (repo_root / ".git").mkdir()
    (nested_package / "pyproject.toml").write_text(
        "[project]\nname = 'nested'\n", encoding="utf-8"
    )
    (nested_package / "module.py").write_text(
        "sample_number: int = 1\n", encoding="utf-8"
    )

    monkeypatch.chdir(repo_root)
    relative_target = Path("pkg") / "module.py"
    mypy_result = run_mypy_check([relative_target])

    assert mypy_result.passed, mypy_result.output


def test_run_mypy_check_does_not_report_imported_sibling_on_detached_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A detached gate file does not inherit type errors from an imported sibling.

    ::

        detached/importer.py -> from sibling import broken_value
        detached/sibling.py  -> broken_value: int = "not an integer"
        flag: follow-imports=normal reports sibling.py and fails the gate file
        ok:   follow-imports=skip grades importer.py only -> passed

    The PreToolUse gate stages one file under a temp directory with no project
    root. Following imports there loads site-packages (torch stubs) and sibling
    modules, and the 30s hook budget expires.
    """
    if not check_mypy_available():
        pytest.skip("mypy is not installed")

    detached_directory = tmp_path / "detached_gate_dir"
    detached_directory.mkdir()
    (detached_directory / "sibling.py").write_text(
        "broken_value: int = 'not an integer'\n",
        encoding="utf-8",
    )
    importer_file = detached_directory / "importer.py"
    importer_file.write_text(
        "from sibling import broken_value\n\n"
        "copied_value: int = broken_value\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    mypy_result = run_mypy_check([importer_file])

    assert mypy_result.passed, mypy_result.output
    assert "sibling.py" not in mypy_result.output


def test_run_mypy_check_reports_imported_sibling_on_rooted_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rooted file still follows first-party imports and reports sibling errors.

    ::

        rooted_repo/.git + importer.py -> from sibling import broken_value
        rooted_repo/sibling.py         -> broken_value: int = "not an integer"
        ok:   follow-imports=normal reports sibling.py -> failed
        flag: --follow-imports=skip on rooted files hides sibling.py -> passed

    Skip applies only to detached staging copies. Applying it to a repo file
    would drop first-party type errors the in-repo path must still see.
    """
    if not check_mypy_available():
        pytest.skip("mypy is not installed")

    rooted_repo = tmp_path / "rooted_repo"
    rooted_repo.mkdir()
    (rooted_repo / ".git").mkdir()
    (rooted_repo / "sibling.py").write_text(
        "broken_value: int = 'not an integer'\n",
        encoding="utf-8",
    )
    importer_file = rooted_repo / "importer.py"
    importer_file.write_text(
        "from sibling import broken_value\n\n"
        "copied_value: int = broken_value\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    mypy_result = run_mypy_check([importer_file])

    assert not mypy_result.passed
    assert "sibling.py" in mypy_result.output


def test_run_mypy_check_skips_when_detached_mypy_times_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A detached mypy that exceeds its timeout does not fail the file.

    ::

        detached/module.py, subprocess.run raises TimeoutExpired
        ok:   passed=True and the skip message is in the output
        flag: TimeoutExpired propagates and the PreToolUse hook dies
    """
    detached_file = tmp_path / "detached" / "module.py"
    detached_file.parent.mkdir()
    detached_file.write_text("sample_number: int = 1\n", encoding="utf-8")

    monkeypatch.setattr(
        mypy_integration_module, "check_mypy_available", lambda: True
    )

    def raise_timeout(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="mypy", timeout=1)

    monkeypatch.setattr(mypy_integration_module.subprocess, "run", raise_timeout)
    with caplog.at_level(logging.WARNING):
        mypy_result = run_mypy_check([detached_file])

    assert mypy_result.passed
    assert "timed out on a detached file" in mypy_result.output
    assert "timed out on a detached file" in caplog.text


def test_run_mypy_check_applies_config_resolved_from_config_source_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A staged file is checked under the config resolved from the original path.

    A strict ``[tool.mypy]`` config flags an untyped def only when
    ``config_source_path`` resolves it; native discovery from the detached
    file finds no config and passes.
    """
    strict_repo = tmp_path / "strict_repo"
    strict_repo.mkdir()
    (strict_repo / "pyproject.toml").write_text(
        "[tool.mypy]\ndisallow_untyped_defs = true\n", encoding="utf-8"
    )
    detached_file = tmp_path / "detached" / "untyped.py"
    detached_file.parent.mkdir(parents=True)
    detached_file.write_text(
        "def annotate_nothing(value):\n    return value\n", encoding="utf-8"
    )

    monkeypatch.chdir(tmp_path)

    without_source = run_mypy_check([detached_file])
    with_source = run_mypy_check(
        [detached_file], config_source_path=strict_repo / "pyproject.toml"
    )

    assert without_source.passed, without_source.output
    assert not with_source.passed


def test_mypy_result_dataclass() -> None:
    """Test MypyResult dataclass creation."""
    result = MypyResult(passed=True, output="test", error_count=0)
    assert result.passed is True
    assert result.output == "test"
    assert result.error_count == 0


def test_check_mypy_available_returns_false_when_not_installed() -> None:
    """Test that check_mypy_available returns False when mypy not found."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert check_mypy_available() is False


def test_run_mypy_check_returns_passed_for_empty_files() -> None:
    """Test that run_mypy_check passes with no files."""
    result = run_mypy_check([])
    assert result.passed is True
    assert result.error_count == 0
    assert "No files" in result.output


def test_find_pyproject_returns_pyproject_with_tool_mypy(tmp_path: Path) -> None:
    project_root = tmp_path / "myproj"
    nested_dir = project_root / "src" / "deep"
    nested_dir.mkdir(parents=True)
    project_pyproject = project_root / "pyproject.toml"
    project_pyproject.write_text("[tool.mypy]\nignore_missing_imports = true\n")
    target_file = nested_dir / "module.py"
    target_file.write_text("x: int = 1\n")
    found_path = find_pyproject_with_mypy_config(target_file)
    assert found_path == project_pyproject


def test_find_pyproject_skips_pyproject_without_tool_mypy(tmp_path: Path) -> None:
    outer_root = tmp_path / "outer"
    inner_root = outer_root / "inner"
    inner_root.mkdir(parents=True)
    outer_pyproject = outer_root / "pyproject.toml"
    outer_pyproject.write_text("[tool.mypy]\nignore_missing_imports = true\n")
    inner_pyproject = inner_root / "pyproject.toml"
    inner_pyproject.write_text("[project]\nname = 'inner-package'\n")
    target_file = inner_root / "module.py"
    target_file.write_text("y: str = 'hello'\n")
    found_path = find_pyproject_with_mypy_config(target_file)
    assert found_path == outer_pyproject


def test_find_pyproject_returns_none_when_no_match(tmp_path: Path) -> None:
    isolated_dir = tmp_path / "isolated"
    isolated_dir.mkdir()
    target_file = isolated_dir / "module.py"
    target_file.write_text("z: float = 1.0\n")
    assert find_pyproject_with_mypy_config(target_file) is None


def test_find_pyproject_handles_malformed_toml(tmp_path: Path) -> None:
    project_root = tmp_path / "broken"
    project_root.mkdir()
    project_pyproject = project_root / "pyproject.toml"
    project_pyproject.write_text("[tool.mypy\nbroken = true\n")
    target_file = project_root / "module.py"
    target_file.write_text("a = 1\n")
    assert find_pyproject_with_mypy_config(target_file) is None
