#!/usr/bin/env python3
"""PreToolUse guard: deny shell and file-tool access to the stamp directory.

The push and PR-create gates trust a single invariant: only
``invoke_code_review.py --record-stamp`` mints stamp files under
``~/.claude/code-review-stamps/``. settings.json cannot be the only shipped
protection, so this guard fires on both surfaces:

- Bash / PowerShell: deny any command that names the stamp directory (absolute
  path, cd-then-relative write, cd into the stamp directory, a split directory
  change through the Claude home into the stamp directory, stamp-file shape, a
  path-join write, or a path assembled by obfuscation that decodes to a stamp
  segment), or that imports the stamp store module or calls its mint function.
- Write / Edit / MultiEdit: deny any path under the stamp directory.

No legitimate workflow reaches that directory through a shell or the file
tools: the invoker writes in-process after a clean review, so the sanctioned
minter command names none of these matchers and passes without an allowlist.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    _blocking_directory = str(Path(__file__).resolve().parent)
    if _blocking_directory not in sys.path:
        sys.path.insert(0, _blocking_directory)
    _hooks_directory = str(Path(__file__).resolve().parent.parent)
    if _hooks_directory not in sys.path:
        sys.path.append(_hooks_directory)

    from code_review_enforcement_config_bootstrap import (
        register_code_review_enforcement_constants,
    )
    from verified_commit_config_bootstrap import register_verified_commit_constants

    register_code_review_enforcement_constants()
    register_verified_commit_constants()

    from code_review_stamp_store import stamp_directory
    from code_review_stamp_write_blocker_parts.obfuscated_stamp_path_reference import (
        references_obfuscated_stamp_path,
    )
    from code_review_stamp_write_blocker_parts.split_directory_change_into_stamp import (
        changes_through_split_directory_into_stamp,
        directory_change_prefix,
    )
    from config.code_review_enforcement_constants import (
        ALL_GATED_SHELL_TOOL_NAMES,
        ALL_STAMP_STORE_FORGE_PATTERNS,
        ALL_WRITE_EDIT_TOOL_NAMES,
        DENY_PERMISSION_DECISION,
        PRE_TOOL_USE_HOOK_EVENT_NAME,
        RELATIVE_STAMP_DIRECTORY_PATTERN,
        STAMP_DIRECTORY_GUARD_MESSAGE,
        STAMP_DIRECTORY_NAME,
        STAMP_FILE_REFERENCE_BOUNDARY_PREFIX_PATTERN,
        STAMP_FILE_ROOT_KEY_JSON_SUFFIX_PATTERN,
        STAMP_WRITE_BLOCKER_HOOK_MODULE_NAME,
    )
    from config.verified_commit_constants import (
        CLAUDE_HOME_DIRECTORY_NAME,
        CLAUDE_HOME_TARGET_BOUNDARY_PATTERN,
        COMMAND_AFTER_DIRECTORY_CHANGE_PATTERN,
        DIRECTORY_CHANGE_TARGET_PATTERN,
        NON_REDIRECT_FILE_WRITE_PRIMITIVE_PATTERN,
        ROOT_KEY_HEX_LENGTH,
        VERDICT_DIRECTORY_NAME_SEPARATOR_PATTERN,
        VERDICT_DIRECTORY_PATH_BOUNDARY_PATTERN,
        VERDICT_DIRECTORY_TARGET_BOUNDARY_PATTERN,
        VERDICT_PATH_GLUE_PATTERN,
    )

    from hooks_constants.hook_block_logger import log_hook_block
    from hooks_constants.pre_tool_use_stdin import (
        read_hook_input_dictionary_from_stdin,
    )
except ImportError as import_error:
    raise ImportError(
        "code_review_stamp_directory_write_blocker: cannot import its dependencies; "
        "ensure the blocking directory is importable."
    ) from import_error


def _stamp_file_relative_reference_pattern() -> str:
    """Build the ``code-review-stamps/<root-key>.json`` stamp-file shape pattern."""
    root_key_json_suffix = STAMP_FILE_ROOT_KEY_JSON_SUFFIX_PATTERN % ROOT_KEY_HEX_LENGTH
    return (
        f"{STAMP_FILE_REFERENCE_BOUNDARY_PREFIX_PATTERN}"
        f"{re.escape(STAMP_DIRECTORY_NAME)}{root_key_json_suffix}"
    )


def _references_absolute_stamp_path(command_text: str) -> bool:
    """Decide whether a command names an absolute stamp-directory path."""
    stamp_directory_pattern = re.compile(
        re.escape(CLAUDE_HOME_DIRECTORY_NAME)
        + VERDICT_DIRECTORY_NAME_SEPARATOR_PATTERN
        + re.escape(STAMP_DIRECTORY_NAME)
        + VERDICT_DIRECTORY_PATH_BOUNDARY_PATTERN,
        re.IGNORECASE,
    )
    return stamp_directory_pattern.search(command_text) is not None


def _changes_into_claude_home_then_writes_relative(command_text: str) -> bool:
    """Decide whether a command enters the Claude home then writes the stamp dir."""
    directory_change_into_claude_pattern = re.compile(
        directory_change_prefix()
        + DIRECTORY_CHANGE_TARGET_PATTERN
        + re.escape(CLAUDE_HOME_DIRECTORY_NAME)
        + CLAUDE_HOME_TARGET_BOUNDARY_PATTERN,
        re.IGNORECASE,
    )
    change_match = directory_change_into_claude_pattern.search(command_text)
    if change_match is None:
        return False
    relative_stamp_pattern = re.compile(RELATIVE_STAMP_DIRECTORY_PATTERN, re.IGNORECASE)
    return relative_stamp_pattern.search(command_text, change_match.end()) is not None


def _changes_into_stamp_directory_then_writes(command_text: str) -> bool:
    """Decide whether a command enters the stamp directory then runs a command."""
    directory_change_into_stamp_pattern = re.compile(
        directory_change_prefix()
        + DIRECTORY_CHANGE_TARGET_PATTERN
        + re.escape(CLAUDE_HOME_DIRECTORY_NAME)
        + r"[\\/]"
        + re.escape(STAMP_DIRECTORY_NAME)
        + VERDICT_DIRECTORY_TARGET_BOUNDARY_PATTERN,
        re.IGNORECASE,
    )
    change_match = directory_change_into_stamp_pattern.search(command_text)
    if change_match is None:
        return False
    command_after_change_pattern = re.compile(COMMAND_AFTER_DIRECTORY_CHANGE_PATTERN)
    return (
        command_after_change_pattern.search(command_text, change_match.end())
        is not None
    )


def _references_stamp_file_shape(command_text: str) -> bool:
    """Decide whether a command names a stamp file's ``<root-key>.json`` shape."""
    stamp_file_pattern = re.compile(
        _stamp_file_relative_reference_pattern(), re.IGNORECASE
    )
    return stamp_file_pattern.search(command_text) is not None


