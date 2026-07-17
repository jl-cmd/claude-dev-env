"""Run validators that grade the whole project rather than one file."""

import subprocess
from pathlib import Path
from typing import List, Optional

from .validator_env import hooks_dir
from .validator_result import ValidatorResult
from .validator_subprocess import invoke_validator_module


def get_project_root() -> Optional[Path]:
    """Get project root by finding git root.

    Uses ``git -C <hooks_dir>`` to pin git's working tree to the hooks
    directory without setting the subprocess cwd. On Windows, ``CreateProcess``
    rejects some UNC working directories, so setting ``cwd=hooks_dir`` would
    fail when ``hooks_dir`` resolves to a UNC path. The ``-C`` flag tells git
    to operate as if started in that directory while the subprocess itself
    inherits a normal cwd from the caller. Anchoring git to ``hooks_dir`` is
    required so the lookup resolves to this repo even when the caller's cwd
    points at an unrelated git checkout (e.g., the user's home), avoiding
    validators that ``rglob`` over tens of thousands of unrelated files.
    """
    completed_git_lookup = subprocess.run(
        ["git", "-C", str(hooks_dir), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed_git_lookup.returncode == 0:
        return Path(completed_git_lookup.stdout.strip())
    return None


def run_file_structure_checks(project_root: Optional[Path] = None) -> ValidatorResult:
    """Run file structure checks on project."""
    if project_root is None:
        project_root = get_project_root()

    if project_root is None:
        return ValidatorResult(
            name="File Structure",
            checks="14,15",
            passed=True,
            output="Not in a git repository - skipping",
        )

    result = invoke_validator_module("file_structure_checks", [str(project_root)])

    return ValidatorResult(
        name="File Structure",
        checks="14,15",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
    )


def run_git_checks() -> ValidatorResult:
    """Run git/GitHub checks."""
    result = invoke_validator_module("git_checks", [])

    return ValidatorResult(
        name="Git/PR Workflow",
        checks="23,24",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
    )


def run_comment_checks(files: List[Path]) -> ValidatorResult:
    """Comment preservation is enforced by code_rules_enforcer hook.

    The hook compares old vs new content to block NEW comments and
    print a stderr advisory when an existing comment is removed. This
    standalone validator is disabled because it flags ALL comments in
    existing files, which forces agents to remove them to pass validation.
    """
    return ValidatorResult(
        name="No Comments",
        checks="26",
        passed=True,
        output="Handled by code_rules_enforcer hook (old vs new comparison)",
    )
