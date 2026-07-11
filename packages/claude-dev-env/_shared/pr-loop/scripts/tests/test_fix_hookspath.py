"""Tests for shared fix_hookspath.py extracted from skills/bugteam/scripts/.

Covers:
- removes a local-scope core.hooksPath override and re-runs preflight
- sets global core.hooksPath when missing
- idempotent: second invocation produces the same final state with no errors
- no-op when no override exists and global is already canonical
- exits non-zero with a clear message when canonical hooks dir is missing
- handles paths with spaces
"""

import importlib.util
import os
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


def _load_fix_module() -> ModuleType:
    module_path = Path(__file__).parent.parent / "fix_hookspath.py"
    spec = importlib.util.spec_from_file_location("fix_hookspath", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fix_hookspath = _load_fix_module()


def _make_isolated_git_environment(home_directory: Path) -> dict[str, str]:
    isolated_environment = os.environ.copy()
    isolated_environment["HOME"] = str(home_directory)
    isolated_environment["USERPROFILE"] = str(home_directory)
    isolated_environment["XDG_CONFIG_HOME"] = str(home_directory / ".config")
    isolated_environment["GIT_CONFIG_GLOBAL"] = str(home_directory / ".gitconfig")
    isolated_environment["GIT_CONFIG_NOSYSTEM"] = "1"
    return isolated_environment


def _initialize_repository(repository_path: Path, environment: dict[str, str]) -> None:
    repository_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--quiet", str(repository_path)],
        check=True,
        env=environment,
    )


def _set_local_hooks_path(
    repository_path: Path,
    hooks_path_value: str,
    environment: dict[str, str],
) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(repository_path),
            "config",
            "--local",
            "core.hooksPath",
            hooks_path_value,
        ],
        check=True,
        env=environment,
    )


def _set_global_hooks_path(hooks_path_value: str, environment: dict[str, str]) -> None:
    subprocess.run(
        ["git", "config", "--global", "core.hooksPath", hooks_path_value],
        check=True,
        env=environment,
    )


