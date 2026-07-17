#!/usr/bin/env python3
"""PreToolUse hook: block writes, durable posts, and commits that carry PII.

Surfaces guarded:

- Write / Edit / MultiEdit — new content about to land on disk
- Bash / PowerShell ``gh`` post subcommands and GitHub MCP post tools — durable
  bodies
- Bash / PowerShell ``git commit`` (including ``git.exe`` and flag forms) —
  staged file contents about to become history. Commit message bodies are out
  of scope; only staged blob text is scanned.

Payload and post-body scanning live in ``pii_payload_scan``; git-commit command
detection lives in ``pii_commit_command``; both re-export through this entry
module so the hooks.json wiring and every importer resolve unchanged.

A repository named in ``CLAUDE_PII_EXEMPT_REPOS`` or the ``pii_exempt_repositories``
list in ``~/.claude/local-identity.json`` skips the staged-commit scan; a
repository without a readable origin remote is never exempt. Exact values listed
under ``pii_allowlisted_values`` for a repository's origin slug may pass the
Write/Edit and staged-commit scans in that repository only.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

try:
    _blocking_directory = str(Path(__file__).resolve().parent)
    _hooks_directory = str(Path(__file__).resolve().parent.parent)
    for each_bootstrap_directory in (_blocking_directory, _hooks_directory):
        if each_bootstrap_directory not in sys.path:
            sys.path.insert(0, each_bootstrap_directory)
    from pii_commit_command import (
        extract_git_commit_working_directory,
        is_git_commit_shell_command,
    )
    from pii_payload_scan import (
        build_deny_reason,
        evaluate_post_body_texts,
        evaluate_write_edit_payload,
    )
    from pii_prevention_blocker_parts.repository_exemption import (
        _is_repository_exempt_from_pii_scan,
        _owner_repo_slug_from_origin_url,
        repository_allowlisted_values,
    )
    from pii_prevention_blocker_parts.repository_resolution import (
        compose_command_working_directory,
        expand_user_directory,
        refusal_reason_for_unresolved_repository,
    )
    from pii_scanner import is_path_exempt_from_pii_scan, scan_text_for_pii
    from precommit_code_rules_gate import resolve_repository_root
    from volatile_path_in_post_blocker import (
        extract_gh_post_body_texts_for_privacy_gate,
        extract_mcp_body_texts,
    )

    from hooks_constants.hook_block_logger import log_hook_block
    from hooks_constants.pii_prevention_constants import (
        ALL_SHELL_TOOL_NAMES,
        ALL_STAGED_BLOB_SHOW_COMMAND_PREFIX,
        ALL_STAGED_FILES_COMMAND,
        ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES,
        BODY_FILE_ENCODING,
        GIT_COMMAND_TIMEOUT_SECONDS,
        HOOK_SCRIPT_BASENAME,
        MAXIMUM_STAGED_FILE_BYTES,
        MCP_GITHUB_TOOL_PREFIX,
        NULL_BYTE_MARKER,
        STAGED_BLOB_PREFIX,
        STAGED_BLOB_REASON_DECODE_FAILED,
        STAGED_BLOB_REASON_GIT_SHOW_FAILED,
        STAGED_BLOB_REASON_NULL_BYTES,
        STAGED_BLOB_REASON_OVERSIZED,
        STAGED_BLOB_UNSCANNABLE_REASON_TEMPLATE,
        STAGED_LIST_FAILURE_REASON,
    )
    from hooks_constants.pre_tool_use_stdin import (
        read_hook_input_dictionary_from_stdin,
    )
except ImportError as import_error:
    raise ImportError(
        "pii_prevention_blocker: cannot import its sibling modules; "
        "ensure the blocking and hooks directories are importable."
    ) from import_error


__all__ = [
    "evaluate",
    "evaluate_bash_command",
    "evaluate_post_body_texts",
    "evaluate_staged_commit",
    "evaluate_write_edit_payload",
    "extract_git_commit_working_directory",
    "is_git_commit_shell_command",
    "list_staged_file_paths",
    "read_staged_file_text",
    "resolve_repository_root",
    "_owner_repo_slug_from_origin_url",
    "main",
]


def list_staged_file_paths(
    repository_root: Path,
) -> tuple[list[str] | None, str | None]:
    """List staged non-deleted paths, or report a list failure.

    Args:
        repository_root: Repository root used as the git working directory.

    Returns:
        ``(paths, None)`` on success, or ``(None, deny_reason)`` when the
        staged list cannot be read (fail-closed for commit gating).
    """
    try:
        completed_process = subprocess.run(
            list(ALL_STAGED_FILES_COMMAND),
            check=False, capture_output=True,
            text=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            cwd=str(repository_root),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None, STAGED_LIST_FAILURE_REASON
    if completed_process.returncode != 0:
        return None, STAGED_LIST_FAILURE_REASON
    all_paths = [
        each_line.strip()
        for each_line in completed_process.stdout.splitlines()
        if each_line.strip()
    ]
    return all_paths, None


def _git_show_staged_blob(
    repository_root: Path, staged_blob_reference: str
) -> subprocess.CompletedProcess[bytes] | None:
    """Return the ``git show`` result for a staged blob, or None on failure."""
    try:
        completed_process = subprocess.run(
            list(ALL_STAGED_BLOB_SHOW_COMMAND_PREFIX) + [staged_blob_reference],
            check=False, capture_output=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            cwd=str(repository_root),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if completed_process.returncode != 0:
        return None
    return completed_process


def _unscannable_result(relative_path: str, reason: str) -> tuple[None, str]:
    """Build the ``(None, deny_reason)`` pair for an unscannable staged blob."""
    return None, STAGED_BLOB_UNSCANNABLE_REASON_TEMPLATE.format(
        relative_path=relative_path, reason=reason
    )


def read_staged_file_text(
    repository_root: Path, relative_path: str
) -> tuple[str | None, str | None]:
    """Return staged blob text, or ``(None, deny_reason)`` when unscannable.

    Args:
        repository_root: Repository root for the git show working directory.
        relative_path: Repository-relative path of the staged file.

    Returns:
        ``(text, None)`` for scannable UTF-8 text; ``(None, reason)`` otherwise.
    """
    staged_blob_reference = STAGED_BLOB_PREFIX + relative_path
    completed_process = _git_show_staged_blob(repository_root, staged_blob_reference)
    if completed_process is None:
        return _unscannable_result(relative_path, STAGED_BLOB_REASON_GIT_SHOW_FAILED)
    raw_bytes = completed_process.stdout
    if len(raw_bytes) > MAXIMUM_STAGED_FILE_BYTES:
        return _unscannable_result(relative_path, STAGED_BLOB_REASON_OVERSIZED)
    if NULL_BYTE_MARKER in raw_bytes:
        return _unscannable_result(relative_path, STAGED_BLOB_REASON_NULL_BYTES)
    try:
        return raw_bytes.decode(BODY_FILE_ENCODING), None
    except UnicodeDecodeError:
        return _unscannable_result(relative_path, STAGED_BLOB_REASON_DECODE_FAILED)


def _scan_staged_path(
    repository_root: Path, relative_path: str, all_allowlisted_values: frozenset[str]
) -> str | None:
    """Return a deny reason for one staged path, or None when it is clean."""
    staged_text, unscannable_reason = read_staged_file_text(
        repository_root, relative_path
    )
    if unscannable_reason is not None:
        return unscannable_reason
    if staged_text is None:
        return _unscannable_result(relative_path, STAGED_BLOB_REASON_GIT_SHOW_FAILED)[1]
    all_findings = [
        each_finding
        for each_finding in scan_text_for_pii(staged_text)
        if each_finding.matched_text not in all_allowlisted_values
    ]
    if not all_findings:
        return None
    return build_deny_reason(all_findings, f"staged commit ({relative_path})")


def evaluate_staged_commit(repository_root: Path) -> str | None:
    """Return a deny reason when staged content carries PII or is unscannable.

    Fail-closed: git list/show failures and unscannable blobs deny the commit
    rather than treating unread content as clean. A value in the repository's
    PII allowlist is dropped from the findings, so its commits may carry it.

    Args:
        repository_root: Repository whose index is about to be committed.

    Returns:
        Deny reason text, or None when every scannable staged path is clean.
    """
    all_relative_paths, list_failure_reason = list_staged_file_paths(repository_root)
    if list_failure_reason is not None or all_relative_paths is None:
        return list_failure_reason or STAGED_LIST_FAILURE_REASON
    all_allowlisted_values = repository_allowlisted_values(repository_root)
    for each_relative_path in all_relative_paths:
        if is_path_exempt_from_pii_scan(each_relative_path):
            continue
        deny_reason = _scan_staged_path(
            repository_root, each_relative_path, all_allowlisted_values
        )
        if deny_reason is not None:
            return deny_reason
    return None


def _evaluate_commit_staged_content(
    bash_command: str, working_directory: str | None
) -> str | None:
    """Scan the staged content of the repository the commit command targets.

    Resolves the repository from the command's ``-C``/``cd`` path, falling back
    to the session working directory only when the command names none, so a
    removed cwd never blocks a commit that targets a valid repo.

    Args:
        bash_command: The Bash or PowerShell tool command string.
        working_directory: Session working directory fallback.

    Returns:
        Deny reason text, or None when the staged content is clean or exempt.
    """
    command_directory = compose_command_working_directory(bash_command)
    attempted_directory = (
        command_directory if command_directory is not None else working_directory
    )
    expanded_directory = expand_user_directory(attempted_directory)
    repository_root = resolve_repository_root(expanded_directory)
    if repository_root is None:
        return refusal_reason_for_unresolved_repository(attempted_directory)
    if _is_repository_exempt_from_pii_scan(repository_root):
        return None
    return evaluate_staged_commit(repository_root)


def evaluate_bash_command(
    bash_command: str, working_directory: str | None
) -> str | None:
    """Return a deny reason for a shell gh post or git commit with PII.

    Args:
        bash_command: The Bash or PowerShell tool command string.
        working_directory: Session working directory, used only when the command
            names no repository path.

    Returns:
        Deny reason text, or None when the command is clean or out of scope.
    """
    all_post_bodies, body_file_failure_reason = (
        extract_gh_post_body_texts_for_privacy_gate(
            bash_command, working_directory=working_directory
        )
    )
    if body_file_failure_reason is not None:
        return body_file_failure_reason
    post_deny_reason = evaluate_post_body_texts(all_post_bodies)
    if post_deny_reason is not None:
        return post_deny_reason
    if not is_git_commit_shell_command(bash_command):
        return None
    return _evaluate_commit_staged_content(bash_command, working_directory)


def _evaluate_shell_tool(
    all_tool_input: dict[str, object], payload_by_key: dict[str, object]
) -> str | None:
    """Resolve the command and working directory, then gate a shell tool call."""
    command_value = all_tool_input.get("command", "")
    if not isinstance(command_value, str) or not command_value:
        return None
    working_directory_value = all_tool_input.get("working_directory")
    working_directory = (
        working_directory_value
        if isinstance(working_directory_value, str)
        else None
    )
    if working_directory is None:
        cwd_value = payload_by_key.get("cwd")
        working_directory = cwd_value if isinstance(cwd_value, str) else None
    return evaluate_bash_command(command_value, working_directory=working_directory)


def evaluate(payload_by_key: dict[str, object]) -> str | None:
    """Decide whether a PreToolUse payload carries high-confidence PII.

    Args:
        payload_by_key: The PreToolUse payload with tool_name and tool_input.

    Returns:
        Deny-reason text when blocked, or None when allowed.
    """
    raw_tool_name = payload_by_key.get("tool_name", "")
    tool_name = raw_tool_name if isinstance(raw_tool_name, str) else ""
    raw_tool_input = payload_by_key.get("tool_input", {})
    all_tool_input = raw_tool_input if isinstance(raw_tool_input, dict) else {}
    if tool_name in ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES:
        return evaluate_write_edit_payload(
            tool_name, all_tool_input, hook_payload=payload_by_key
        )
    if tool_name in ALL_SHELL_TOOL_NAMES:
        return _evaluate_shell_tool(all_tool_input, payload_by_key)
    if tool_name.startswith(MCP_GITHUB_TOOL_PREFIX):
        return evaluate_post_body_texts(extract_mcp_body_texts(all_tool_input))
    return None


def build_deny_payload(deny_reason: str) -> dict[str, object]:
    """Build the PreToolUse deny payload for *deny_reason*.

    Args:
        deny_reason: The permissionDecisionReason text.

    Returns:
        Deny payload dictionary serialized to stdout by the hook.
    """
    log_hook_block(
        calling_hook_name=HOOK_SCRIPT_BASENAME,
        hook_event="PreToolUse",
        block_reason=deny_reason,
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason,
        }
    }


def main() -> None:
    """Read PreToolUse stdin and deny when high-confidence PII is present."""
    payload_dictionary = read_hook_input_dictionary_from_stdin()
    if payload_dictionary is None:
        sys.exit(0)
    deny_reason = evaluate(payload_dictionary)
    if deny_reason is None:
        sys.exit(0)
    sys.stdout.write(json.dumps(build_deny_payload(deny_reason)) + "\n")
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
