"""Agent-home tooling exemption tests for the classifier and the enforcer.

A coding agent installs its own helper scripts under a dot-directory in the
user's home — ``~/.grok/runs/`` sits beside the already-exempt
``~/.claude/hooks/``. That tree is vendored tooling rather than project code,
so the repository code rules do not govern it::

    /home/example/.grok/runs/worktree-health/health.py  -> exempt
    C:/dev/my-project/src/grokking.py               -> governed
"""

from __future__ import annotations

import os
from subprocess import CompletedProcess
import tempfile
from pathlib import Path

import pytest

from blocking import _path_setup  # noqa: F401  (pins this checkout ahead of sibling worktrees)
import code_rules_enforcer_test_support
from blocking.code_rules_shared import is_agent_home_tooling, is_ephemeral_path
from code_rules_enforcer_test_support import run_precheck

_VIOLATING_PRODUCTION_SOURCE = "def process_data(payload: str) -> None:\n    print(payload)\n"


def _check_as(candidate_source: str, target_path: str) -> CompletedProcess[str]:
    """Run the enforcer's pre-check on a candidate judged as another path.

    Args:
        candidate_source: Python source written to the candidate file.
        target_path: Destination path the candidate is judged as.

    Returns:
        The completed process carrying stdout, stderr, and the exit code.
    """
    with tempfile.TemporaryDirectory() as scratch:
        candidate = Path(scratch) / "candidate.py"
        candidate.write_text(candidate_source, encoding="utf-8")
        return run_precheck(candidate, target_path, None)


def test_run_precheck_forwards_environment_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_environment_by_name = {"CLAUDE_JOB_DIR": "/agent/jobs"}
    captured_environment_by_name: dict[str, str] | None = None

    def capture_run_enforcer_cli(
        _script_path: Path,
        _all_arguments: list[str],
        extra_environment_by_name: dict[str, str] | None,
    ) -> CompletedProcess[str]:
        nonlocal captured_environment_by_name
        captured_environment_by_name = extra_environment_by_name
        return CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        code_rules_enforcer_test_support,
        "run_enforcer_cli",
        capture_run_enforcer_cli,
    )
    completed = run_precheck(
        Path("candidate.py"),
        "target.py",
        expected_environment_by_name,
    )

    assert completed.returncode == 0
    assert captured_environment_by_name == {"CLAUDE_JOB_DIR": "/agent/jobs"}


def test_posix_agent_home_path_is_agent_tooling() -> None:
    assert is_agent_home_tooling("/home/example/.grok/runs/worktree-health/health.py")


def test_windows_agent_home_path_is_agent_tooling() -> None:
    assert is_agent_home_tooling(r"C:\Users\example\.grok\runs\worktree-health\health.py")


def test_any_depth_under_the_agent_home_is_agent_tooling() -> None:
    assert is_agent_home_tooling("/home/example/.grok/hooks/force_worktree.py")


def test_ordinary_project_code_is_not_agent_tooling() -> None:
    assert not is_agent_home_tooling("/dev/my-project/src/service.py")


def test_a_filename_spelled_like_the_agent_is_not_agent_tooling() -> None:
    assert not is_agent_home_tooling("/dev/my-project/src/grokking.py")


def test_a_directory_without_the_leading_dot_is_not_agent_tooling() -> None:
    assert not is_agent_home_tooling("/dev/my-project/grok/runner.py")


def test_an_empty_path_is_not_agent_tooling() -> None:
    assert not is_agent_home_tooling("")


def test_agent_home_path_is_exempt_from_the_repository_gates() -> None:
    assert is_ephemeral_path("/home/example/.grok/runs/worktree-health/health.py")


def test_project_code_is_not_exempt_from_the_repository_gates() -> None:
    assert not is_ephemeral_path("/dev/my-project/src/service.py")


def test_enforcer_allows_violating_source_under_the_agent_home() -> None:
    target = os.path.join("/home/example", ".grok", "runs", "worktree-health", "health.py")

    completed = _check_as(_VIOLATING_PRODUCTION_SOURCE, target)

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_enforcer_still_flags_the_same_source_in_a_project_path() -> None:
    target = os.path.join("/dev/my-project", "src", "service.py")

    completed = _check_as(_VIOLATING_PRODUCTION_SOURCE, target)

    assert completed.returncode != 0
