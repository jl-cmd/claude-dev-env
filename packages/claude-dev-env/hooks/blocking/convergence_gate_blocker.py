#!/usr/bin/env python3
"""PreToolUse hook: block gh pr ready until convergence pre-conditions pass.

Runs check_convergence.py against the PR and denies the gh pr ready
call if any condition fails. The agent sees exactly which conditions
failed and can address them before retrying.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.convergence_gate_blocker_constants import (  # noqa: E402
    COMMAND_SEPARATOR_PATTERN,
    GH_PR_READY_ANCHOR_PATTERN,
    PR_URL_OWNER_REPO_NUMBER_PATTERN,
    REPO_OVERRIDE_FLAG_PATTERN,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402


def _ready_command_segment(command: str) -> str:
    """Return the ``gh pr ready`` invocation, clipped at the next command separator.

    ::

        gh pr ready 161 && gh pr comment 999 --repo other-owner/other-repo
        ^^^^^^^^^^^^^^^^                            clipped -> returned segment

    Scanning only this segment keeps a ``--repo`` flag or PR URL that belongs to
    a chained command from binding the gate to the wrong PR.
    """
    ready_match = re.search(GH_PR_READY_ANCHOR_PATTERN, command)
    if ready_match is None:
        return command
    ready_tail = command[ready_match.start() :]
    separator_match = re.search(COMMAND_SEPARATOR_PATTERN, ready_tail)
    if separator_match is None:
        return ready_tail
    return ready_tail[: separator_match.start()]


def _parse_pr_url(command: str) -> tuple[str, str, int] | None:
    """Return (owner, repo, pr_number) from a full PR URL in the command."""
    url_match = re.search(PR_URL_OWNER_REPO_NUMBER_PATTERN, command)
    if url_match is None:
        return None
    return url_match.group("owner"), url_match.group("repo"), int(url_match.group("number"))


def _parse_repo_flag(command: str) -> tuple[str, str] | None:
    """Return (owner, repo) from a --repo/-R flag in the command."""
    flag_match = re.search(REPO_OVERRIDE_FLAG_PATTERN, command)
    if flag_match is None:
        return None
    return flag_match.group("owner"), flag_match.group("repo")


def _resolve_target_identity(command: str, cwd: str | None) -> tuple[str, str, int] | None:
    """Resolve the (owner, repo, pr_number) the gate keys its evidence to.

    A full PR URL in the command yields all three. A --repo/-R flag yields
    the repository while the PR number resolves from the command number or
    the cwd. With neither present, both the repository and the number
    resolve from the cwd.
    """
    ready_segment = _ready_command_segment(command)
    pr_url_identity = _parse_pr_url(ready_segment)
    if pr_url_identity is not None:
        return pr_url_identity

    pr_number = _resolve_pr_number(ready_segment, cwd)
    if pr_number is None:
        return None

    repo_flag_identity = _parse_repo_flag(ready_segment)
    if repo_flag_identity is not None:
        flag_owner, flag_repo = repo_flag_identity
        return flag_owner, flag_repo, pr_number

    cwd_identity = _resolve_owner_repo(cwd)
    if cwd_identity is None:
        return None
    cwd_owner, cwd_repo = cwd_identity
    return cwd_owner, cwd_repo, pr_number


def _resolve_pr_number(command: str, cwd: str | None) -> int | None:
    direct_match = re.search(r"\bgh\s+pr\s+ready\s+(\d+)", command)
    if direct_match:
        return int(direct_match.group(1))
    try:
        completed_process = subprocess.run(
            ["gh", "pr", "view", "--json", "number", "--jq", ".number"],
            capture_output=True,
            text=True,
            cwd=cwd or None,
            check=False,
        )
    except OSError:
        return None
    if completed_process.returncode != 0:
        return None
    try:
        return int(completed_process.stdout.strip())
    except (ValueError, TypeError):
        return None


def _resolve_owner_repo(cwd: str | None) -> tuple[str, str] | None:
    try:
        completed_process = subprocess.run(
            ["gh", "repo", "view", "--json", "owner,name", "--jq", ".owner.login,.name"],
            capture_output=True,
            text=True,
            cwd=cwd or None,
            check=False,
        )
    except OSError:
        return None
    if completed_process.returncode != 0:
        return None
    parts = completed_process.stdout.strip().splitlines()
    if len(parts) <= 1:
        match = re.match(
            r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?$",
            completed_process.stdout.strip(),
        )
        if match:
            return match.group(1), match.group(2)
        return None
    return parts[0], parts[1]


def _run_convergence_check(
    script: str, owner: str, repo: str, pr_number: int, cwd: str | None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            script,
            "--owner",
            owner,
            "--repo",
            repo,
            "--pr-number",
            str(pr_number),
        ],
        capture_output=True,
        text=True,
        cwd=cwd or None,
        check=False,
    )


def main() -> None:
    check_convergence_script = str(
        Path.home() / ".claude/skills/pr-converge/scripts/check_convergence.py"
    )

    if not Path(check_convergence_script).is_file():
        sys.exit(0)

    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    command = hook_input.get("tool_input", {}).get("command", "")
    gh_pr_ready_pattern = re.compile(r"\bgh\s+pr\s+ready\b(?![^&|;\n]*--undo)")
    if not gh_pr_ready_pattern.search(command):
        sys.exit(0)

    cwd = hook_input.get("cwd")
    target_identity = _resolve_target_identity(command, cwd)
    if target_identity is None:
        sys.exit(0)
    owner, repo, pr_number = target_identity

    completed_process = _run_convergence_check(
        check_convergence_script, owner, repo, pr_number, cwd
    )

    if completed_process.returncode in (0, 2):
        sys.exit(0)

    block_reason = (
        "Convergence check failed — PR is not ready to mark ready:\n\n" + completed_process.stdout
    )
    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": block_reason,
        }
    }
    log_hook_block(
        calling_hook_name="convergence_gate_blocker.py",
        hook_event="PreToolUse",
        block_reason=block_reason,
        tool_name="Bash",
    )
    print(json.dumps(deny_payload))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
