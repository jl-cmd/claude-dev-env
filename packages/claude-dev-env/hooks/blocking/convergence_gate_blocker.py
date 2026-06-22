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

from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402


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

    cwd = hook_input.get("tool_input", {}).get("cwd")
    pr_number = _resolve_pr_number(command, cwd)
    if pr_number is None:
        sys.exit(0)

    owner_repo = _resolve_owner_repo(cwd)
    if owner_repo is None:
        sys.exit(0)
    owner, repo = owner_repo

    completed_process = subprocess.run(
        [
            sys.executable,
            check_convergence_script,
            "--owner",
            owner,
            "--repo",
            repo,
            "--pr-number",
            str(pr_number),
        ],
        capture_output=True,
        text=True,
        check=False,
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
