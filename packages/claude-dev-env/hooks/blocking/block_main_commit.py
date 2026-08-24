"""
PreToolUse hook that blocks direct commits to main/master branch in any git project.
Requires explicit user confirmation before allowing the commit.

Handles commits in any directory context:
- Plain `git commit` (uses CWD)
- `cd /path && git commit` or `cd /path; git commit`
- `pushd /path && git commit`
- `git -C /path commit`
- Quoted and tilde-expanded paths
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402

GIT_COMMAND_TIMEOUT_SECONDS = 5
PROTECTED_BRANCHES = ("main", "master")
PROTECTED_REMOTE_PATTERNS: list[str] = []


def parse_git_commit_directory(bash_command: str) -> tuple[bool, str | None]:
    """Return the Git commit match state and selected working directory."""
    git_c_match = re.search(
        r"(?:^|(?<=[;&|]))\s*git\s+-C\s+[\"']?([^\"';&|]+?)[\"']?\s+commit(?:\s|$)",
        bash_command,
        flags=re.IGNORECASE,
    )
    if git_c_match:
        return True, git_c_match.group(1).strip()

    git_commit_match = re.search(
        r"(?:^|(?<=[;&|]))\s*git\s+commit(?:\s|$)",
        bash_command,
        flags=re.IGNORECASE,
    )
    if git_commit_match is None:
        return False, None

    prefix = bash_command[:git_commit_match.start()]

    cd_matches = re.findall(
        r"(?:cd|pushd)\s+[\"']?([^\"';&|]+?)[\"']?\s*[;&|]",
        prefix,
        flags=re.IGNORECASE,
    )
    if cd_matches:
        return True, cd_matches[-1].strip()

    return True, None


def extract_git_working_directory(bash_command: str) -> str | None:
    """Return the working directory selected by a Git commit command."""
    _, working_directory = parse_git_commit_directory(bash_command)
    return working_directory


def is_commit_command(bash_command: str) -> bool:
    """Return the Git commit match state for the shell command."""
    is_commit, _ = parse_git_commit_directory(bash_command)
    return is_commit


def resolve_directory(
    directory: str | None,
    from_directory: str | None = None,
) -> str | None:
    """Resolve a directory path, expanding ~ and validating existence."""
    selected_directory = directory if directory is not None else from_directory
    if selected_directory is None:
        return None

    expanded = os.path.expanduser(selected_directory)

    if not os.path.isabs(expanded):
        base_directory = from_directory or os.getcwd()
        expanded = os.path.abspath(os.path.join(base_directory, expanded))

    if os.path.isdir(expanded):
        return expanded

    return None


def get_branch_at_directory(working_dir: str | None = None) -> str | None:
    """Get the current git branch at a specific directory."""
    try:
        completed_process = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=False, capture_output=True,
            text=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            cwd=working_dir,
        )
        if completed_process.returncode == 0:
            return completed_process.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return None


def is_protected_repo(working_dir: str | None = None) -> bool:
    if not PROTECTED_REMOTE_PATTERNS:
        return True
    try:
        completed_process = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            check=False, capture_output=True,
            text=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            cwd=working_dir,
        )
        if completed_process.returncode == 0:
            remote_url = completed_process.stdout.strip()
            return any(pattern in remote_url for pattern in PROTECTED_REMOTE_PATTERNS)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return False


def is_main_commit_confirmed(bash_command: str) -> bool:
    """Return True if the command includes the explicit confirmation sentinel."""
    return "--allow-main-commit" in bash_command


def parse_hook_context_from_stdin() -> tuple[str, str | None]:
    try:
        hook_event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return "", None

    bash_command = hook_event.get("tool_input", {}).get("command", "")
    return bash_command, hook_event.get("cwd")


def parse_bash_command_from_stdin() -> str:
    """Return the Bash command from the hook payload on standard input."""
    bash_command, _ = parse_hook_context_from_stdin()
    return bash_command


DRAFT_PR_INSTRUCTION = (
    " Instead: (1) create a feature branch with `git checkout -b <descriptive-branch-name>`, "
    "(2) commit your changes there, "
    "(3) push with `git push -u origin <branch-name>`, "
    "(4) create a draft PR with `gh pr create --draft`. "
    "If you must commit to main, the user needs to approve explicitly."
)


def build_denial_response(branch_name: str, repo_dir: str | None) -> dict:
    location = f" in {repo_dir}" if repo_dir else ""
    denial_reason = (
        f"BLOCKED: Direct commit to '{branch_name}'{location} is not allowed."
        + DRAFT_PR_INSTRUCTION
    )

    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": denial_reason,
        }
    }


def main() -> None:
    bash_command, event_cwd = parse_hook_context_from_stdin()
    has_commit_command, target_dir_raw = parse_git_commit_directory(bash_command)

    if not has_commit_command:
        sys.exit(0)

    if is_main_commit_confirmed(bash_command):
        sys.exit(0)

    target_dir = resolve_directory(target_dir_raw, from_directory=event_cwd)

    if (target_dir_raw or event_cwd) and not target_dir:
        sys.exit(0)

    current_branch = get_branch_at_directory(working_dir=target_dir)

    if current_branch not in PROTECTED_BRANCHES:
        sys.exit(0)

    if not is_protected_repo(working_dir=target_dir):
        sys.exit(0)

    denial = build_denial_response(current_branch, target_dir)
    log_hook_block(
        calling_hook_name="block_main_commit.py",
        hook_event="PreToolUse",
        block_reason=denial["hookSpecificOutput"]["permissionDecisionReason"],
        tool_name="Bash",
        offending_input_preview=bash_command,
    )
    print(json.dumps(denial))
    sys.exit(0)


if __name__ == "__main__":
    main()
