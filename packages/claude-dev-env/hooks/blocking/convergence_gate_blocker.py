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

from blocking.pr_description_pr_number import (  # noqa: E402
    _extract_pr_number_from_command,
)
from hooks_constants.convergence_gate_blocker_constants import (  # noqa: E402
    ALL_GH_PR_VIEW_NUMBER_COMMAND,
    BASH_LINE_CONTINUATION_PATTERN,
    COMMAND_SEPARATOR_PATTERN,
    GH_PR_READY_ANCHOR_PATTERN,
    GH_REPO_FLAG,
    GIT_URL_SUFFIX,
    PR_URL_OWNER_REPO_NUMBER_PATTERN,
    REPO_OVERRIDE_FLAG_PATTERN,
    REPO_SLUG_TEMPLATE,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402


def _ready_command_segment(command: str) -> str:
    """Return the ``gh pr ready`` invocation, clipped at the next command separator.

    ::

        gh pr ready 161 && gh pr comment 999 --repo other-owner/other-repo
        ^^^^^^^^^^^^^^^^                            clipped -> returned segment

    Scanning only this segment keeps a ``--repo`` flag or PR URL that belongs to
    a chained command from binding the gate to the wrong PR. A backslash-newline
    continuation is folded to a space before the separator search, so a
    ``--repo`` flag written on a continued line stays inside the segment.
    """
    ready_match = re.search(GH_PR_READY_ANCHOR_PATTERN, command)
    if ready_match is None:
        return command
    ready_tail = command[ready_match.start() :]
    ready_tail = re.sub(BASH_LINE_CONTINUATION_PATTERN, " ", ready_tail)
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
    return flag_match.group("owner"), flag_match.group("repo").removesuffix(GIT_URL_SUFFIX)


def _resolve_named_identity(
    command: str, cwd: str | None
) -> tuple[tuple[str, str] | None, int] | None:
    """Resolve the repository the command names and its PR number.

    A full PR URL yields both the (owner, repo) pair and the number. A
    ``--repo``/``-R`` flag yields the pair while the number resolves from the
    command's positional argument or the named repository's current-branch PR.
    With neither present, the pair is None — leaving gh bound to the current
    directory's repository — and the number resolves the same way. Every parse
    runs over the ``gh pr ready`` segment alone, clipped at the next command
    separator, so a flag or URL belonging to a chained command cannot bind the
    gate to the wrong PR.

    Args:
        command: The raw shell command captured by the hook.
        cwd: The working directory gh runs in when the number resolves from the
            current branch, or None for the process default.

    Returns:
        The (owner, repo) pair the command names — None when it names none —
        paired with the resolved PR number, or None when no number resolves.
    """
    ready_segment = _ready_command_segment(command)
    pr_url_identity = _parse_pr_url(ready_segment)
    if pr_url_identity is not None:
        url_owner, url_repo, url_number = pr_url_identity
        return (url_owner, url_repo), url_number
    all_target_repo = _parse_repo_flag(ready_segment)
    from_owner, from_repo = all_target_repo if all_target_repo is not None else (None, None)
    resolved_pr_number = _resolve_pr_number(ready_segment, cwd, from_owner, from_repo)
    if resolved_pr_number is None:
        return None
    return all_target_repo, resolved_pr_number


def _resolve_target_identity(command: str, cwd: str | None) -> tuple[str, str, int] | None:
    """Resolve the (owner, repo, pr_number) the gate keys its evidence to.

    Delegates the repository-and-number resolution to the shared core, then
    falls back to the cwd repository for the number when the command names no
    repository of its own.
    """
    named_identity = _resolve_named_identity(command, cwd)
    if named_identity is None:
        return None
    all_target_repo, pr_number = named_identity
    if all_target_repo is not None:
        owner, repo = all_target_repo
        return owner, repo, pr_number

    cwd_identity = _resolve_owner_repo(cwd)
    if cwd_identity is None:
        return None
    cwd_owner, cwd_repo = cwd_identity
    return cwd_owner, cwd_repo, pr_number


def _repo_flag_arguments(all_target_repo: tuple[str, str] | None) -> list[str]:
    """Build the ``--repo owner/repo`` arguments for a gh subcommand.

    Args:
        all_target_repo: The (owner, repo) pair the command names, or None when
            the command names no repository.

    Returns:
        A ``[--repo, owner/repo]`` argument pair when a repository is named, or
        an empty list when it is None — leaving gh bound to the current
        directory's repository.
    """
    if all_target_repo is None:
        return []
    owner, repo = all_target_repo
    return [GH_REPO_FLAG, REPO_SLUG_TEMPLATE.format(owner=owner, repo=repo)]


def _resolve_current_branch_pr_number(
    all_target_repo: tuple[str, str] | None, cwd: str | None
) -> int | None:
    """Resolve the current-branch PR number through ``gh pr view``.

    Args:
        all_target_repo: The (owner, repo) pair the command names, or None to
            read the current directory's repository.
        cwd: The working directory gh runs in, or None for the process default.

    Returns:
        The PR number gh reports, or None when gh is missing, exits non-zero,
        or prints no integer — every failure path returns None so the caller
        fails open.
    """
    all_view_arguments = [
        *ALL_GH_PR_VIEW_NUMBER_COMMAND,
        *_repo_flag_arguments(all_target_repo),
    ]
    try:
        completed_process = subprocess.run(
            all_view_arguments,
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


def _resolve_pr_number(
    command: str,
    cwd: str | None,
    from_owner: str | None,
    from_repo: str | None,
) -> int | None:
    direct_number = _extract_pr_number_from_command(command)
    if direct_number is not None:
        return direct_number
    if from_owner is not None and from_repo is not None:
        all_target_repo: tuple[str, str] | None = (from_owner, from_repo)
    else:
        all_target_repo = None
    return _resolve_current_branch_pr_number(all_target_repo, cwd)


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
    gh_pr_ready_pattern = re.compile(GH_PR_READY_ANCHOR_PATTERN)
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
