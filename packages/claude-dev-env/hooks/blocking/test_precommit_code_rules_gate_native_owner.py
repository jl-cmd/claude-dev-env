"""Production-path tests for native staged-gate ownership.

The tests run the Agent Bash dispatcher and a native Git pre-commit hook against
the same isolated repository. The agent path passes the commit through. The
native path runs the staged gate and controls the commit.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_ROOT = Path(__file__).resolve().parent.parent
BLOCKING_ROOT = HOOKS_ROOT / "blocking"
GIT_HOOKS_ROOT = HOOKS_ROOT / "git-hooks"
DISPATCHER_SOURCE_PATH = BLOCKING_ROOT / "bash_pre_tool_use_dispatcher.py"
GIT_COMMAND_TIMEOUT_SECONDS = 60
CLEAN_MODULE_SOURCE = (
    "def add_one(number: int) -> int:\n"
    '    """Increase the number.\n\n'
    "    Args:\n        number: The input number.\n\n"
    "    Returns:\n        The next number.\n"
    '    """\n'
    "    return number + 1\n"
)
PAIRED_TEST_SOURCE = (
    "from widget import add_one\n\n"
    "def test_add_one() -> None:\n    assert add_one(1) == 2\n"
)


def run_git(
    repository_root: Path,
    *git_arguments: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run one isolated Git command and return its captured process record."""
    return subprocess.run(
        ["git", *git_arguments],
        cwd=str(repository_root),
        check=check,
        capture_output=True,
        text=True,
        timeout=GIT_COMMAND_TIMEOUT_SECONDS,
    )


def initialize_repository(repository_root: Path) -> None:
    """Create a repository with one committed base file and no active hook."""
    run_git(repository_root, "init")
    run_git(repository_root, "config", "user.name", "Hook Test")
    run_git(repository_root, "config", "user.email", "hook-test@example.invalid")
    run_git(repository_root, "config", "core.hooksPath", "absent_fixture_hooks")
    (repository_root / "README.md").write_text("base\n", encoding="utf-8")
    run_git(repository_root, "add", "README.md")
    run_git(repository_root, "commit", "-m", "base")


def write_gate_script(gate_path: Path, marker_path: Path, exit_code: int) -> None:
    """Write a staged-gate fixture that records arguments and exits."""
    gate_path.write_text(
        "import pathlib\n"
        "import sys\n"
        f"pathlib.Path({str(marker_path)!r}).write_text("
        "'\\n'.join(sys.argv[1:]), encoding='utf-8')\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8",
    )


def install_native_pre_commit(hooks_path: Path) -> None:
    """Register the actual package owner with its complete linter dependency tree."""
    hooks_path.mkdir()
    pre_commit_path = hooks_path / "pre-commit"
    pre_commit_path.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"sys.path.insert(0, {str(GIT_HOOKS_ROOT)!r})\n"
        "import pre_commit\n"
        "sys.exit(pre_commit.main())\n",
        encoding="utf-8",
    )
    pre_commit_path.chmod(pre_commit_path.stat().st_mode | stat.S_IXUSR)


def configured_hooks_path(repository_root: Path) -> str | None:
    """Return the repository-local hooks path when one is configured."""
    completed_config = run_git(
        repository_root,
        "config",
        "--local",
        "--get",
        "core.hooksPath",
        check=False,
    )
    if completed_config.returncode != 0:
        return None
    return completed_config.stdout.strip()


def restore_hooks_path(repository_root: Path, prior_hooks_path: str | None) -> None:
    """Restore the repository-local hooks path captured before a benchmark."""
    if prior_hooks_path is None:
        run_git(
            repository_root,
            "config",
            "--local",
            "--unset-all",
            "core.hooksPath",
            check=False,
        )
        return
    run_git(repository_root, "config", "--local", "core.hooksPath", prior_hooks_path)


@contextmanager
def temporary_hooks_path(repository_root: Path, benchmark_hooks_path: Path) -> Iterator[None]:
    """Apply a benchmark hooks path and restore the prior local setting."""
    prior_hooks_path = configured_hooks_path(repository_root)
    run_git(repository_root, "config", "--local", "core.hooksPath", str(benchmark_hooks_path))
    try:
        yield
    finally:
        restore_hooks_path(repository_root, prior_hooks_path)


def stage_module(repository_root: Path) -> None:
    """Stage a valid module and matching test before exercising the legacy gate."""
    (repository_root / "widget.py").write_text(CLEAN_MODULE_SOURCE, encoding="utf-8")
    (repository_root / "test_widget.py").write_text(PAIRED_TEST_SOURCE, encoding="utf-8")
    run_git(repository_root, "add", "widget.py", "test_widget.py")


def build_bash_payload(repository_root: Path) -> str:
    """Build the Bash dispatcher payload for a commit in the fixture repository."""
    commit_command = f'git -C "{repository_root}" commit -m add'
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": commit_command}})


def run_agent_dispatcher(repository_root: Path) -> subprocess.CompletedProcess[str]:
    """Run the production Bash dispatcher against the fixture commit command."""
    return subprocess.run(
        [sys.executable, str(DISPATCHER_SOURCE_PATH)],
        cwd=str(repository_root),
        input=build_bash_payload(repository_root),
        capture_output=True,
        text=True,
        timeout=GIT_COMMAND_TIMEOUT_SECONDS,
    )


def run_native_commit(repository_root: Path) -> subprocess.CompletedProcess[str]:
    """Run the real Git commit that invokes the configured native hook."""
    return run_git(
        repository_root,
        "commit",
        "-m",
        "add widget",
        check=False,
    )


def test_agent_dispatcher_passes_commit_through_without_running_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Agent Bash path continues the commit without running the staged gate."""
    initialize_repository(tmp_path)
    stage_module(tmp_path)
    gate_marker_path = tmp_path / "agent_gate_invocation.txt"
    gate_path = tmp_path / "agent_gate.py"
    write_gate_script(gate_path, gate_marker_path, exit_code=1)
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(gate_path))

    completed_dispatcher = run_agent_dispatcher(tmp_path)

    assert completed_dispatcher.returncode == 0, completed_dispatcher.stderr
    assert completed_dispatcher.stdout.strip() == ""
    assert not gate_marker_path.exists()


