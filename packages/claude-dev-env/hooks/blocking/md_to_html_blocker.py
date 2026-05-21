#!/usr/bin/env python3
"""PreToolUse hook: blocks Write/Edit targeting .md files, redirecting to .html.

HTML preserves spatial structure (diffs, timelines, comparisons, diagrams)
that markdown flattens. See https://thariqs.github.io/html-effectiveness/
"""

import json
import os
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.md_to_html_blocker_constants import (  # noqa: E402
    ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES,
    CLAUDE_DEV_ENV_REPO_NAME_SEGMENT,
    MINIMUM_SEGMENT_COUNT_TO_MATCH_INDICATOR,
    PACKAGES_TOP_LEVEL_SEGMENT,
    WINDOWS_DRIVE_LETTER_SEGMENT_LENGTH,
)


_markdown_extension = ".md"
_html_effectiveness_url = "https://thariqs.github.io/html-effectiveness/"
_exempt_root_filenames = ("readme.md", "changelog.md")


def _looks_like_absolute_path(file_path: str, first_segment: str) -> bool:
    if file_path.startswith("/") or file_path.startswith("\\"):
        return True
    if (
        len(first_segment) == WINDOWS_DRIVE_LETTER_SEGMENT_LENGTH
        and first_segment[1] == ":"
        and first_segment[0].isalpha()
    ):
        return True
    return False


def _is_exempt_path(file_path: str) -> bool:
    normalized = os.path.normpath(file_path).replace("\\", "/")
    lower_normalized = normalized.lower()
    if "/.claude/" in lower_normalized or lower_normalized.startswith(".claude/"):
        return True
    all_segments = [each_segment for each_segment in lower_normalized.split("/") if each_segment]
    starting_segment_index_options: list[int] = [0]
    if all_segments and _looks_like_absolute_path(file_path, all_segments[0]):
        starting_segment_index_options = list(range(len(all_segments)))
    for each_starting_index in starting_segment_index_options:
        if (
            len(all_segments) >= each_starting_index + MINIMUM_SEGMENT_COUNT_TO_MATCH_INDICATOR
            and all_segments[each_starting_index] == PACKAGES_TOP_LEVEL_SEGMENT
            and all_segments[each_starting_index + 1] == CLAUDE_DEV_ENV_REPO_NAME_SEGMENT
            and all_segments[each_starting_index + 2] in ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES
        ):
            return True
    basename = os.path.basename(normalized)
    if basename.lower() in _exempt_root_filenames:
        directory = os.path.dirname(normalized)
        if directory in ("", "."):
            return True
    return False


def _block_reason(file_path: str) -> str:
    return (
        f"BLOCKED: Write/Edit to .md file '{file_path}' is not permitted. "
        "Use .html files instead for documentation. "
        f"See {_html_effectiveness_url} for why HTML "
        "is more effective than Markdown for structured information."
    )


def _block_context() -> str:
    return (
        "Generate a self-contained .html file instead of .md. "
        "Design freely — HTML can express spatial structure, interactivity, "
        "and visual hierarchy that markdown cannot.\n\n"
        "Reference for HTML effectiveness patterns:\n"
        f"{_html_effectiveness_url}\n"
        "Exceptions (.md still allowed):\n"
        "- Files inside .claude/ directories\n"
        "- README.md and CHANGELOG.md at repo root\n"
        "- packages/claude-dev-env/{agents,docs,skills,rules,system-prompts,commands}/ source files"
    )


def _block_system_message() -> str:
    return (
        ".md files are blocked in this project — generate a self-contained .html "
        f"file instead. See {_html_effectiveness_url} for "
        "design patterns and examples. Exemptions: .claude/ infrastructure, "
        "README.md, CHANGELOG.md at repo root, and "
        "packages/claude-dev-env/{agents,docs,skills,rules,system-prompts,commands}/ source files."
    )


def main() -> None:
    """Read hook input JSON from stdin, deny .md writes or pass through silently.

    Returns:
        None (exits process).
    """
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
    if not file_path:
        sys.exit(0)

    if not file_path.lower().endswith(_markdown_extension):
        sys.exit(0)

    if _is_exempt_path(file_path):
        sys.exit(0)

    block_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": _block_reason(file_path),
            "additionalContext": _block_context(),
        },
        "systemMessage": _block_system_message(),
        "suppressOutput": True,
    }

    _emit_hook_result(block_payload, sys.stdout)
    sys.exit(0)


def _emit_hook_result(all_hook_data: dict, output_stream: TextIO) -> None:
    output_stream.write(json.dumps(all_hook_data) + "\n")
    output_stream.flush()


if __name__ == "__main__":
    main()
