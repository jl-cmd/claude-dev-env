#!/usr/bin/env python3
"""PreToolUse hook: blocks Write/Edit containing historical/comparative language in comments and .md files.

Enforces the "describe current state only" rule — no "instead of", "previously",
"now uses", or similar transitional framing. Comments and documentation should
describe what IS, not what WAS or what CHANGED.
"""

import json
import os
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin  # noqa: E402
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.state_description_blocker_constants import (  # noqa: E402
    ALL_BLOCK_COMMENT_EXTENSIONS,
    ALL_BLOCK_COMMENT_ONLY_EXTENSIONS,
    ALL_COMMENT_BEARING_EXTENSIONS,
    ALL_COMMENT_TRANSITION_PATTERNS,
    ALL_HASH_AND_SLASH_EXTENSIONS,
    ALL_HASH_ONLY_EXTENSIONS,
    ALL_MARKDOWN_EXTENSIONS,
    CODE_FENCE_PATTERN,
    INLINE_CODE_PATTERN,
)


def _get_file_extension(file_path: str) -> str:
    _, extension = os.path.splitext(file_path)
    return extension.lower()


def is_markdown_file(file_path: str) -> bool:
    return _get_file_extension(file_path) in ALL_MARKDOWN_EXTENSIONS


def is_comment_bearing_file(file_path: str) -> bool:
    return _get_file_extension(file_path) in ALL_COMMENT_BEARING_EXTENSIONS


def _get_inline_markers(extension: str) -> tuple[str, ...]:
    if extension in ALL_HASH_ONLY_EXTENSIONS:
        return ("#",)
    if extension in ALL_HASH_AND_SLASH_EXTENSIONS:
        return ("#", "//")
    if extension in ALL_BLOCK_COMMENT_ONLY_EXTENSIONS:
        return ()
    return ("//",)


def _extract_comment_lines(text: str, extension: str = "") -> list[str]:
    """Extract comment lines from source code — Python (#), JS/TS/C/Rust/Go (//), and block comments."""
    all_comment_lines: list[str] = []
    all_lines = text.splitlines()

    is_in_block_comment = False
    has_block_comments = extension in ALL_BLOCK_COMMENT_EXTENSIONS
    all_inline_markers = _get_inline_markers(extension)
    for each_line in all_lines:
        stripped = each_line.strip()

        if has_block_comments:
            if any(
                stripped.startswith(each_marker)
                for each_marker in all_inline_markers
            ):
                all_comment_lines.append(stripped)
                continue
            if "/*" in stripped and not is_in_block_comment:
                is_in_block_comment = True
                slash_star_index = stripped.find("/*")
                close_star_index = stripped.find("*/", slash_star_index + len("/*"))
                if close_star_index >= 0:
                    all_comment_lines.append(
                        stripped[slash_star_index : close_star_index + 2]
                    )
                    is_in_block_comment = False
                    after_close = stripped[close_star_index + 2:].lstrip()
                    if not after_close:
                        continue
                    stripped = after_close
                else:
                    all_comment_lines.append(stripped[slash_star_index:])
                    continue
            if is_in_block_comment:
                close_index = stripped.find("*/")
                if close_index >= 0:
                    all_comment_lines.append(stripped[: close_index + 2])
                    is_in_block_comment = False
                else:
                    all_comment_lines.append(stripped)
                    continue

        if any(
            stripped.startswith(each_marker) for each_marker in all_inline_markers
        ):
            all_comment_lines.append(stripped)
            continue

        inline_index = _find_inline_comment_start(stripped, all_inline_markers)
        if inline_index is not None and inline_index > 0:
            all_comment_lines.append(stripped[inline_index:])
            continue

    return all_comment_lines


def _find_inline_comment_start(stripped: str, all_markers: tuple[str, ...]) -> int | None:
    """Find the earliest inline comment marker in a code line, across all markers.
    Skips // when preceded by : to avoid treating URLs as inline comments,
    but continues searching for subsequent // that are actual comments."""
    best_position: int | None = None
    for each_marker in all_markers:
        search_start = 0
        while True:
            position = stripped.find(each_marker, search_start)
            if position <= 0:
                break
            if each_marker == "//" and stripped[position - 1] == ":":
                search_start = position + 1
                continue
            if best_position is None or position < best_position:
                best_position = position
            break
    return best_position


