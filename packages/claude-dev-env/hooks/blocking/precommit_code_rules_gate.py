"""PreToolUse hook that records the staged Python surface.

Intercepts Bash `git commit` invocations (including `git -C <path> commit`),
resolves the repository root, and counts staged Python files. This agent
surface emits passive staged-surface evidence for the commit path.
"""

import re
import subprocess
import sys
from pathlib import Path

_blocking_dir = str(Path(__file__).resolve().parent)
if _blocking_dir not in sys.path:
    sys.path.insert(0, _blocking_dir)
_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from block_main_commit import (  # noqa: E402
    extract_git_working_directory,
    is_commit_command,
    parse_bash_command_from_stdin,
    resolve_directory,
)

from hooks_constants.precommit_code_rules_gate_constants import (  # noqa: E402
    ALL_GIT_REPOSITORY_ROOT_COMMAND,
    ALL_STAGED_PYTHON_FILES_COMMAND,
    GIT_COMMAND_TIMEOUT_SECONDS,
    GIT_DASH_C_COMMIT_PATTERN,
)


def is_git_commit_invocation(bash_command: str) -> bool:
    """Report whether *bash_command* runs a git commit.

    Matches both the plain ``git commit`` substring form and the
    ``git -C <path> commit`` form, where the directory flag sits between
    the two words.

    Args:
        bash_command: The Bash tool command string from the hook payload.

    Returns:
        True when the command invokes git commit; False otherwise.
    """
    if is_commit_command(bash_command):
        return True
    return re.search(GIT_DASH_C_COMMIT_PATTERN, bash_command) is not None


def resolve_repository_root(working_directory: str | None) -> Path | None:
    """Resolve the git repository root for the commit's working directory.

    Args:
        working_directory: Directory the commit runs in, or None for the
            hook's current working directory.

    Returns:
        The repository root path, or None when the directory is not inside
        a git repository or git is unavailable.
    """
    try:
        completed_process = subprocess.run(
            list(ALL_GIT_REPOSITORY_ROOT_COMMAND),
            check=False, capture_output=True,
            text=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            cwd=working_directory,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if completed_process.returncode != 0:
        return None
    top_level_text = completed_process.stdout.strip()
    if not top_level_text:
        return None
    return Path(top_level_text)


def count_staged_python_files(repository_root: Path) -> int:
    """Count repository-relative paths of staged Python files.

    Args:
        repository_root: Repository root used as the git working directory.

    Returns:
        Number of Python files staged for add, copy, modify, or rename.
        Returns zero when the listing command fails, so Git can surface the
        repository problem.
    """
    try:
        completed_process = subprocess.run(
            list(ALL_STAGED_PYTHON_FILES_COMMAND),
            check=False, capture_output=True,
            text=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            cwd=str(repository_root),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return 0
    if completed_process.returncode != 0:
        return 0
    return sum(
        1
        for each_line in completed_process.stdout.splitlines()
        if each_line.strip()
    )


def main() -> None:
    """Record staged-surface evidence for Git commits."""
    bash_command = parse_bash_command_from_stdin()
    if not is_git_commit_invocation(bash_command):
        sys.exit(0)
    working_directory = resolve_directory(extract_git_working_directory(bash_command))
    repository_root = resolve_repository_root(working_directory)
    if repository_root is None:
        sys.exit(0)
    staged_python_file_count = count_staged_python_files(repository_root)
    if staged_python_file_count == 0:
        sys.exit(0)
    sys.stderr.write(f"Staged Python files: {staged_python_file_count}.\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
