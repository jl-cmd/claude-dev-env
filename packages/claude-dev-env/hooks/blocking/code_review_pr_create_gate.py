"""PreToolUse gate: PR create lands only behind a clean xhigh code-review stamp.

Fires on Bash/PowerShell ``gh pr create`` and on the MCP
``create_pull_request`` tool. Resolves the repository from the session
working directory (or the payload cwd), computes the live change-surface
hash, and allows the create only when a clean stamp at effort ``xhigh`` or
higher covers that exact hash under ``~/.claude/code-review-stamps/``.

Empty surfaces and repos with no resolvable upstream base are out of scope
and allowed. Push lands behind ``code_review_push_gate`` and commit behind
``verified_commit_gate``; this gate covers pull-request creation only.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    _blocking_directory = str(Path(__file__).resolve().parent)
    _hooks_directory = str(Path(__file__).resolve().parent.parent)
    for each_bootstrap_directory in (_blocking_directory, _hooks_directory):
        if each_bootstrap_directory not in sys.path:
            sys.path.insert(0, each_bootstrap_directory)

    from code_review_enforcement_config_bootstrap import (
        register_code_review_enforcement_constants,
    )
    from verified_commit_config_bootstrap import register_verified_commit_constants

    register_code_review_enforcement_constants()
    register_verified_commit_constants()

    from code_review_stamp_store import live_surface_hash, stamp_covers_surface
    from config.code_review_enforcement_constants import (
        ALL_GATED_SHELL_TOOL_NAMES,
        DENY_PERMISSION_DECISION,
        GH_PR_CREATE_INVOCATION_PATTERN,
        HASH_PREVIEW_LENGTH,
        MCP_CREATE_PULL_REQUEST_TOOL_NAME,
        PR_CREATE_GATE_CORRECTIVE_MESSAGE,
        PR_CREATE_GATE_HOOK_MODULE_NAME,
        PR_CREATE_REQUIRED_EFFORT,
        PRE_TOOL_USE_HOOK_EVENT_NAME,
    )
    from verification_verdict_store import resolve_repo_root

    from hooks_constants.hook_block_logger import log_hook_block
except ImportError as import_error:
    raise ImportError(
        "the code_review_pr_create_gate dependencies did not import; "
        "ensure the hooks directory is importable."
    ) from import_error


def build_deny_payload(deny_reason: str) -> dict[str, dict[str, str]]:
    """Build the PreToolUse deny payload for a blocked PR create.

    Args:
        deny_reason: The corrective message naming why the create is denied.

    Returns:
        The ``hookSpecificOutput`` deny payload.
    """
    return {
        "hookSpecificOutput": {
            "hookEventName": PRE_TOOL_USE_HOOK_EVENT_NAME,
            "permissionDecision": DENY_PERMISSION_DECISION,
            "permissionDecisionReason": deny_reason,
        }
    }


def _strip_quoted_regions(command_text: str) -> str:
    """Blank out single- and double-quoted spans so prose is not gated."""
    quote_pattern = re.compile(r"\"[^\"]*\"|'[^']*'")
    return quote_pattern.sub(lambda each_match: " " * len(each_match.group(0)), command_text)


def command_invokes_gh_pr_create(command_text: str) -> bool:
    """Decide whether a shell command invokes ``gh pr create``.

    ::

        gh pr create --title T --body-file b.md  -> True
        echo "gh pr create"                      -> False (quoted prose)
        gh pr edit 1 --title T                   -> False

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        True when the command contains a real ``gh pr create`` invocation.
    """
    quote_stripped_command = _strip_quoted_regions(command_text)
    invocation_pattern = re.compile(GH_PR_CREATE_INVOCATION_PATTERN, re.IGNORECASE)
    return invocation_pattern.search(quote_stripped_command) is not None


def is_mcp_create_pull_request_tool(tool_name: str) -> bool:
    """Decide whether a tool name is the MCP create-pull-request tool.

    Args:
        tool_name: The PreToolUse ``tool_name`` field.

    Returns:
        True when the name is the configured MCP create-PR tool.
    """
    return tool_name == MCP_CREATE_PULL_REQUEST_TOOL_NAME


def deny_reason_for_directory(target_directory: str) -> str | None:
    """Decide whether a PR create from a directory must be blocked.

    ::

        no repo / empty surface / covering xhigh stamp   -> None (allow)
        production surface without xhigh-or-higher stamp -> corrective (deny)

    Args:
        target_directory: The session or repo directory the create targets.

    Returns:
        The deny reason when the surface needs a clean xhigh stamp and none
        covers it; None when the create may proceed.
    """
    repo_root = resolve_repo_root(target_directory)
    if repo_root is None:
        return None
    surface_hash = live_surface_hash(repo_root)
    if surface_hash is None:
        return None
    if stamp_covers_surface(repo_root, surface_hash, PR_CREATE_REQUIRED_EFFORT):
        return None
    hash_preview = surface_hash[:HASH_PREVIEW_LENGTH]
    return (
        f"{PR_CREATE_GATE_CORRECTIVE_MESSAGE} (repo: {repo_root}, surface sha256 {hash_preview}...)"
    )


def _deny_for_directory_or_none(
    session_directory: str,
) -> dict[str, dict[str, str]] | None:
    """Return the deny payload for a directory that lacks a covering stamp."""
    deny_reason = deny_reason_for_directory(session_directory)
    if deny_reason is None:
        return None
    return build_deny_payload(deny_reason)


def _shell_command_targets_pr_create(all_pretooluse_payload: dict[str, object]) -> bool:
    """Decide whether a shell payload carries a real ``gh pr create``."""
    tool_input = all_pretooluse_payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return False
    command_text = tool_input.get("command", "")
    if not isinstance(command_text, str) or not command_text:
        return False
    return command_invokes_gh_pr_create(command_text)


def decision_for_payload(
    all_pretooluse_payload: dict[str, object],
) -> dict[str, dict[str, str]] | None:
    """Build the deny decision for a gated PR-create attempt.

    Args:
        all_pretooluse_payload: The PreToolUse hook payload.

    Returns:
        The deny decision mapping when the create lacks a covering xhigh
        stamp; None when the create may proceed.
    """
    tool_name = all_pretooluse_payload.get("tool_name", "")
    if not isinstance(tool_name, str):
        return None
    session_directory = all_pretooluse_payload.get("cwd", ".")
    if not isinstance(session_directory, str):
        session_directory = "."
    if is_mcp_create_pull_request_tool(tool_name):
        return _deny_for_directory_or_none(session_directory)
    if tool_name not in ALL_GATED_SHELL_TOOL_NAMES:
        return None
    if not _shell_command_targets_pr_create(all_pretooluse_payload):
        return None
    return _deny_for_directory_or_none(session_directory)


def _log_and_emit_deny(deny_reason: str, tool_name: str) -> None:
    """Log the block and write the deny payload to stdout."""
    log_hook_block(
        calling_hook_name=PR_CREATE_GATE_HOOK_MODULE_NAME,
        hook_event=PRE_TOOL_USE_HOOK_EVENT_NAME,
        block_reason=deny_reason,
        tool_name=tool_name if isinstance(tool_name, str) else None,
    )
    sys.stdout.write(json.dumps(build_deny_payload(deny_reason)) + "\n")


def main() -> None:
    """Read the PreToolUse payload and decide whether to allow the PR create."""
    try:
        pretooluse_payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    deny_decision = decision_for_payload(pretooluse_payload)
    if deny_decision is None:
        return
    tool_name = pretooluse_payload.get("tool_name", "")
    deny_reason = deny_decision["hookSpecificOutput"]["permissionDecisionReason"]
    if not isinstance(deny_reason, str):
        return
    _log_and_emit_deny(deny_reason, tool_name if isinstance(tool_name, str) else "")


if __name__ == "__main__":
    main()
