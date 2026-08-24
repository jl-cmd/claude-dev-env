"""Production-path tests for direct commit branch protection."""

import json
import os
from pathlib import Path
import subprocess
import sys


def _run_git(from_directory: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", *arguments],
        cwd=from_directory,
        check=True,
        capture_output=True,
        text=True,
    )


def _create_repository(from_directory: Path, branch_name: str) -> Path:
    repository = from_directory / branch_name
    repository.mkdir()
    _run_git(repository, "init", "--initial-branch", "main")
    hook_directory = repository / ".git" / "test-hooks"
    hook_directory.mkdir()
    _run_git(repository, "config", "core.hooksPath", str(hook_directory))
    _run_git(repository, "config", "user.email", "test@example.com")
    _run_git(repository, "config", "user.name", "Test User")
    (repository / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    _run_git(repository, "add", "tracked.txt")
    _run_git(repository, "-c", "commit.gpgsign=false", "commit", "-m", "initial")
    if branch_name != "main":
        _run_git(repository, "switch", "-c", branch_name)
    return repository


def _run_commit_gate(
    from_directory: Path,
    process_directory: Path,
    command: str = "git commit -m test",
) -> subprocess.CompletedProcess[str]:
    hook_script = Path(__file__).with_name("block_main_commit.py")
    home_directory = from_directory.parent / "test-home"
    home_directory.mkdir(exist_ok=True)
    environment = os.environ.copy()
    environment.update({"HOME": str(home_directory), "USERPROFILE": str(home_directory)})
    hook_payload = {
        "tool_name": "Bash",
        "cwd": str(from_directory),
        "tool_input": {"command": command},
    }
    return subprocess.run(
        [sys.executable, str(hook_script)],
        cwd=process_directory,
        input=json.dumps(hook_payload),
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_blocks_commit_on_protected_branch_from_hook_event_cwd(tmp_path: Path) -> None:
    repository = _create_repository(tmp_path, "main")
    process_repository = _create_repository(tmp_path, "agent-owned-change")

    completed_process = _run_commit_gate(repository, process_repository)

    assert completed_process.returncode == 0
    hook_response = json.loads(completed_process.stdout)
    assert hook_response["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert str(repository) in hook_response["hookSpecificOutput"]["permissionDecisionReason"]


def test_allows_commit_on_owned_branch_from_hook_event_cwd(tmp_path: Path) -> None:
    repository = _create_repository(tmp_path, "agent-owned-change")
    process_repository = _create_repository(tmp_path, "main")

    completed_process = _run_commit_gate(repository, process_repository)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_resolves_relative_git_c_from_hook_event_cwd(tmp_path: Path) -> None:
    repository = _create_repository(tmp_path, "main")
    process_repository = _create_repository(tmp_path, "agent-owned-change")

    completed_process = _run_commit_gate(
        tmp_path,
        process_repository,
        command="git -C main commit -m test",
    )

    assert completed_process.returncode == 0
    hook_response = json.loads(completed_process.stdout)
    assert hook_response["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert str(repository) in hook_response["hookSpecificOutput"]["permissionDecisionReason"]


def test_matches_case_insensitive_shell_git_command(tmp_path: Path) -> None:
    repository = _create_repository(tmp_path, "main")
    process_repository = _create_repository(tmp_path, "agent-owned-change")

    completed_process = _run_commit_gate(
        tmp_path,
        process_repository,
        command="CD main && GIT COMMIT -m test",
    )

    assert completed_process.returncode == 0
    hook_response = json.loads(completed_process.stdout)
    assert hook_response["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert str(repository) in hook_response["hookSpecificOutput"]["permissionDecisionReason"]


def test_ignores_unrelated_command_containing_git_commit(tmp_path: Path) -> None:
    repository = _create_repository(tmp_path, "main")
    process_repository = _create_repository(tmp_path, "agent-owned-change")

    completed_process = _run_commit_gate(
        repository,
        process_repository,
        command="echo git commit",
    )

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""
