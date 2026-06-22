"""PreToolUse hook that runs the staged CODE_RULES gate before git commit.

Intercepts Bash `git commit` invocations (including `git -C <path> commit`),
resolves the repository root, and runs the shared code_rules_gate engine in
``--staged`` mode over the staged files. A commit that would introduce
CODE_RULES violations is denied with the gate's file:line report so the
violations surface before the commit instead of stalling converge loops at
commit time. Non-commit commands, repositories with no staged Python files,
and clean staged changes pass through silently. A gate-engine failure denies
the commit with the failure detail — the gate never fails open.
"""

import json
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
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.precommit_code_rules_gate_constants import (  # noqa: E402
    ALL_GIT_REPOSITORY_ROOT_COMMAND,
    ALL_STAGED_PYTHON_FILES_COMMAND,
    GATE_RELATIVE_PATH,
    GATE_TIMEOUT_SECONDS,
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
            capture_output=True,
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


def list_staged_python_files(repository_root: Path) -> list[str]:
    """List repository-relative paths of staged Python files.

    Args:
        repository_root: Repository root used as the git working directory.

    Returns:
        Repository-relative paths of Python files staged for add, copy,
        modify, or rename. Empty when the listing command fails — the
        caller then allows the commit because git itself will surface the
        repository problem.
    """
    try:
        completed_process = subprocess.run(
            list(ALL_STAGED_PYTHON_FILES_COMMAND),
            capture_output=True,
            text=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            cwd=str(repository_root),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []
    if completed_process.returncode != 0:
        return []
    return [
        each_line.strip()
        for each_line in completed_process.stdout.splitlines()
        if each_line.strip()
    ]


def run_staged_gate(repository_root: Path) -> tuple[int, str]:
    """Run the shared code_rules_gate engine in staged mode.

    Args:
        repository_root: Repository root passed to the gate's --repo-root.

    Returns:
        Tuple of the gate exit code and its stderr report. A missing gate
        script or a gate timeout returns a non-zero code with an
        explanatory message so the commit is denied rather than waved
        through on infrastructure failure.
    """
    gate_path = Path(__file__).resolve().parents[2] / GATE_RELATIVE_PATH
    if not gate_path.is_file():
        return 1, f"precommit_code_rules_gate: gate engine missing at {gate_path}"
    try:
        completed_process = subprocess.run(
            [
                sys.executable,
                str(gate_path),
                "--repo-root",
                str(repository_root),
                "--staged",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GATE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return 1, (
            f"precommit_code_rules_gate: gate engine timed out after {GATE_TIMEOUT_SECONDS}s"
        )
    return completed_process.returncode, completed_process.stderr


def build_denial_response(gate_report: str) -> dict:
    """Build the PreToolUse deny payload carrying the gate report.

    Args:
        gate_report: The gate's stderr report listing file:line violations.

    Returns:
        The hookSpecificOutput deny mapping for the PreToolUse protocol.
    """
    denial_reason = (
        f"BLOCKED: staged files violate CODE_RULES; fix before committing.\n{gate_report.strip()}"
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": denial_reason,
        }
    }


def main() -> None:
    """Gate git commits on the staged CODE_RULES report."""
    bash_command = parse_bash_command_from_stdin()
    if not is_git_commit_invocation(bash_command):
        sys.exit(0)
    working_directory = resolve_directory(extract_git_working_directory(bash_command))
    repository_root = resolve_repository_root(working_directory)
    if repository_root is None:
        sys.exit(0)
    if not list_staged_python_files(repository_root):
        sys.exit(0)
    gate_exit_code, gate_report = run_staged_gate(repository_root)
    if gate_exit_code == 0:
        sys.exit(0)
    denial = build_denial_response(gate_report)
    log_hook_block(
        calling_hook_name="precommit_code_rules_gate.py",
        hook_event="PreToolUse",
        block_reason=denial["hookSpecificOutput"]["permissionDecisionReason"],
        tool_name="Bash",
        offending_input_preview=bash_command,
    )
    print(json.dumps(denial))
    sys.exit(0)


if __name__ == "__main__":
    main()
