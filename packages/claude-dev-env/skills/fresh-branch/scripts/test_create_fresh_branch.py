"""Behavioral tests for create_fresh_branch using real temporary git repos."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from fresh_branch_scripts_constants.fresh_branch_cli_constants import (
    DEFAULT_AGENT_SLUG,
    DEFAULT_BASE_REF,
    ERROR_CLI_ARGUMENTS,
    EXIT_CODE_FAILURE,
    EXIT_CODE_SUCCESS,
    FRESH_BRANCH_AGENT_ENV_VAR,
    PAYLOAD_KEY_AGENT,
    PAYLOAD_KEY_BASE_COMMIT,
    PAYLOAD_KEY_BASE_REF,
    PAYLOAD_KEY_BRANCH,
    PAYLOAD_KEY_ERROR,
    PAYLOAD_KEY_REPO_ROOT,
    PAYLOAD_KEY_WORKTREE_PATH,
)

SCRIPT_PATH = SCRIPTS_DIRECTORY / "create_fresh_branch.py"
GIT_USER_NAME = "fresh-branch-test"
GIT_USER_EMAIL = "fresh-branch-test@example.com"
INITIAL_COMMIT_MESSAGE = "initial commit"
MAIN_BRANCH_NAME = "main"
REMOTE_NAME = "origin"
SEED_FILE_NAME = "README.md"
SEED_FILE_CONTENTS = "seed\n"
ALL_AGENT_ENV_MARKERS = (
    FRESH_BRANCH_AGENT_ENV_VAR,
    "CURSOR_AGENT",
    "CURSOR_TRACE_ID",
    "CODEX_HOME",
    "CODEX_CI",
    "GROK_AGENT",
    "CLAUDECODE",
    "CLAUDE_CODE_ENTRYPOINT",
)


def load_create_fresh_branch_module() -> ModuleType:
    module_name = "create_fresh_branch_under_test"
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    loaded_module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = loaded_module
    spec.loader.exec_module(loaded_module)
    return loaded_module


def clear_agent_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for each_env_name in ALL_AGENT_ENV_MARKERS:
        monkeypatch.delenv(each_env_name, raising=False)


def run_git(
    all_arguments: list[str],
    working_directory: Path,
    empty_hooks_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    git_arguments = list(all_arguments)
    if empty_hooks_path is not None:
        git_arguments = [
            "-c",
            f"core.hooksPath={empty_hooks_path}",
            *git_arguments,
        ]
    return subprocess.run(
        ["git", *git_arguments],
        cwd=str(working_directory),
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )


def configure_git_identity(repository_path: Path, empty_hooks_path: Path) -> None:
    run_git(
        ["config", "user.name", GIT_USER_NAME],
        repository_path,
        empty_hooks_path=empty_hooks_path,
    )
    run_git(
        ["config", "user.email", GIT_USER_EMAIL],
        repository_path,
        empty_hooks_path=empty_hooks_path,
    )
    run_git(
        ["config", "commit.gpgsign", "false"],
        repository_path,
        empty_hooks_path=empty_hooks_path,
    )


def build_repo_with_origin(workspace_path: Path) -> Path:
    workspace_path.mkdir(parents=True, exist_ok=True)
    empty_hooks_path = workspace_path / "empty-hooks"
    empty_hooks_path.mkdir()
    bare_origin = workspace_path / "origin.git"
    run_git(
        ["init", "--bare", str(bare_origin)],
        workspace_path,
        empty_hooks_path=empty_hooks_path,
    )
    clone_path = workspace_path / "clone"
    run_git(
        ["clone", str(bare_origin), str(clone_path)],
        workspace_path,
        empty_hooks_path=empty_hooks_path,
    )
    configure_git_identity(clone_path, empty_hooks_path=empty_hooks_path)
    run_git(
        ["checkout", "-b", MAIN_BRANCH_NAME],
        clone_path,
        empty_hooks_path=empty_hooks_path,
    )
    (clone_path / SEED_FILE_NAME).write_text(SEED_FILE_CONTENTS, encoding="utf-8")
    run_git(["add", SEED_FILE_NAME], clone_path, empty_hooks_path=empty_hooks_path)
    run_git(
        ["commit", "-m", INITIAL_COMMIT_MESSAGE],
        clone_path,
        empty_hooks_path=empty_hooks_path,
    )
    run_git(
        ["push", "-u", REMOTE_NAME, MAIN_BRANCH_NAME],
        clone_path,
        empty_hooks_path=empty_hooks_path,
    )
    return clone_path


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


def read_head_branch(repository_path: Path) -> str:
    completed = run_git(["rev-parse", "--abbrev-ref", "HEAD"], repository_path)
    return completed.stdout.strip()


def read_head_commit(repository_path: Path) -> str:
    completed = run_git(["rev-parse", "HEAD"], repository_path)
    return completed.stdout.strip()


def read_remote_main_commit(repository_path: Path) -> str:
    completed = run_git(
        ["ls-remote", REMOTE_NAME, f"refs/heads/{MAIN_BRANCH_NAME}"],
        repository_path,
    )
    return completed.stdout.split()[0]


class TestResolveAgentSlug:
    def should_prefer_flag_over_environment(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_create_fresh_branch_module()
        clear_agent_environment(monkeypatch)
        monkeypatch.setenv(FRESH_BRANCH_AGENT_ENV_VAR, "codex")
        assert module.resolve_agent_slug("Cursor") == "cursor"

    def should_use_fresh_branch_agent_env_before_markers(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_create_fresh_branch_module()
        clear_agent_environment(monkeypatch)
        monkeypatch.setenv(FRESH_BRANCH_AGENT_ENV_VAR, "Grok")
        monkeypatch.setenv("CURSOR_TRACE_ID", "1")
        assert module.resolve_agent_slug(None) == "grok"

    def should_detect_cursor_from_marker(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_create_fresh_branch_module()
        clear_agent_environment(monkeypatch)
        monkeypatch.setenv("CURSOR_TRACE_ID", "abc")
        assert module.resolve_agent_slug(None) == "cursor"

    def should_detect_codex_from_marker(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_create_fresh_branch_module()
        clear_agent_environment(monkeypatch)
        monkeypatch.setenv("CODEX_HOME", "/tmp/codex")
        assert module.resolve_agent_slug(None) == "codex"

    def should_detect_grok_from_marker(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_create_fresh_branch_module()
        clear_agent_environment(monkeypatch)
        monkeypatch.setenv("GROK_AGENT", "1")
        assert module.resolve_agent_slug(None) == "grok"

    def should_default_to_claude_when_no_markers(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_create_fresh_branch_module()
        clear_agent_environment(monkeypatch)
        assert module.resolve_agent_slug(None) == DEFAULT_AGENT_SLUG

    def should_reject_invalid_agent_slug(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_create_fresh_branch_module()
        clear_agent_environment(monkeypatch)
        with pytest.raises(ValueError, match="agent slug"):
            module.resolve_agent_slug("../evil")


class TestResolveAgentWorktreeRoot:
    def should_use_userprofile_scratch_on_windows(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_create_fresh_branch_module()
        monkeypatch.setattr(module.sys, "platform", "win32")
        monkeypatch.setenv("USERPROFILE", r"C:\Users\example")
        worktree_root = module.resolve_agent_worktree_root("grok")
        assert worktree_root == (
            Path(r"C:\Users\example") / "AppData" / "Local" / "Temp" / "grok"
        )

    def should_fall_back_to_gettempdir_off_windows(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        module = load_create_fresh_branch_module()
        monkeypatch.setattr(module.sys, "platform", "linux")
        monkeypatch.setattr(module.tempfile, "gettempdir", lambda: str(tmp_path))
        worktree_root = module.resolve_agent_worktree_root("claude")
        assert worktree_root == tmp_path / "claude"


class TestResolveUniqueWorktreePath:
    def should_return_preferred_when_missing(self, tmp_path: Path) -> None:
        module = load_create_fresh_branch_module()
        preferred_path = tmp_path / "feature-one"
        assert module.resolve_unique_worktree_path(preferred_path) == preferred_path

    def should_suffix_when_preferred_exists(self, tmp_path: Path) -> None:
        module = load_create_fresh_branch_module()
        preferred_path = tmp_path / "feature-one"
        preferred_path.mkdir()
        unique_path = module.resolve_unique_worktree_path(preferred_path)
        assert unique_path == tmp_path / "feature-one-2"


class TestNormalizeBaseRef:
    def should_expand_bare_branch_name_to_origin_tracking_ref(self) -> None:
        module = load_create_fresh_branch_module()
        assert module.normalize_base_ref(MAIN_BRANCH_NAME) == DEFAULT_BASE_REF

    def should_preserve_explicit_remote_tracking_ref(self) -> None:
        module = load_create_fresh_branch_module()
        assert module.normalize_base_ref(DEFAULT_BASE_REF) == DEFAULT_BASE_REF

    def should_preserve_non_origin_remote_ref(self) -> None:
        module = load_create_fresh_branch_module()
        assert module.normalize_base_ref("upstream/dev") == "upstream/dev"


class TestAgentSlugPathSafety:
    def should_reject_parent_segment_agent_slug_without_mkdir_outside(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_create_fresh_branch_module()
        agent_scratch_parent = tmp_path / "agent-scratch"
        agent_scratch_parent.mkdir()
        escaped_agent_root = (agent_scratch_parent / ".." / "escape-agent").resolve()
        monkeypatch.setattr(module.sys, "platform", "linux")
        monkeypatch.setattr(
            module.tempfile,
            "gettempdir",
            lambda: str(agent_scratch_parent),
        )
        with pytest.raises(ValueError, match="agent slug"):
            module.create_fresh_branch(
                branch_name="fix/safe-branch",
                repo_path=tmp_path / "unused-repo",
                agent_slug="../escape-agent",
                base_ref=DEFAULT_BASE_REF,
            )
        assert not escaped_agent_root.exists()
        assert not (agent_scratch_parent / "claude").exists()

    def should_reject_empty_agent_slug(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_create_fresh_branch_module()
        agent_scratch_parent = tmp_path / "agent-scratch"
        agent_scratch_parent.mkdir()
        monkeypatch.setattr(module.sys, "platform", "linux")
        monkeypatch.setattr(
            module.tempfile,
            "gettempdir",
            lambda: str(agent_scratch_parent),
        )
        with pytest.raises(ValueError, match="agent slug"):
            module.create_fresh_branch(
                branch_name="fix/safe-branch",
                repo_path=tmp_path / "unused-repo",
                agent_slug="",
                base_ref=DEFAULT_BASE_REF,
            )
        assert not any(agent_scratch_parent.iterdir())


class TestBranchNamePathSafety:
    def should_reject_parent_segments_without_mkdir_outside(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_create_fresh_branch_module()
        agent_scratch_parent = tmp_path / "agent-scratch"
        agent_scratch_parent.mkdir()
        monkeypatch.setattr(module.sys, "platform", "linux")
        monkeypatch.setattr(
            module.tempfile,
            "gettempdir",
            lambda: str(agent_scratch_parent),
        )
        escaped_path = agent_scratch_parent / "escape"
        with pytest.raises(ValueError, match="relative path"):
            module.create_fresh_branch(
                branch_name="fix/../../escape",
                repo_path=tmp_path / "unused-repo",
                agent_slug="claude",
                base_ref=DEFAULT_BASE_REF,
            )
        assert not escaped_path.exists()
        assert not (agent_scratch_parent / "claude").exists()

    def should_reject_absolute_branch_without_mkdir_outside(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_create_fresh_branch_module()
        agent_scratch_parent = tmp_path / "agent-scratch"
        agent_scratch_parent.mkdir()
        outside_target = tmp_path / "outside-evil"
        monkeypatch.setattr(module.sys, "platform", "linux")
        monkeypatch.setattr(
            module.tempfile,
            "gettempdir",
            lambda: str(agent_scratch_parent),
        )
        with pytest.raises(ValueError, match="relative path"):
            module.create_fresh_branch(
                branch_name=str(outside_target),
                repo_path=tmp_path / "unused-repo",
                agent_slug="claude",
                base_ref=DEFAULT_BASE_REF,
            )
        assert not outside_target.exists()
        assert not (agent_scratch_parent / "claude").exists()


class TestCreateFreshBranchIntegration:
    def should_create_worktree_branch_without_moving_caller_head(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_create_fresh_branch_module()
        repository_path = build_repo_with_origin(tmp_path / "repo")
        caller_head_before = read_head_branch(repository_path)
        caller_commit_before = read_head_commit(repository_path)
        agent_scratch_parent = tmp_path / "agent-scratch"
        monkeypatch.setattr(module.sys, "platform", "linux")
        monkeypatch.setattr(
            module.tempfile,
            "gettempdir",
            lambda: str(agent_scratch_parent),
        )
        success_payload = module.create_fresh_branch(
            branch_name="fix/example-one",
            repo_path=repository_path,
            agent_slug="grok",
            base_ref=DEFAULT_BASE_REF,
        )
        worktree_path = Path(success_payload[PAYLOAD_KEY_WORKTREE_PATH])
        assert worktree_path.is_dir()
        assert worktree_path == agent_scratch_parent / "grok" / "fix" / "example-one"
        assert read_head_branch(worktree_path) == "fix/example-one"
        assert read_head_commit(worktree_path) == caller_commit_before
        assert success_payload[PAYLOAD_KEY_BRANCH] == "fix/example-one"
        assert success_payload[PAYLOAD_KEY_BASE_REF] == DEFAULT_BASE_REF
        assert success_payload[PAYLOAD_KEY_BASE_COMMIT] == caller_commit_before
        assert success_payload[PAYLOAD_KEY_AGENT] == "grok"
        assert Path(success_payload[PAYLOAD_KEY_REPO_ROOT]) == repository_path.resolve()
        assert read_head_branch(repository_path) == caller_head_before
        assert read_head_commit(repository_path) == caller_commit_before
        assert (worktree_path / SEED_FILE_NAME).read_text(encoding="utf-8") == (
            SEED_FILE_CONTENTS
        )

    def should_allocate_suffix_when_worktree_path_exists(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_create_fresh_branch_module()
        repository_path = build_repo_with_origin(tmp_path / "repo")
        agent_scratch_parent = tmp_path / "agent-scratch"
        monkeypatch.setattr(module.sys, "platform", "linux")
        monkeypatch.setattr(
            module.tempfile,
            "gettempdir",
            lambda: str(agent_scratch_parent),
        )
        occupied_path = agent_scratch_parent / "claude" / "fix" / "collision"
        occupied_path.mkdir(parents=True)
        success_payload = module.create_fresh_branch(
            branch_name="fix/collision",
            repo_path=repository_path,
            agent_slug="claude",
            base_ref=DEFAULT_BASE_REF,
        )
        worktree_path = Path(success_payload[PAYLOAD_KEY_WORKTREE_PATH])
        assert worktree_path == agent_scratch_parent / "claude" / "fix" / "collision-2"
        assert worktree_path.is_dir()
        assert read_head_branch(worktree_path) == "fix/collision"

    def should_fail_when_branch_already_exists(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_create_fresh_branch_module()
        repository_path = build_repo_with_origin(tmp_path / "repo")
        agent_scratch_parent = tmp_path / "agent-scratch"
        monkeypatch.setattr(module.sys, "platform", "linux")
        monkeypatch.setattr(
            module.tempfile,
            "gettempdir",
            lambda: str(agent_scratch_parent),
        )
        module.create_fresh_branch(
            branch_name="fix/dup",
            repo_path=repository_path,
            agent_slug="claude",
            base_ref=DEFAULT_BASE_REF,
        )
        with pytest.raises(RuntimeError, match="worktree add failed"):
            module.create_fresh_branch(
                branch_name="fix/dup",
                repo_path=repository_path,
                agent_slug="claude",
                base_ref=DEFAULT_BASE_REF,
            )

    def should_use_remote_tracking_tip_for_bare_base_name(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_create_fresh_branch_module()
        repository_path = build_repo_with_origin(tmp_path / "repo")
        empty_hooks_path = tmp_path / "repo" / "empty-hooks"
        origin_tip_before = read_head_commit(repository_path)
        (repository_path / SEED_FILE_NAME).write_text("local-only\n", encoding="utf-8")
        run_git(
            ["add", SEED_FILE_NAME],
            repository_path,
            empty_hooks_path=empty_hooks_path,
        )
        run_git(
            ["commit", "-m", "local advance"],
            repository_path,
            empty_hooks_path=empty_hooks_path,
        )
        local_main_commit = read_head_commit(repository_path)
        assert local_main_commit != origin_tip_before
        agent_scratch_parent = tmp_path / "agent-scratch"
        monkeypatch.setattr(module.sys, "platform", "linux")
        monkeypatch.setattr(
            module.tempfile,
            "gettempdir",
            lambda: str(agent_scratch_parent),
        )
        success_payload = module.create_fresh_branch(
            branch_name="fix/bare-base",
            repo_path=repository_path,
            agent_slug="claude",
            base_ref=MAIN_BRANCH_NAME,
        )
        worktree_path = Path(success_payload[PAYLOAD_KEY_WORKTREE_PATH])
        assert success_payload[PAYLOAD_KEY_BASE_REF] == DEFAULT_BASE_REF
        assert success_payload[PAYLOAD_KEY_BASE_COMMIT] == origin_tip_before
        assert read_head_commit(worktree_path) == origin_tip_before
        assert read_head_commit(worktree_path) != local_main_commit


class TestWorktreeBranchTracking:
    def should_leave_new_branch_without_an_upstream(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_create_fresh_branch_module()
        repository_path = build_repo_with_origin(tmp_path / "repo")
        agent_scratch_parent = tmp_path / "agent-scratch"
        monkeypatch.setattr(module.sys, "platform", "linux")
        monkeypatch.setattr(
            module.tempfile,
            "gettempdir",
            lambda: str(agent_scratch_parent),
        )
        success_payload = module.create_fresh_branch(
            branch_name="fix/no-upstream",
            repo_path=repository_path,
            agent_slug="claude",
            base_ref=DEFAULT_BASE_REF,
        )
        worktree_path = Path(success_payload[PAYLOAD_KEY_WORKTREE_PATH])
        assert read_head_branch(worktree_path) == "fix/no-upstream"
        assert read_branch_config(repository_path, "fix/no-upstream", "merge") == ""
        assert read_branch_config(repository_path, "fix/no-upstream", "remote") == ""

    def should_not_aim_a_bare_push_at_main_under_push_default_upstream(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        module = load_create_fresh_branch_module()
        repository_path = build_repo_with_origin(tmp_path / "repo")
        empty_hooks_path = tmp_path / "repo" / "empty-hooks"
        run_git(
            ["config", "push.default", "upstream"],
            repository_path,
            empty_hooks_path=empty_hooks_path,
        )
        agent_scratch_parent = tmp_path / "agent-scratch"
        monkeypatch.setattr(module.sys, "platform", "linux")
        monkeypatch.setattr(
            module.tempfile,
            "gettempdir",
            lambda: str(agent_scratch_parent),
        )
        success_payload = module.create_fresh_branch(
            branch_name="feature/silent-push",
            repo_path=repository_path,
            agent_slug="claude",
            base_ref=DEFAULT_BASE_REF,
        )
        worktree_path = Path(success_payload[PAYLOAD_KEY_WORKTREE_PATH])
        (worktree_path / SEED_FILE_NAME).write_text("drive-by\n", encoding="utf-8")
        run_git(["add", SEED_FILE_NAME], worktree_path, empty_hooks_path=empty_hooks_path)
        run_git(
            ["commit", "-m", "work on the feature branch"],
            worktree_path,
            empty_hooks_path=empty_hooks_path,
        )
        origin_main_before = read_remote_main_commit(repository_path)
        push_attempt = subprocess.run(
            ["git", "-c", f"core.hooksPath={empty_hooks_path}", "push"],
            cwd=str(worktree_path),
            check=False,
            capture_output=True,
            text=True,
        )
        assert push_attempt.returncode != 0, (
            "bare push should be refused, but it succeeded:\n"
            f"{push_attempt.stdout}{push_attempt.stderr}"
        )
        assert read_remote_main_commit(repository_path) == origin_main_before


class TestMainCli:
    def should_print_success_json_and_exit_zero(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        module = load_create_fresh_branch_module()
        repository_path = build_repo_with_origin(tmp_path / "repo")
        agent_scratch_parent = tmp_path / "agent-scratch"
        monkeypatch.setattr(module.sys, "platform", "linux")
        monkeypatch.setattr(
            module.tempfile,
            "gettempdir",
            lambda: str(agent_scratch_parent),
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "create_fresh_branch.py",
                "--branch-name",
                "feat/cli-ok",
                "--agent",
                "grok",
                "--repo",
                str(repository_path),
            ],
        )
        exit_code = module.main()
        captured = capsys.readouterr()
        assert exit_code == EXIT_CODE_SUCCESS
        success_payload = json.loads(captured.out)
        assert success_payload[PAYLOAD_KEY_BRANCH] == "feat/cli-ok"
        assert success_payload[PAYLOAD_KEY_AGENT] == "grok"
        assert Path(success_payload[PAYLOAD_KEY_WORKTREE_PATH]).is_dir()

    def should_print_error_json_and_exit_nonzero_for_bad_repo(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        module = load_create_fresh_branch_module()
        empty_directory = tmp_path / "not-a-repo"
        empty_directory.mkdir()
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "create_fresh_branch.py",
                "--branch-name",
                "feat/no-repo",
                "--repo",
                str(empty_directory),
                "--agent",
                "claude",
            ],
        )
        exit_code = module.main()
        captured = capsys.readouterr()
        assert exit_code == EXIT_CODE_FAILURE
        error_payload = json.loads(captured.out)
        assert PAYLOAD_KEY_ERROR in error_payload
        assert "git repository" in error_payload[PAYLOAD_KEY_ERROR]

    def should_print_error_json_when_branch_name_flag_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        module = load_create_fresh_branch_module()
        monkeypatch.setattr(sys, "argv", ["create_fresh_branch.py"])
        exit_code = module.main()
        captured = capsys.readouterr()
        assert exit_code == EXIT_CODE_FAILURE
        error_payload = json.loads(captured.out)
        assert error_payload[PAYLOAD_KEY_ERROR] == ERROR_CLI_ARGUMENTS

    def should_print_error_json_for_parent_segment_branch_name(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        module = load_create_fresh_branch_module()
        repository_path = build_repo_with_origin(tmp_path / "repo")
        agent_scratch_parent = tmp_path / "agent-scratch"
        agent_scratch_parent.mkdir()
        escaped_path = agent_scratch_parent / "escape"
        monkeypatch.setattr(module.sys, "platform", "linux")
        monkeypatch.setattr(
            module.tempfile,
            "gettempdir",
            lambda: str(agent_scratch_parent),
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "create_fresh_branch.py",
                "--branch-name",
                "../escape",
                "--repo",
                str(repository_path),
                "--agent",
                "claude",
            ],
        )
        exit_code = module.main()
        captured = capsys.readouterr()
        assert exit_code == EXIT_CODE_FAILURE
        error_payload = json.loads(captured.out)
        assert PAYLOAD_KEY_ERROR in error_payload
        assert "relative path" in error_payload[PAYLOAD_KEY_ERROR]
        assert not escaped_path.exists()
        assert not (agent_scratch_parent / "claude").exists()

    def should_print_error_json_for_absolute_branch_name(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        module = load_create_fresh_branch_module()
        repository_path = build_repo_with_origin(tmp_path / "repo")
        agent_scratch_parent = tmp_path / "agent-scratch"
        agent_scratch_parent.mkdir()
        outside_target = tmp_path / "outside-evil"
        monkeypatch.setattr(module.sys, "platform", "linux")
        monkeypatch.setattr(
            module.tempfile,
            "gettempdir",
            lambda: str(agent_scratch_parent),
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "create_fresh_branch.py",
                "--branch-name",
                str(outside_target),
                "--repo",
                str(repository_path),
                "--agent",
                "claude",
            ],
        )
        exit_code = module.main()
        captured = capsys.readouterr()
        assert exit_code == EXIT_CODE_FAILURE
        error_payload = json.loads(captured.out)
        assert PAYLOAD_KEY_ERROR in error_payload
        assert "relative path" in error_payload[PAYLOAD_KEY_ERROR]
        assert not outside_target.exists()
        assert not (agent_scratch_parent / "claude").exists()
