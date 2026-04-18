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

GIT_COMMAND_TIMEOUT_SECONDS = 5
PROTECTED_BRANCHES = ("main", "master")
PROTECTED_REMOTE_PATTERNS: list[str] = []


def extract_git_working_directory(bash_command: str) -> str | None:
    """Extract the directory where git commit will actually execute.

    Parses the bash command for directory-changing patterns that precede
    the git commit, and for git's own -C flag.

    Returns None if the commit runs in the hook's CWD.
    """
    git_c_match = re.search(
        r"git\s+-C\s+[\"']?([^\"';&|]+?)[\"']?\s+commit",
        bash_command,
    )
    if git_c_match:
        return git_c_match.group(1).strip()

    commit_pos = bash_command.lower().find("git commit")
    if commit_pos == -1:
        return None

    prefix = bash_command[:commit_pos]

    cd_matches = re.findall(
        r"(?:cd|pushd)\s+[\"']?([^\"';&|]+?)[\"']?\s*[;&|]",
        prefix,
    )
    if cd_matches:
        return cd_matches[-1].strip()

    return None


def resolve_directory(directory: str | None) -> str | None:
    """Resolve a directory path, expanding ~ and validating existence."""
    if directory is None:
        return None

    expanded = os.path.expanduser(directory)

    if not os.path.isabs(expanded):
        expanded = os.path.abspath(expanded)

    if os.path.isdir(expanded):
        return expanded

    return None


def get_branch_at_directory(working_dir: str | None = None) -> str | None:
    """Get the current git branch at a specific directory."""
    try:
        completed_process = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
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
            capture_output=True,
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


def is_commit_command(bash_command: str) -> bool:
    return "git commit" in bash_command.lower().strip()


def is_main_commit_confirmed(bash_command: str) -> bool:
    """Return True if the command includes the explicit confirmation sentinel."""
    return "--allow-main-commit" in bash_command


def parse_bash_command_from_stdin() -> str:
    try:
        hook_event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return ""

    return hook_event.get("tool_input", {}).get("command", "")


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
    bash_command = parse_bash_command_from_stdin()

    if not is_commit_command(bash_command):
        sys.exit(0)

    if is_main_commit_confirmed(bash_command):
        sys.exit(0)

    target_dir_raw = extract_git_working_directory(bash_command)
    target_dir = resolve_directory(target_dir_raw)

    if target_dir_raw and not target_dir:
        sys.exit(0)

    current_branch = get_branch_at_directory(working_dir=target_dir)

    if current_branch not in PROTECTED_BRANCHES:
        sys.exit(0)

    if not is_protected_repo(working_dir=target_dir):
        sys.exit(0)

    denial = build_denial_response(current_branch, target_dir)
    print(json.dumps(denial))
    sys.exit(0)


if __name__ == "__main__":
    main()
