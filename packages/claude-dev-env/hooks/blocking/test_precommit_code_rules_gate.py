"""Behavior tests for the precommit_code_rules_gate PreToolUse hook.

Each test builds a real git repository in a temporary directory, stages
real files, and runs the hook script as a subprocess with a PreToolUse
JSON payload on stdin — the exact production invocation path.
"""

import json
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parent / "precommit_code_rules_gate.py"

CLEAN_MODULE_SOURCE = '''"""Increment helper used by the precommit gate tests."""


def add_one(number: int) -> int:
    """Return *number* plus one.

    Args:
        number: The integer to increment.

    Returns:
        The incremented integer.
    """
    return number + 1
'''

VIOLATING_MODULE_SOURCE = '''"""Module carrying a banned identifier for the precommit gate tests."""


def compute_total() -> int:
    """Return a fixed total.

    Returns:
        The fixed total.
    """
    result = 1
    return result
'''

WIDGET_MODULE_BASE_SOURCE = '''"""Arithmetic helpers used by the precommit gate worktree tests."""


def add_one(number: int) -> int:
    """Return *number* plus one.

    Args:
        number: The integer to increment.

    Returns:
        The incremented integer.
    """
    return number + 1
'''

WIDGET_MODULE_EXPANDED_SOURCE = '''"""Arithmetic helpers used by the precommit gate worktree tests."""


def add_one(number: int) -> int:
    """Return *number* plus one.

    Args:
        number: The integer to increment.

    Returns:
        The incremented integer.
    """
    return number + 1


def subtract_one(number: int) -> int:
    """Return *number* minus one.

    Args:
        number: The integer to decrement.

    Returns:
        The decremented integer.
    """
    return number - 1
'''

WIDGET_TEST_BASE_SOURCE = '''"""Behavior tests for the widget arithmetic helpers."""

from widget import add_one


def test_add_one_increments() -> None:
    """add_one returns its argument plus one."""
    assert add_one(1) == 2
'''

WIDGET_TEST_EXPANDED_SOURCE = '''"""Behavior tests for the widget arithmetic helpers."""

from widget import add_one, subtract_one


def test_add_one_increments() -> None:
    """add_one returns its argument plus one."""
    assert add_one(1) == 2


def test_subtract_one_decrements() -> None:
    """subtract_one returns its argument minus one."""
    assert subtract_one(2) == 1
'''


def run_git(repository_root: Path, *git_arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repository_root), *git_arguments],
        check=True,
        capture_output=True,
    )


def initialize_repository(repository_root: Path) -> None:
    run_git(repository_root, "init")
    run_git(repository_root, "config", "user.email", "tests@example.com")
    run_git(repository_root, "config", "user.name", "Gate Tests")
    run_git(repository_root, "commit", "--allow-empty", "-m", "initial")


def stage_file(repository_root: Path, relative_name: str, source_text: str) -> None:
    (repository_root / relative_name).write_text(source_text, encoding="utf-8")
    run_git(repository_root, "add", relative_name)


def run_hook(bash_command: str, working_directory: Path) -> subprocess.CompletedProcess[str]:
    payload = json.dumps({"tool_input": {"command": bash_command}})
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(working_directory),
        timeout=120,
    )


def parse_denial(hook_stdout: str) -> dict:
    return json.loads(hook_stdout)["hookSpecificOutput"]


def test_non_commit_command_passes_through(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    completed_hook = run_hook("git status", tmp_path)
    assert completed_hook.returncode == 0
    assert completed_hook.stdout.strip() == ""


def test_commit_with_clean_staged_python_file_is_allowed(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    stage_file(tmp_path, "incrementer.py", CLEAN_MODULE_SOURCE)
    completed_hook = run_hook("git commit -m add", tmp_path)
    assert completed_hook.returncode == 0
    assert completed_hook.stdout.strip() == ""


def test_commit_with_violating_staged_file_is_blocked(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    stage_file(tmp_path, "totals.py", VIOLATING_MODULE_SOURCE)
    completed_hook = run_hook("git commit -m add", tmp_path)
    assert completed_hook.returncode == 0
    denial = parse_denial(completed_hook.stdout)
    assert denial["permissionDecision"] == "deny"
    assert "totals.py" in denial["permissionDecisionReason"]
    assert "Line" in denial["permissionDecisionReason"]


def test_git_dash_c_commit_form_is_blocked(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    initialize_repository(repository_root)
    stage_file(repository_root, "totals.py", VIOLATING_MODULE_SOURCE)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    quoted_root = str(repository_root)
    completed_hook = run_hook(f'git -C "{quoted_root}" commit -m add', elsewhere)
    assert completed_hook.returncode == 0
    denial = parse_denial(completed_hook.stdout)
    assert denial["permissionDecision"] == "deny"
    assert "totals.py" in denial["permissionDecisionReason"]


def test_commit_with_no_staged_python_files_is_allowed(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    stage_file(tmp_path, "notes.md", "# Notes\n")
    completed_hook = run_hook("git commit -m docs", tmp_path)
    assert completed_hook.returncode == 0
    assert completed_hook.stdout.strip() == ""


def test_worktree_commit_reads_worktree_paired_tests_not_sibling_checkout(
    tmp_path: Path,
) -> None:
    main_checkout = tmp_path / "main_checkout"
    main_checkout.mkdir()
    initialize_repository(main_checkout)
    (main_checkout / "widget.py").write_text(WIDGET_MODULE_BASE_SOURCE, encoding="utf-8")
    (main_checkout / "test_widget.py").write_text(WIDGET_TEST_BASE_SOURCE, encoding="utf-8")
    run_git(main_checkout, "add", "widget.py", "test_widget.py")
    run_git(main_checkout, "commit", "-m", "base")
    worktree_root = tmp_path / "sibling_worktree"
    run_git(main_checkout, "worktree", "add", str(worktree_root), "-b", "feature")
    stage_file(worktree_root, "widget.py", WIDGET_MODULE_EXPANDED_SOURCE)
    stage_file(worktree_root, "test_widget.py", WIDGET_TEST_EXPANDED_SOURCE)
    quoted_worktree = str(worktree_root)
    completed_hook = run_hook(
        f'git -C "{quoted_worktree}" commit -m expand', main_checkout
    )
    assert completed_hook.returncode == 0
    assert completed_hook.stdout.strip() == ""