def _segments_join_as_stamp_path(command_text: str) -> bool:
    """Decide whether the two name segments sit adjacent in a path-join shape."""
    home_name = re.escape(CLAUDE_HOME_DIRECTORY_NAME)
    stamp_name = re.escape(STAMP_DIRECTORY_NAME)
    path_join_pattern = re.compile(
        home_name
        + VERDICT_PATH_GLUE_PATTERN
        + stamp_name
        + "|"
        + stamp_name
        + VERDICT_PATH_GLUE_PATTERN
        + home_name,
        re.IGNORECASE,
    )
    return path_join_pattern.search(command_text) is not None


def _writes_with_stamp_path_intent(command_text: str) -> bool:
    """Decide whether a write joins the two name segments into a stamp path."""
    has_non_redirect_write = (
        re.search(NON_REDIRECT_FILE_WRITE_PRIMITIVE_PATTERN, command_text) is not None
    )
    if not has_non_redirect_write:
        return False
    return _segments_join_as_stamp_path(command_text)


def _references_store_module_or_mint_call(command_text: str) -> bool:
    """Decide whether a command imports the stamp store or calls its mint call.

    ::

        python -c "from code_review_stamp_store import record_clean_stamp"  -> True
        python -c "record_clean_stamp(root, live_hash, 'xhigh')"            -> True
        python -m pytest test_code_review_stamp_store.py                    -> False

    A forge that re-implements the mint in-process names no stamp path, so the
    path matchers miss it. Matching the store import and the mint call closes
    that gap. A pytest run naming the store test file matches none of these.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        True when the command imports ``code_review_stamp_store`` or calls
        ``record_clean_stamp``; False otherwise.
    """
    for each_forge_pattern in ALL_STAMP_STORE_FORGE_PATTERNS:
        if re.search(each_forge_pattern, command_text):
            return True
    return False