def _read_local_hooks_path(repository_path: Path, environment: dict[str, str]) -> str:
    completed_process = subprocess.run(
        [
            "git",
            "-C",
            str(repository_path),
            "config",
            "--local",
            "--get",
            "core.hooksPath",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    return completed_process.stdout.strip()


def _read_global_hooks_path(environment: dict[str, str]) -> str:
    completed_process = subprocess.run(
        ["git", "config", "--global", "--get", "core.hooksPath"],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    return completed_process.stdout.strip()


def _create_canonical_hooks_directory(home_directory: Path) -> Path:
    canonical_hooks_directory = home_directory / ".claude" / "hooks" / "git-hooks"
    canonical_hooks_directory.mkdir(parents=True)
    return canonical_hooks_directory


def test_should_remove_local_override_and_pass_preflight(tmp_path: Path) -> None:
    home_directory = tmp_path / "home"
    home_directory.mkdir()
    environment = _make_isolated_git_environment(home_directory)
    canonical_hooks_directory = _create_canonical_hooks_directory(home_directory)
    _set_global_hooks_path(str(canonical_hooks_directory), environment)
    repository_path = tmp_path / "synthetic-repo"
    _initialize_repository(repository_path, environment)
    stale_local_value = str(repository_path / ".git" / "hooks")
    _set_local_hooks_path(repository_path, stale_local_value, environment)

    exit_code = fix_hookspath.main(
        ["--repo-root", str(repository_path)],
        all_environment_overrides=environment,
    )

    assert exit_code == 0
    assert _read_local_hooks_path(repository_path, environment) == ""


def test_should_set_global_hooks_path_when_missing(tmp_path: Path) -> None:
    home_directory = tmp_path / "home"
    home_directory.mkdir()
    environment = _make_isolated_git_environment(home_directory)
    canonical_hooks_directory = _create_canonical_hooks_directory(home_directory)
    repository_path = tmp_path / "synthetic-repo"
    _initialize_repository(repository_path, environment)
    stale_local_value = str(repository_path / ".git" / "hooks")
    _set_local_hooks_path(repository_path, stale_local_value, environment)

    exit_code = fix_hookspath.main(
        ["--repo-root", str(repository_path)],
        all_environment_overrides=environment,
    )

    assert exit_code == 0
    global_value_after_fix = _read_global_hooks_path(environment)
    assert (
        global_value_after_fix.replace("\\", "/")
        .rstrip("/")
        .endswith("hooks/git-hooks")
    )


def test_should_be_idempotent(tmp_path: Path) -> None:
    home_directory = tmp_path / "home"
    home_directory.mkdir()
    environment = _make_isolated_git_environment(home_directory)
    canonical_hooks_directory = _create_canonical_hooks_directory(home_directory)
    _set_global_hooks_path(str(canonical_hooks_directory), environment)
    repository_path = tmp_path / "synthetic-repo"
    _initialize_repository(repository_path, environment)
    stale_local_value = str(repository_path / ".git" / "hooks")
    _set_local_hooks_path(repository_path, stale_local_value, environment)

    first_exit_code = fix_hookspath.main(
        ["--repo-root", str(repository_path)],
        all_environment_overrides=environment,
    )
    second_exit_code = fix_hookspath.main(
        ["--repo-root", str(repository_path)],
        all_environment_overrides=environment,
    )

    assert first_exit_code == 0
    assert second_exit_code == 0
    assert _read_local_hooks_path(repository_path, environment) == ""


def test_should_no_op_when_already_clean(tmp_path: Path) -> None:
    home_directory = tmp_path / "home"
    home_directory.mkdir()
    environment = _make_isolated_git_environment(home_directory)
    canonical_hooks_directory = _create_canonical_hooks_directory(home_directory)
    _set_global_hooks_path(str(canonical_hooks_directory), environment)
    repository_path = tmp_path / "synthetic-repo"
    _initialize_repository(repository_path, environment)

    exit_code = fix_hookspath.main(
        ["--repo-root", str(repository_path)],
        all_environment_overrides=environment,
    )

    assert exit_code == 0
    assert _read_local_hooks_path(repository_path, environment) == ""
    assert (
        _read_global_hooks_path(environment)
        .replace("\\", "/")
        .rstrip("/")
        .endswith("hooks/git-hooks")
    )


def test_should_exit_nonzero_when_canonical_hooks_directory_missing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home_directory = tmp_path / "home"
    home_directory.mkdir()
    environment = _make_isolated_git_environment(home_directory)
    repository_path = tmp_path / "synthetic-repo"
    _initialize_repository(repository_path, environment)
    stale_local_value = str(repository_path / ".git" / "hooks")
    _set_local_hooks_path(repository_path, stale_local_value, environment)

    exit_code = fix_hookspath.main(
        ["--repo-root", str(repository_path)],
        all_environment_overrides=environment,
    )

    assert exit_code != 0
    captured_streams = capsys.readouterr()
    assert "hooks/git-hooks" in captured_streams.err.replace("\\", "/")


def test_constant_wrapper_functions_have_been_removed() -> None:
    """The three wrappers returned an already-imported module-level constant
    unchanged. They added a layer of indirection with no transformation,
    validation, or test seam, so they were inlined at every call site
    and removed.
    """
    assert not hasattr(fix_hookspath, "_expected_hooks_path_suffix")
    assert not hasattr(fix_hookspath, "_canonical_hooks_directory_components")
    assert not hasattr(fix_hookspath, "_home_env_var_names")


def test_is_canonical_hooks_path_still_recognizes_canonical_suffix() -> None:
    canonical_value_with_suffix = "/home/example/.claude/hooks/git-hooks"
    assert fix_hookspath.is_canonical_hooks_path(canonical_value_with_suffix)


def test_resolve_canonical_hooks_directory_uses_home_env_overrides(
    tmp_path: Path,
) -> None:
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    overrides = {"HOME": str(fake_home), "USERPROFILE": str(fake_home)}
    resolved = fix_hookspath.resolve_canonical_hooks_directory(overrides)
    assert resolved == fake_home / ".claude" / "hooks" / "git-hooks"


def test_list_local_core_hooks_path_values_surfaces_git_stderr(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When git -C ... config --get-all exits non-zero with stderr, the helper
    must print a diagnostic to sys.stderr so the failure is distinguishable from
    "no local override exists".
    """
    failing_completed_process = subprocess.CompletedProcess(
        args=["git"],
        returncode=128,
        stdout="",
        stderr="fatal: not a git repository (or any parent up to mount point /)",
    )
    monkeypatch.setattr(
        fix_hookspath.subprocess, "run", lambda *_args, **_kwargs: failing_completed_process
    )

    returned_values = fix_hookspath.list_local_core_hooks_path_values(
        tmp_path / "any-repo", None
    )

    assert returned_values == []
    captured_streams = capsys.readouterr()
    assert "fix_hookspath" in captured_streams.err
    assert "core.hooksPath" in captured_streams.err
    assert "not a git repository" in captured_streams.err


def test_list_local_core_hooks_path_values_quiet_when_stderr_empty(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`git config --get-all` exits 1 with empty stderr when the key is simply
    unset. That is the dominant happy path and must NOT emit a diagnostic."""
    unset_completed_process = subprocess.CompletedProcess(
        args=["git"], returncode=1, stdout="", stderr=""
    )
    monkeypatch.setattr(
        fix_hookspath.subprocess, "run", lambda *_args, **_kwargs: unset_completed_process
    )

    returned_values = fix_hookspath.list_local_core_hooks_path_values(
        tmp_path / "any-repo", None
    )

    assert returned_values == []
    captured_streams = capsys.readouterr()
    assert captured_streams.err == ""


def test_read_global_core_hooks_path_surfaces_git_stderr(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the global git-config read exits non-zero with stderr, the helper
    must print a diagnostic so callers can distinguish "global unset" from
    "git broken"."""
    failing_completed_process = subprocess.CompletedProcess(
        args=["git"],
        returncode=128,
        stdout="",
        stderr="fatal: bad config line 1 in file /home/example/.gitconfig",
    )
    monkeypatch.setattr(
        fix_hookspath.subprocess, "run", lambda *_args, **_kwargs: failing_completed_process
    )

    returned_value = fix_hookspath.read_global_core_hooks_path(None)

    assert returned_value == ""
    captured_streams = capsys.readouterr()
    assert "fix_hookspath" in captured_streams.err
    assert "core.hooksPath" in captured_streams.err
    assert "bad config" in captured_streams.err


def test_read_global_core_hooks_path_quiet_when_stderr_empty(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`git config --global --get` exits 1 with empty stderr when the key is
    simply unset. That is the dominant happy path and must NOT emit a diagnostic."""
    unset_completed_process = subprocess.CompletedProcess(
        args=["git"], returncode=1, stdout="", stderr=""
    )
    monkeypatch.setattr(
        fix_hookspath.subprocess, "run", lambda *_args, **_kwargs: unset_completed_process
    )

    returned_value = fix_hookspath.read_global_core_hooks_path(None)

    assert returned_value == ""
    captured_streams = capsys.readouterr()
    assert captured_streams.err == ""


def test_should_handle_paths_with_spaces(tmp_path: Path) -> None:
    home_directory = tmp_path / "home with space"
    home_directory.mkdir()
    environment = _make_isolated_git_environment(home_directory)
    canonical_hooks_directory = _create_canonical_hooks_directory(home_directory)
    _set_global_hooks_path(str(canonical_hooks_directory), environment)
    repository_path = tmp_path / "repo with space"
    _initialize_repository(repository_path, environment)
    stale_local_value = str(repository_path / ".git" / "hooks")
    _set_local_hooks_path(repository_path, stale_local_value, environment)

    exit_code = fix_hookspath.main(
        ["--repo-root", str(repository_path)],
        all_environment_overrides=environment,
    )

    assert exit_code == 0
    assert _read_local_hooks_path(repository_path, environment) == ""
