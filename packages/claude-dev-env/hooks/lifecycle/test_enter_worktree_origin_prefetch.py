"""Unit tests for the enter_worktree_origin_prefetch PreToolUse hook.

Uses real git repositories (a "remote" repo cloned into a "local" one) so the
fetch behavior is exercised against actual git plumbing, not mocked calls.
"""

from __future__ import annotations

import importlib.util
import io
import json
import pathlib
import subprocess
import sys

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
_HOOKS_TREE = _HOOK_DIR.parent
for each_path in (str(_HOOK_DIR), str(_HOOKS_TREE)):
    if each_path not in sys.path:
        sys.path.insert(0, each_path)

hook_spec = importlib.util.spec_from_file_location(
    "enter_worktree_origin_prefetch",
    _HOOK_DIR / "enter_worktree_origin_prefetch.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)


def _run_git(repo_directory: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_directory,
        capture_output=True,
        text=True,
        check=True,
    )


def _init_repo_with_commit(repo_directory: pathlib.Path) -> None:
    repo_directory.mkdir(parents=True, exist_ok=True)
    _run_git(repo_directory, "init", "--quiet", "--initial-branch=main")
    _run_git(repo_directory, "config", "user.email", "test@example.com")
    _run_git(repo_directory, "config", "user.name", "Test")
    _run_git(repo_directory, "commit", "--allow-empty", "--quiet", "-m", "init")


def _clone_as_local(remote_directory: pathlib.Path, local_directory: pathlib.Path) -> None:
    subprocess.run(
        ["git", "clone", "--quiet", str(remote_directory), str(local_directory)],
        capture_output=True,
        text=True,
        check=True,
    )
    _run_git(local_directory, "config", "user.email", "test@example.com")
    _run_git(local_directory, "config", "user.name", "Test")


def test_is_enter_worktree_creation_true_when_no_path_given() -> None:
    payload = {"tool_name": "EnterWorktree", "tool_input": {}}
    assert hook_module.is_enter_worktree_creation(payload) is True


def test_is_enter_worktree_creation_true_with_name_only() -> None:
    payload = {"tool_name": "EnterWorktree", "tool_input": {"name": "my-branch"}}
    assert hook_module.is_enter_worktree_creation(payload) is True


def test_is_enter_worktree_creation_false_when_path_given() -> None:
    payload = {"tool_name": "EnterWorktree", "tool_input": {"path": "/some/worktree"}}
    assert hook_module.is_enter_worktree_creation(payload) is False


def test_is_enter_worktree_creation_false_for_other_tool() -> None:
    payload = {"tool_name": "Bash", "tool_input": {}}
    assert hook_module.is_enter_worktree_creation(payload) is False


def test_resolve_origin_default_branch_reads_cloned_head(tmp_path: pathlib.Path) -> None:
    remote_directory = tmp_path / "remote"
    local_directory = tmp_path / "local"
    _init_repo_with_commit(remote_directory)
    _clone_as_local(remote_directory, local_directory)

    resolved_branch = hook_module.resolve_origin_default_branch(str(local_directory))

    assert resolved_branch == "main"


def test_resolve_origin_default_branch_returns_none_without_origin(
    tmp_path: pathlib.Path,
) -> None:
    solo_directory = tmp_path / "solo"
    _init_repo_with_commit(solo_directory)

    resolved_branch = hook_module.resolve_origin_default_branch(str(solo_directory))

    assert resolved_branch is None


def test_fetch_origin_branch_updates_stale_local_ref(tmp_path: pathlib.Path) -> None:
    remote_directory = tmp_path / "remote"
    local_directory = tmp_path / "local"
    _init_repo_with_commit(remote_directory)
    _clone_as_local(remote_directory, local_directory)

    _run_git(remote_directory, "commit", "--allow-empty", "--quiet", "-m", "second")
    remote_head_sha = _run_git(remote_directory, "rev-parse", "HEAD").stdout.strip()
    local_cached_sha_before = _run_git(
        local_directory, "rev-parse", "refs/remotes/origin/main"
    ).stdout.strip()
    assert local_cached_sha_before != remote_head_sha

    hook_module.fetch_origin_branch(str(local_directory), "main")

    local_cached_sha_after = _run_git(
        local_directory, "rev-parse", "refs/remotes/origin/main"
    ).stdout.strip()
    assert local_cached_sha_after == remote_head_sha


def test_fetch_origin_branch_never_raises_when_remote_missing(tmp_path: pathlib.Path) -> None:
    solo_directory = tmp_path / "solo"
    _init_repo_with_commit(solo_directory)

    hook_module.fetch_origin_branch(str(solo_directory), "main")


def test_main_fetches_stale_ref_and_exits_zero(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    remote_directory = tmp_path / "remote"
    local_directory = tmp_path / "local"
    _init_repo_with_commit(remote_directory)
    _clone_as_local(remote_directory, local_directory)
    _run_git(remote_directory, "commit", "--allow-empty", "--quiet", "-m", "second")
    remote_head_sha = _run_git(remote_directory, "rev-parse", "HEAD").stdout.strip()

    payload = {
        "tool_name": "EnterWorktree",
        "tool_input": {},
        "cwd": str(local_directory),
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

    with pytest.raises(SystemExit) as exit_info:
        hook_module.main()

    assert exit_info.value.code == 0
    local_cached_sha_after = _run_git(
        local_directory, "rev-parse", "refs/remotes/origin/main"
    ).stdout.strip()
    assert local_cached_sha_after == remote_head_sha


def test_main_exits_zero_for_non_enter_worktree_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": "/tmp"}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

    with pytest.raises(SystemExit) as exit_info:
        hook_module.main()

    assert exit_info.value.code == 0


def test_main_exits_zero_on_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))

    with pytest.raises(SystemExit) as exit_info:
        hook_module.main()

    assert exit_info.value.code == 0


def test_main_exits_zero_on_empty_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))

    with pytest.raises(SystemExit) as exit_info:
        hook_module.main()

    assert exit_info.value.code == 0


def test_main_exits_zero_on_whitespace_only_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("   \n\t  "))

    with pytest.raises(SystemExit) as exit_info:
        hook_module.main()

    assert exit_info.value.code == 0


def test_main_exits_zero_on_json_array_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("[]"))

    with pytest.raises(SystemExit) as exit_info:
        hook_module.main()

    assert exit_info.value.code == 0


def test_main_exits_zero_on_json_scalar_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("42"))

    with pytest.raises(SystemExit) as exit_info:
        hook_module.main()

    assert exit_info.value.code == 0
