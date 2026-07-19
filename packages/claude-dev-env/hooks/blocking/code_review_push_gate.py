"""PreToolUse gate: git push lands only behind a clean low code-review stamp.

Fires on Bash/PowerShell tool calls when ``CODE_REVIEW_ENFORCEMENT_ENABLED``
is on (default off). When the command carries a ``git push``, the gate
resolves each repository the push targets, computes the live
change-surface hash against the merge base, and allows the push only when a
clean stamp at effort ``low`` or higher covers that exact hash under
``~/.claude/code-review-stamps/``.

Allowed without a stamp:

- a command carrying the bypass marker (``# code-review-skip``) as a trailing
  shell comment,
- a repository with no resolvable upstream base,
- a mechanically exempt surface (docs and image files, pytest test files, and
  Python files whose docstring-stripped AST is unchanged), and
- a surface a clean ``low``-or-higher stamp already covers.

Commit lands behind ``verified_commit_gate``; only push is gated here.
"""

from __future__ import annotations

import json
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

    from code_review_gate_deny import log_and_emit_code_review_deny
    from code_review_stamp_store import live_surface_hash, stamp_covers_surface
    from config.code_review_enforcement_constants import (
        ALL_GATED_SHELL_TOOL_NAMES,
        CODE_REVIEW_BYPASS_MARKER,
        CODE_REVIEW_ENFORCEMENT_ENABLED,
        GATED_PUSH_SUBCOMMANDS,
        HASH_PREVIEW_LENGTH,
        PUSH_GATE_CORRECTIVE_MESSAGE,
        PUSH_GATE_HOOK_MODULE_NAME,
        PUSH_REQUIRED_EFFORT,
    )
    from verification_verdict_store import (
        is_verification_exempt_diff,
        resolve_merge_base,
        resolve_repo_root,
    )
    from verified_commit_gate_parts.command_tokenization import (
        command_carries_trailing_marker,
    )
    from verified_commit_gate_parts.gated_invocations import gated_repo_directories
except ImportError as import_error:
    raise ImportError(
        "the code_review_push_gate dependencies did not import; "
        "ensure the hooks directory is importable."
    ) from import_error


def deny_reason_for_directory(target_directory: str) -> str | None:
    """Decide whether a push from a directory must be blocked.

    Allowed when enforcement is off, the directory is no repo, has no upstream
    base, is a mechanically exempt surface, or a clean low-or-higher stamp
    covers it.

    Args:
        target_directory: The directory the push targets.

    Returns:
        The deny reason when the surface lacks a covering low stamp, else None.
    """
    if not CODE_REVIEW_ENFORCEMENT_ENABLED:
        return None
    repo_root = resolve_repo_root(target_directory)
    if repo_root is None:
        return None
    merge_base_sha = resolve_merge_base(repo_root)
    if merge_base_sha is None:
        return None
    if is_verification_exempt_diff(repo_root, merge_base_sha):
        return None
    surface_hash = live_surface_hash(repo_root)
    if surface_hash is None:
        return None
    if stamp_covers_surface(repo_root, surface_hash, PUSH_REQUIRED_EFFORT):
        return None
    hash_preview = surface_hash[:HASH_PREVIEW_LENGTH]
    return f"{PUSH_GATE_CORRECTIVE_MESSAGE} (repo: {repo_root}, surface sha256 {hash_preview}...)"


def _emit_first_denied_directory(command_text: str, session_directory: str, tool_name: str) -> None:
    """Deny the push against the first target directory that lacks a stamp."""
    all_target_directories = gated_repo_directories(
        command_text, session_directory, all_gated_subcommands=GATED_PUSH_SUBCOMMANDS
    )
    for each_target_directory in all_target_directories:
        deny_reason = deny_reason_for_directory(each_target_directory)
        if deny_reason is None:
            continue
        log_and_emit_code_review_deny(deny_reason, tool_name, PUSH_GATE_HOOK_MODULE_NAME)
        return


def main() -> None:
    """Read the PreToolUse payload and decide whether to allow the push.

    Allows the command without a stamp when it carries the bypass marker
    (``CODE_REVIEW_BYPASS_MARKER``) as a genuine trailing shell comment;
    otherwise denies a push whose surface lacks a covering low stamp.
    """
    try:
        pretooluse_payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    tool_name = pretooluse_payload.get("tool_name", "")
    if tool_name not in ALL_GATED_SHELL_TOOL_NAMES:
        return
    tool_input = pretooluse_payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return
    command_text = tool_input.get("command", "")
    if not isinstance(command_text, str) or not command_text:
        return
    if command_carries_trailing_marker(command_text, CODE_REVIEW_BYPASS_MARKER):
        return
    session_directory = pretooluse_payload.get("cwd", ".")
    if not isinstance(session_directory, str):
        session_directory = "."
    _emit_first_denied_directory(command_text, session_directory, tool_name)


if __name__ == "__main__":
    main()