def find_violations(text: str, file_path: str) -> list[str]:
    """Return all violated patterns found in text for the given file.

    For .md files, scans the entire text. For code files, scans only comment lines.
    Returns a list of matched pattern source strings.
    """
    if is_markdown_file(file_path):
        scan_text = text
    elif is_comment_bearing_file(file_path):
        all_comment_lines = _extract_comment_lines(text, _get_file_extension(file_path))
        scan_text = "\n".join(all_comment_lines)
    else:
        return []

    if is_markdown_file(file_path):
        scan_text = CODE_FENCE_PATTERN.sub("", scan_text)
        scan_text = INLINE_CODE_PATTERN.sub("", scan_text)

    if not scan_text.strip():
        return []

    all_detected: list[str] = []
    all_transition_patterns = ALL_COMMENT_TRANSITION_PATTERNS
    for each_pattern in all_transition_patterns:
        all_matches = each_pattern.findall(scan_text)
        if all_matches:
            all_detected.append(all_matches[0].strip().lower())

    return all_detected


def _build_deny_reason(file_path: str, all_detected_patterns: list[str]) -> str:
    """Build the permissionDecisionReason text for a historical-language denial.

    Args:
        file_path: The target file path the violation was found in.
        all_detected_patterns: The matched historical/comparative phrases.

    Returns:
        The deny-reason text naming the file and the detected phrases.
    """
    formatted = ", ".join(f'"{each_pattern}"' for each_pattern in all_detected_patterns)
    return (
        f"Historical/comparative language detected in {file_path}: "
        f"{formatted}. Describe current state only — no 'instead of', "
        f"'previously', 'now uses', etc. The git log tracks what changed. "
        f"Comments and docs describe what IS."
    )


def evaluate(payload_by_key: dict[str, object]) -> str | None:
    """Decide whether a Write/Edit payload carries historical/comparative language.

    Applies the same tool-name gate, file-extension gate, content selection, and
    pattern scan the standalone hook applies. Returns the deny-reason text when a
    historical phrase is found, or None to allow.

    Args:
        payload_by_key: The PreToolUse payload with tool_name and tool_input.

    Returns:
        The permissionDecisionReason text when the write is denied, or None when
        the write is allowed.
    """
    raw_tool_name = payload_by_key.get("tool_name", "")
    tool_name = raw_tool_name if isinstance(raw_tool_name, str) else ""
    if tool_name not in ("Write", "Edit"):
        return None

    raw_tool_input = payload_by_key.get("tool_input", {})
    tool_input = raw_tool_input if isinstance(raw_tool_input, dict) else {}

    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not file_path:
        return None
    if not (is_markdown_file(file_path) or is_comment_bearing_file(file_path)):
        return None

    content_key = "content" if tool_name == "Write" else "new_string"
    raw_content = tool_input.get(content_key, "")
    content_to_check = raw_content if isinstance(raw_content, str) else ""
    if not content_to_check:
        return None

    all_detected_patterns = find_violations(content_to_check, file_path)
    if not all_detected_patterns:
        return None

    return _build_deny_reason(file_path, all_detected_patterns)


def build_deny_payload(deny_reason: str) -> dict[str, object]:
    """Build the full deny payload the hook writes for a deny-reason string.

    The payload carries the core permission decision plus the BAD/GOOD rewrite
    guidance in additionalContext, the user-facing systemMessage, and output
    suppression, so a caller routing this hook through a dispatcher reproduces
    the same deny shape the standalone hook writes.

    Args:
        deny_reason: The permissionDecisionReason text for the denial.

    Returns:
        The deny payload dictionary the hook serializes to stdout.
    """
    log_hook_block(
        calling_hook_name="state_description_blocker.py",
        hook_event="PreToolUse",
        block_reason=deny_reason,
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason,
            "additionalContext": (
                "Rewrite the affected comments or documentation to describe "
                "only the current state. For example:\n"
                '  BAD: "Uses X instead of Y"  →  GOOD: "Uses X"\n'
                '  BAD: "Previously configured via Z"  →  GOOD: "Configured via Z"\n'
                "See ~/.claude/rules/no-historical-clutter.md for full rules."
            ),
        },
        "systemMessage": "Agent wrote comparative/historical language - describe current state only",
        "suppressOutput": True,
    }


def main() -> None:
    payload_dictionary = read_hook_input_dictionary_from_stdin()
    if payload_dictionary is None:
        sys.exit(0)

    deny_reason = evaluate(payload_dictionary)
    if deny_reason is None:
        sys.exit(0)

    _emit_hook_result(build_deny_payload(deny_reason), sys.stdout)
    sys.exit(0)


def _emit_hook_result(all_hook_data: dict, output_stream: TextIO) -> None:
    """Write the hook result JSON to the given output stream."""
    output_stream.write(json.dumps(all_hook_data) + "\n")
    output_stream.flush()


if __name__ == "__main__":
    main()
