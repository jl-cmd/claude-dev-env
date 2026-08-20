"""Behavioral tests for fresh_branch_git_commands using real temporary git repos."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from fresh_branch_git_commands import (
    assert_git_accepts_branch_name,
    build_worktree_add_arguments,
    create_worktree_branch,
    fetch_base_ref,
    is_ref_present,
    read_failure_text,
    resolve_base_commit,
    resolve_repo_root,
    run_git,
    split_remote_ref,
)

GIT_USER_NAME = "fresh-branch-test"
GIT_USER_EMAIL = "fresh-branch-test@example.com"
MAIN_BRANCH_NAME = "main"
SEED_FILE_NAME = "README.md"
SEED_FILE_CONTENTS = "seed\n"


def build_repo(workspace_path: Path) -> Path:
    workspace_path.mkdir(parents=True, exist_ok=True)
    empty_hooks_path = workspace_path / "empty-hooks"
    empty_hooks_path.mkdir()
    hooks_argument = ["-c", f"core.hooksPath={empty_hooks_path}"]
    subprocess.run(
        ["git", *hooks_argument, "init", "-b", MAIN_BRANCH_NAME, str(workspace_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    for each_pair in (
        ("user.name", GIT_USER_NAME),
        ("user.email", GIT_USER_EMAIL),
        ("commit.gpgsign", "false"),
    ):
        subprocess.run(
            ["git", *hooks_argument, "config", *each_pair],
            cwd=str(workspace_path),
            check=True,
            capture_output=True,
            text=True,
        )
    (workspace_path / SEED_FILE_NAME).write_text(SEED_FILE_CONTENTS, encoding="utf-8")
    subprocess.run(
        ["git", *hooks_argument, "add", SEED_FILE_NAME],
        cwd=str(workspace_path),
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", *hooks_argument, "commit", "-m", "initial commit"],
        cwd=str(workspace_path),
        check=True,
        capture_output=True,
        text=True,
    )
    return workspace_path


def build_clone_with_origin(workspace_path: Path) -> tuple[Path, Path]:
    seed_path = build_repo(workspace_path / "seed")
    empty_hooks_path = seed_path / "empty-hooks"
    hooks_argument = ["-c", f"core.hooksPath={empty_hooks_path}"]
    bare_origin = workspace_path / "origin.git"
    subprocess.run(
        ["git", *hooks_argument, "clone", "--bare", str(seed_path), str(bare_origin)],
        check=True,
        capture_output=True,
        text=True,
    )
    clone_path = workspace_path / "clone"
    subprocess.run(
        ["git", *hooks_argument, "clone", str(bare_origin), str(clone_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    for each_pair in (
        ("user.name", GIT_USER_NAME),
        ("user.email", GIT_USER_EMAIL),
        ("commit.gpgsign", "false"),
    ):
        subprocess.run(
            ["git", *hooks_argument, "config", *each_pair],
            cwd=str(clone_path),
            check=True,
            capture_output=True,
            text=True,
        )
    return clone_path, bare_origin


def advance_origin_main(workspace_path: Path, bare_origin: Path) -> str:
    pusher_path = workspace_path / "pusher"
    empty_hooks_path = workspace_path / "seed" / "empty-hooks"
    hooks_argument = ["-c", f"core.hooksPath={empty_hooks_path}"]
    subprocess.run(
        ["git", *hooks_argument, "clone", str(bare_origin), str(pusher_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    for each_pair in (
        ("user.name", GIT_USER_NAME),
        ("user.email", GIT_USER_EMAIL),
        ("commit.gpgsign", "false"),
    ):
        subprocess.run(
            ["git", *hooks_argument, "config", *each_pair],
            cwd=str(pusher_path),
            check=True,
            capture_output=True,
            text=True,
        )
    (pusher_path / SEED_FILE_NAME).write_text("advanced\n", encoding="utf-8")
    subprocess.run(
        ["git", *hooks_argument, "commit", "-am", "advance main"],
        cwd=str(pusher_path),
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", *hooks_argument, "push", "origin", MAIN_BRANCH_NAME],
        cwd=str(pusher_path),
        check=True,
        capture_output=True,
        text=True,
    )
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(pusher_path),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def read_branch_config(
    repository_path: Path,
    branch_name: str,
    config_leaf: str,
) -> str:
    completed = subprocess.run(
        ["git", "config", "--get", f"branch.{branch_name}.{config_leaf}"],
        cwd=str(repository_path),
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


class TestBuildWorktreeAddArguments:
    def test_pass_no_track_so_the_new_branch_gets_no_upstream(self) -> None:
        all_arguments = build_worktree_add_arguments(
            "fix/x",
            Path("/tmp/agent/fix/x"),
            "origin/main",
        )
        assert "--no-track" in all_arguments

    def test_order_arguments_the_way_git_worktree_add_expects(self) -> None:
        all_arguments = build_worktree_add_arguments(
            "fix/x",
            Path("/tmp/agent/fix/x"),
            "origin/main",
        )
        assert all_arguments[:4] == ["worktree", "add", "-b", "fix/x"]
        assert all_arguments[-1] == "origin/main"
        assert all_arguments[-2] == str(Path("/tmp/agent/fix/x"))


class TestSplitRemoteRef:
    def test_split_an_origin_ref(self) -> None:
        assert split_remote_ref("origin/main") == ("origin", "main")

    def test_split_a_non_origin_remote_ref(self) -> None:
        assert split_remote_ref("upstream/dev") == ("upstream", "dev")

    def test_default_a_bare_name_to_origin(self) -> None:
        assert split_remote_ref("main") == ("origin", "main")

    def test_keep_slashes_inside_the_branch_name(self) -> None:
        assert split_remote_ref("origin/fix/nested") == ("origin", "fix/nested")


class TestAssertGitAcceptsBranchName:
    def test_accept_a_conventional_branch_name(self) -> None:
        assert assert_git_accepts_branch_name("fix/example-one") is None

    def test_reject_a_name_git_refuses(self) -> None:
        with pytest.raises(ValueError, match="relative path"):
            assert_git_accepts_branch_name("fix..example")


class TestResolveRepoRoot:
    def test_return_the_toplevel_for_a_nested_path(self, tmp_path: Path) -> None:
        repository_path = build_repo(tmp_path / "repo")
        nested_path = repository_path / "nested"
        nested_path.mkdir()
        assert resolve_repo_root(nested_path).resolve() == repository_path.resolve()

    def test_raise_outside_a_repository(self, tmp_path: Path) -> None:
        plain_directory = tmp_path / "plain"
        plain_directory.mkdir()
        with pytest.raises(RuntimeError, match="git repository"):
            resolve_repo_root(plain_directory)


class TestIsRefPresent:
    def test_find_a_local_branch(self, tmp_path: Path) -> None:
        repository_path = build_repo(tmp_path / "repo")
        assert is_ref_present(repository_path, MAIN_BRANCH_NAME) is True

    def test_not_find_an_absent_ref(self, tmp_path: Path) -> None:
        repository_path = build_repo(tmp_path / "repo")
        assert is_ref_present(repository_path, "origin/nowhere") is False


class TestReadFailureText:
    def test_prefer_stderr(self, tmp_path: Path) -> None:
        repository_path = build_repo(tmp_path / "repo")
        completed = run_git(["rev-parse", "does-not-exist"], repository_path)
        assert completed.returncode != 0
        assert "does-not-exist" in read_failure_text(completed)


class TestFetchBaseRef:
    def test_bring_the_remote_tip_into_the_clone(self, tmp_path: Path) -> None:
        clone_path, bare_origin = build_clone_with_origin(tmp_path / "workspace")
        advanced_commit = advance_origin_main(tmp_path / "workspace", bare_origin)
        fetch_base_ref(clone_path, "origin/main")
        assert is_ref_present(clone_path, "origin/main") is True
        assert resolve_base_commit(clone_path, "origin/main") == advanced_commit

    def test_raise_for_a_remote_branch_that_does_not_exist(
        self,
        tmp_path: Path,
    ) -> None:
        clone_path, _bare_origin = build_clone_with_origin(tmp_path / "workspace")
        with pytest.raises(RuntimeError, match="git fetch failed"):
            fetch_base_ref(clone_path, "origin/nowhere")


class TestResolveBaseCommit:
    def test_return_the_sha_at_the_ref(self, tmp_path: Path) -> None:
        repository_path = build_repo(tmp_path / "repo")
        head_commit = run_git(["rev-parse", "HEAD"], repository_path).stdout.strip()
        assert resolve_base_commit(repository_path, MAIN_BRANCH_NAME) == head_commit

    def test_raise_for_an_unresolvable_ref(self, tmp_path: Path) -> None:
        repository_path = build_repo(tmp_path / "repo")
        with pytest.raises(RuntimeError, match="could not resolve base commit"):
            resolve_base_commit(repository_path, "refs/heads/nowhere")


class TestCreateWorktreeBranch:
    def test_create_the_branch_at_the_base_ref_with_no_upstream(
        self,
        tmp_path: Path,
    ) -> None:
        clone_path, _bare_origin = build_clone_with_origin(tmp_path / "workspace")
        origin_tip = resolve_base_commit(clone_path, "origin/main")
        worktree_path = tmp_path / "worktrees" / "fix" / "created"
        create_worktree_branch(
            clone_path,
            branch_name="fix/created",
            worktree_path=worktree_path,
            base_ref="origin/main",
        )
        assert worktree_path.is_dir()
        assert resolve_base_commit(worktree_path, "HEAD") == origin_tip
        assert read_branch_config(clone_path, "fix/created", "merge") == ""
        assert read_branch_config(clone_path, "fix/created", "remote") == ""

    def test_raise_when_the_branch_already_exists(self, tmp_path: Path) -> None:
        clone_path, _bare_origin = build_clone_with_origin(tmp_path / "workspace")
        first_path = tmp_path / "worktrees" / "dup-one"
        second_path = tmp_path / "worktrees" / "dup-two"
        create_worktree_branch(
            clone_path,
            branch_name="fix/dup",
            worktree_path=first_path,
            base_ref="origin/main",
        )
        with pytest.raises(RuntimeError, match="worktree add failed"):
            create_worktree_branch(
                clone_path,
                branch_name="fix/dup",
                worktree_path=second_path,
                base_ref="origin/main",
            )
