#!/usr/bin/env python3
"""PreToolUse hook: blocks Write/Edit containing historical/comparative language in comments and .md files.

Enforces the "describe current state only" rule — no "instead of", "previously",
"now uses", or similar transitional framing. Comments and documentation should
describe what IS, not what WAS or what CHANGED.
"""

import io
import json
import os
import sys
from pathlib import Path


def _insert_hooks_tree_for_imports() -> None:
    hooks_tree = Path(__file__).absolute().parent.parent
    hooks_tree_string = str(hooks_tree)
    if hooks_tree_string not in sys.path:
        sys.path.insert(0, hooks_tree_string)


_insert_hooks_tree_for_imports()

from config.state_description_blocker_constants import (
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


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if not isinstance(input_data, dict):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if not isinstance(tool_name, str):
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.exit(0)

    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not file_path or not (
        is_markdown_file(file_path) or is_comment_bearing_file(file_path)
    ):
        sys.exit(0)

    content_to_check = ""
    if tool_name == "Write":
        content_to_check = tool_input.get("content", "")
    elif tool_name == "Edit":
        content_to_check = tool_input.get("new_string", "")

    if not content_to_check:
        sys.exit(0)

    all_detected_patterns = find_violations(content_to_check, file_path)
    if not all_detected_patterns:
        sys.exit(0)

    formatted = ", ".join(f'"{p}"' for p in all_detected_patterns)

    block_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"Historical/comparative language detected in {file_path}: "
                f"{formatted}. Describe current state only — no 'instead of', "
                f"'previously', 'now uses', etc. The git log tracks what changed. "
                f"Comments and docs describe what IS."
            ),
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

    _emit_hook_result(block_payload, sys.stdout)
    sys.exit(0)


def _emit_hook_result(all_hook_data: dict, output_stream: io.TextIOBase) -> None:
    """Write the hook result JSON to the given output stream."""
    output_stream.write(json.dumps(all_hook_data) + "\n")
    output_stream.flush()


if __name__ == "__main__":
    main()