def references_stamp_directory(command_text: str) -> bool:
    """Decide whether a command references the code-review stamp directory.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        True when the command names the stamp directory through any matcher — a
        store import or mint call, an absolute path, a cd-then-relative write, a
        cd into the directory, a split directory change into the directory, a
        stamp-file shape, a path-join write, or an obfuscation-decoded stamp
        segment; False otherwise.
    """
    if _references_store_module_or_mint_call(command_text):
        return True
    if _references_absolute_stamp_path(command_text):
        return True
    if _changes_into_claude_home_then_writes_relative(command_text):
        return True
    if _changes_into_stamp_directory_then_writes(command_text):
        return True
    if changes_through_split_directory_into_stamp(command_text):
        return True
    if _references_stamp_file_shape(command_text):
        return True
    if _writes_with_stamp_path_intent(command_text):
        return True
    return references_obfuscated_stamp_path(command_text)


def path_targets_stamp_directory(file_path: str) -> bool:
    """Decide whether a Write/Edit/MultiEdit path sits under the stamp directory.

    Args:
        file_path: The path the file tool targets.

    Returns:
        True when the resolved path is under ``~/.claude/code-review-stamps/``.
    """
    if not file_path:
        return False
    try:
        resolved_target = Path(file_path).expanduser().resolve()
        resolved_stamp_root = stamp_directory().resolve()
    except OSError:
        return False
    if resolved_target == resolved_stamp_root:
        return True
    try:
        resolved_target.relative_to(resolved_stamp_root)
    except ValueError:
        return False
    return True


def build_deny_payload() -> dict[str, dict[str, str]]:
    """Build the PreToolUse deny payload for a stamp-directory access."""
    return {
        "hookSpecificOutput": {
            "hookEventName": PRE_TOOL_USE_HOOK_EVENT_NAME,
            "permissionDecision": DENY_PERMISSION_DECISION,
            "permissionDecisionReason": STAMP_DIRECTORY_GUARD_MESSAGE,
        }
    }


def _shell_decision(all_tool_input: dict[str, object]) -> dict[str, dict[str, str]] | None:
    """Return the deny payload when a shell command targets the stamp directory."""
    command_text = all_tool_input.get("command", "")
    if not isinstance(command_text, str) or not command_text:
        return None
    if not references_stamp_directory(command_text):
        return None
    return build_deny_payload()


def _file_decision(all_tool_input: dict[str, object]) -> dict[str, dict[str, str]] | None:
    """Return the deny payload when a file-tool path targets the stamp directory."""
    file_path = all_tool_input.get("file_path", "")
    if not isinstance(file_path, str):
        return None
    if not path_targets_stamp_directory(file_path):
        return None
    return build_deny_payload()


def decision_for_payload(
    all_pretooluse_payload: dict[str, object],
) -> dict[str, dict[str, str]] | None:
    """Build the deny decision for stamp-directory shell or file-tool access.

    Args:
        all_pretooluse_payload: The PreToolUse hook payload.

    Returns:
        The deny decision mapping when a gated tool targets the stamp
        directory; None when the tool call may proceed.
    """
    tool_name = all_pretooluse_payload.get("tool_name", "")
    if not isinstance(tool_name, str):
        return None
    tool_input = all_pretooluse_payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return None
    if tool_name in ALL_GATED_SHELL_TOOL_NAMES:
        return _shell_decision(tool_input)
    if tool_name not in ALL_WRITE_EDIT_TOOL_NAMES:
        return None
    return _file_decision(tool_input)


def main() -> None:
    """Read the PreToolUse payload and deny stamp-directory access."""
    pretooluse_payload = read_hook_input_dictionary_from_stdin()
    if pretooluse_payload is None:
        return
    deny_decision = decision_for_payload(pretooluse_payload)
    if deny_decision is None:
        return
    raw_tool_name = pretooluse_payload.get("tool_name", "")
    tool_name_for_log = raw_tool_name if isinstance(raw_tool_name, str) else ""
    log_hook_block(
        calling_hook_name=STAMP_WRITE_BLOCKER_HOOK_MODULE_NAME,
        hook_event=PRE_TOOL_USE_HOOK_EVENT_NAME,
        block_reason=STAMP_DIRECTORY_GUARD_MESSAGE,
        tool_name=tool_name_for_log,
    )
    sys.stdout.write(json.dumps(deny_decision) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
