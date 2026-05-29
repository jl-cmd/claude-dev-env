#!/usr/bin/env python3
"""PreToolUse hook that blocks heavy words in AskUserQuestion prose and .md writes.

Reaches for the everyday word over the formal one: `use` over `utilize`,
`start` over `initiate`, `enough` over `sufficient`. Two surfaces are guarded --
AskUserQuestion (its question and option prose) and Write/Edit/MultiEdit targeting a .md
file. Code fences, inline code, blockquotes, URLs, and file paths are stripped
before matching so exact identifiers and paths are never flagged.

See the plain-language rule for the full guidance this hook enforces.
"""

import json
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.plain_language_blocker_constants import (  # noqa: E402
    ALL_SOFTWARE_TERMS,
    ALL_TERM_PATTERNS,
    ALL_WRITE_EDIT_TOOL_NAMES,
    ASK_USER_QUESTION_TOOL_NAME,
    BLOCKQUOTE_LINE_PATTERN,
    FENCED_CODE_BLOCK_PATTERN,
    FILE_PATH_PATTERN,
    INLINE_CODE_PATTERN,
    MARKDOWN_EXTENSION,
    URL_PATTERN,
    USER_FACING_PLAIN_LANGUAGE_NOTICE,
)


def strip_non_prose_regions(text: str) -> str:
    """Return text with code, quotes, URLs, and file paths removed.

    These regions carry exact identifiers and references that plain language
    leaves untouched, so they must not contribute matches.
    """
    without_fences = FENCED_CODE_BLOCK_PATTERN.sub("", text)
    without_inline_code = INLINE_CODE_PATTERN.sub("", without_fences)
    without_blockquotes = BLOCKQUOTE_LINE_PATTERN.sub("", without_inline_code)
    without_urls = URL_PATTERN.sub("", without_blockquotes)
    without_paths = FILE_PATH_PATTERN.sub("", without_urls)
    return without_paths


def find_banned_terms(text: str) -> list[tuple[str, str]]:
    """Return each (matched term, suggested replacement) found in the prose.

    Each term appears at most once, in first-seen order. Matching is
    case-insensitive and respects word boundaries; multi-word phrases match as
    whole units. Terms in the software-term allowlist are exempt and never
    flagged.
    """
    prose_text = strip_non_prose_regions(text)
    all_matches: list[tuple[str, str]] = []
    seen_terms: set[str] = set()
    for each_pattern, each_replacement in ALL_TERM_PATTERNS:
        first_match = each_pattern.search(prose_text)
        if first_match is None:
            continue
        normalized_term = first_match.group(0).lower()
        if normalized_term in seen_terms:
            continue
        if normalized_term in ALL_SOFTWARE_TERMS:
            continue
        seen_terms.add(normalized_term)
        all_matches.append((normalized_term, each_replacement))
    return all_matches


def build_block_reason(all_matches: list[tuple[str, str]]) -> str:
    """Return a deny reason naming each flagged term and its plain replacement."""
    swap_phrases = ", ".join(
        f'use "{each_replacement}" instead of "{each_term}"'
        for each_term, each_replacement in all_matches
    )
    return (
        "BLOCKED: [PLAIN_LANGUAGE] Heavy words detected -- "
        f"{swap_phrases}. Reach for the everyday word the reader understands "
        "on the first pass."
    )


def _collect_ask_user_question_prose(tool_input: dict) -> str:
    all_questions = tool_input.get("questions", [])
    if not isinstance(all_questions, list):
        return ""
    prose_segments: list[str] = []
    for each_question in all_questions:
        if not isinstance(each_question, dict):
            continue
        question_text = each_question.get("question", "")
        if isinstance(question_text, str):
            prose_segments.append(question_text)
        all_options = each_question.get("options", [])
        if isinstance(all_options, list):
            for each_option in all_options:
                if isinstance(each_option, dict):
                    option_label = each_option.get("label", "")
                    if isinstance(option_label, str):
                        prose_segments.append(option_label)
                    option_description = each_option.get("description", "")
                    if isinstance(option_description, str):
                        prose_segments.append(option_description)
    return "\n".join(prose_segments)


def _collect_write_edit_markdown_prose(tool_name: str, tool_input: dict) -> str:
    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not file_path.lower().endswith(MARKDOWN_EXTENSION):
        return ""
    if tool_name == "Write":
        content = tool_input.get("content", "")
        return content if isinstance(content, str) else ""
    if tool_name == "Edit":
        new_string = tool_input.get("new_string", "")
        return new_string if isinstance(new_string, str) else ""
    all_edits = tool_input.get("edits", [])
    if not isinstance(all_edits, list):
        return ""
    prose_segments: list[str] = []
    for each_edit in all_edits:
        if isinstance(each_edit, dict):
            new_string = each_edit.get("new_string", "")
            if isinstance(new_string, str):
                prose_segments.append(new_string)
    return "\n".join(prose_segments)


def _collect_prose_for_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == ASK_USER_QUESTION_TOOL_NAME:
        return _collect_ask_user_question_prose(tool_input)
    if tool_name in ALL_WRITE_EDIT_TOOL_NAMES:
        return _collect_write_edit_markdown_prose(tool_name, tool_input)
    return ""


def _emit_deny(all_matches: list[tuple[str, str]], output_stream: TextIO) -> None:
    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": build_block_reason(all_matches),
        },
        "systemMessage": USER_FACING_PLAIN_LANGUAGE_NOTICE,
        "suppressOutput": True,
    }
    output_stream.write(json.dumps(deny_payload))
    output_stream.flush()


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if not isinstance(input_data, dict):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    if not isinstance(tool_name, str) or not isinstance(tool_input, dict):
        sys.exit(0)

    prose_text = _collect_prose_for_tool(tool_name, tool_input)
    if not prose_text:
        sys.exit(0)

    all_matches = find_banned_terms(prose_text)
    if not all_matches:
        sys.exit(0)

    _emit_deny(all_matches, sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