@pytest.mark.parametrize("gate_exit_code, expected_commit_exit_code", [(1, 1), (0, 0)])
def test_installed_native_pre_commit_controls_staged_gate_decision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    gate_exit_code: int,
    expected_commit_exit_code: int,
) -> None:
    """The native Git hook runs the staged gate and returns its commit decision."""
    initialize_repository(tmp_path)
    native_hooks_path = tmp_path / "native_hooks"
    install_native_pre_commit(native_hooks_path)
    stage_module(tmp_path)
    gate_marker_path = tmp_path / "native_gate_invocation.txt"
    gate_path = tmp_path / "native_gate.py"
    write_gate_script(gate_path, gate_marker_path, gate_exit_code)
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(gate_path))

    with temporary_hooks_path(tmp_path, native_hooks_path):
        completed_commit = run_native_commit(tmp_path)

    assert completed_commit.returncode == expected_commit_exit_code
    assert gate_marker_path.read_text(encoding="utf-8") == "--immediate"


def test_temporary_hooks_path_restores_shared_worktree_config_on_timeout(
    tmp_path: Path,
) -> None:
    initialize_repository(tmp_path)
    supported_hooks_path = tmp_path / "supported_hooks"
    supported_hooks_path.mkdir()
    run_git(tmp_path, "config", "core.hooksPath", str(supported_hooks_path))
    unrelated_worktree = tmp_path.parent / "unrelated_worktree"
    run_git(tmp_path, "worktree", "add", "--detach", str(unrelated_worktree))
    benchmark_hooks_path = tmp_path / "benchmark_hooks"
    benchmark_hooks_path.mkdir()

    try:
        with pytest.raises(subprocess.TimeoutExpired):
            with temporary_hooks_path(tmp_path, benchmark_hooks_path):
                raise subprocess.TimeoutExpired("benchmark", 1)

        assert configured_hooks_path(tmp_path) == str(supported_hooks_path)
        assert configured_hooks_path(unrelated_worktree) == str(supported_hooks_path)
    finally:
        run_git(tmp_path, "worktree", "remove", "--force", str(unrelated_worktree))
