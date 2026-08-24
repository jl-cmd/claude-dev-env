"""Production-path tests for native staged-gate ownership.

The tests run the Agent Bash dispatcher and a native Git pre-commit hook against
the same isolated repository. The agent path passes the commit through. The
native path runs the staged gate and controls the commit.
"""

from __future__ import annotations

import json
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_ROOT = Path(__file__).resolve().parent.parent
BLOCKING_ROOT = HOOKS_ROOT / "blocking"
GIT_HOOKS_ROOT = HOOKS_ROOT / "git-hooks"
PRE_COMMIT_SOURCE_PATH = GIT_HOOKS_ROOT / "pre_commit.py"
GATE_UTILS_SOURCE_PATH = GIT_HOOKS_ROOT / "gate_utils.py"
GIT_HOOKS_CONSTANTS_SOURCE_PATH = GIT_HOOKS_ROOT / "git_hooks_constants"
DISPATCHER_SOURCE_PATH = BLOCKING_ROOT / "bash_pre_tool_use_dispatcher.py"
GIT_COMMAND_TIMEOUT_SECONDS = 60
CLEAN_MODULE_SOURCE = "def add_one(number: int) -> int:\n    return number + 1\n"


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


def install_native_pre_commit(repository_root: Path, hooks_path: Path) -> None:
    """Install the native pre-commit module and its self-contained imports."""
    hooks_path.mkdir()
    shutil.copyfile(PRE_COMMIT_SOURCE_PATH, hooks_path / "pre_commit.py")
    shutil.copyfile(GATE_UTILS_SOURCE_PATH, hooks_path / "gate_utils.py")
    shutil.copytree(
        GIT_HOOKS_CONSTANTS_SOURCE_PATH,
        hooks_path / "git_hooks_constants",
    )
    pre_commit_path = hooks_path / "pre-commit"
    pre_commit_path.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "from pathlib import Path\n"
        "shim_directory = Path(__file__).resolve().parent\n"
        "sys.path.insert(0, str(shim_directory))\n"
        "import pre_commit\n"
        "sys.exit(pre_commit.main())\n",
        encoding="utf-8",
    )
    pre_commit_path.chmod(pre_commit_path.stat().st_mode | stat.S_IXUSR)
    run_git(repository_root, "config", "core.hooksPath", str(hooks_path))


def stage_module(repository_root: Path) -> None:
    """Write and stage one Python module for the commit fixture."""
    (repository_root / "widget.py").write_text(CLEAN_MODULE_SOURCE, encoding="utf-8")
    run_git(repository_root, "add", "widget.py")


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
    assert "Git commit proceeds to configured Git hooks." in completed_dispatcher.stderr
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
    install_native_pre_commit(tmp_path, native_hooks_path)
    stage_module(tmp_path)
    gate_marker_path = tmp_path / "native_gate_invocation.txt"
    gate_path = tmp_path / "native_gate.py"
    write_gate_script(gate_path, gate_marker_path, gate_exit_code)
    monkeypatch.setenv("CODE_RULES_GATE_PATH", str(gate_path))

    completed_commit = run_native_commit(tmp_path)

    assert completed_commit.returncode == expected_commit_exit_code
    assert gate_marker_path.read_text(encoding="utf-8") == "--staged"
