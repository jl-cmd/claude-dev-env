"""PreToolUse gate: git commit/push lands only behind a minted verifier verdict.

Fires on Bash and PowerShell tool calls. When the command carries a
``git commit`` or ``git push``, the gate resolves the repository the command
targets, computes the live change-surface manifest against the merge base,
and allows the command only when one of these holds:

- the command carries the verification bypass marker (``# verify-skip``),
  a manual on-the-fly override that skips the gate for that one command,
- the repository has no resolvable upstream base — no ``origin/HEAD``, no
  configured tracking ref, and neither ``origin/main`` nor ``origin/master``
  (scratch repos with no remote branch are out of scope),
- the surface is mechanically exempt (docs/images by extension, pytest
  test files by name convention, Python files whose docstring-stripped
  AST is unchanged), or
- a passing verifier verdict binds to the exact live manifest hash —
  matched by content hash, not by work-tree location, so a verdict
  ``verifier_verdict_minter.py`` minted while verifying any work tree of
  the surface clears the commit, as does one a workflow ``code-verifier``
  emitted in its own transcript.

The surface binds every changed and untracked file's content, so slicing
work into small commits or staging files cannot move the hash, while any
content edit or new file after verification invalidates the verdict.
Verdict files live under ``~/.claude/verification/`` and are minted only by
the SubagentStop hook when a ``code-verifier`` agent finishes. A blocked
command's deny payload carries ``VERIFY_SKIP_ADDITIONAL_CONTEXT``, so the
agent learns at the moment of the block when ``# verify-skip`` is legitimate.
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

    from verified_commit_config_bootstrap import register_verified_commit_constants

    register_verified_commit_constants()

    from config.verified_commit_constants import (
        ALL_GATED_TOOL_NAMES,
        VERIFICATION_BYPASS_MARKER,
    )
    from config.verified_commit_gate_output_constants import (
        GATE_HOOK_MODULE_NAME,
        PRE_TOOL_USE_HOOK_EVENT_NAME,
    )
    from verified_commit_gate_parts.command_tokenization import (
        command_carries_trailing_marker,
    )
    from verified_commit_gate_parts.deny_payload import build_deny_payload
    from verified_commit_gate_parts.deny_reason import deny_reason_for_directory
    from verified_commit_gate_parts.gated_invocations import gated_repo_directories

    from hooks_constants.hook_block_logger import log_hook_block
except ImportError as import_error:
    raise ImportError(
        "the verified_commit_gate_parts modules did not import; "
        "ensure the hooks directory is importable."
    ) from import_error


def _log_and_emit_deny(deny_reason: str, tool_name: str) -> None:
    """Log the block and write the deny payload to stdout."""
    log_hook_block(
        calling_hook_name=GATE_HOOK_MODULE_NAME,
        hook_event=PRE_TOOL_USE_HOOK_EVENT_NAME,
        block_reason=deny_reason,
        tool_name=tool_name if isinstance(tool_name, str) else None,
    )
    sys.stdout.write(json.dumps(build_deny_payload(deny_reason)) + "\n")


def main() -> None:
    """Read the PreToolUse payload and decide whether to allow the command.

    Allows the command without a verdict when it carries the verification
    bypass marker (``VERIFICATION_BYPASS_MARKER``) as a genuine trailing shell
    comment outside every quoted region, a manual on-the-fly override;
    otherwise denies an unverified commit or push.
    """
    try:
        pretooluse_payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    tool_name = pretooluse_payload.get("tool_name", "")
    if tool_name not in ALL_GATED_TOOL_NAMES:
        return
    command_text = pretooluse_payload.get("tool_input", {}).get("command", "")
    if not command_text:
        return
    if command_carries_trailing_marker(command_text, VERIFICATION_BYPASS_MARKER):
        return
    session_directory = pretooluse_payload.get("cwd", ".")
    transcript_path = pretooluse_payload.get("transcript_path", "")
    for each_target_directory in gated_repo_directories(command_text, session_directory):
        deny_reason = deny_reason_for_directory(each_target_directory, transcript_path)
        if deny_reason is None:
            continue
        _log_and_emit_deny(deny_reason, tool_name)
        return


if __name__ == "__main__":
    main()
