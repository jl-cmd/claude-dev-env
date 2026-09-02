#!/usr/bin/env python3
"""PreToolUse hook that checks AskUserQuestion prose when enabled."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from blocking.config.prose_style_enforcement_constants import (  # noqa: E402
    prose_style_enforcement_enabled_in_environment,
)
from hooks_constants.ask_user_question_shape_constants import (  # noqa: E402
    ASK_USER_QUESTION_TOOL_NAME,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.plain_language_blocker_constants import (  # noqa: E402
    ALL_PLAIN_LANGUAGE_TERM_PATTERNS,
    FENCED_CODE_PATTERN,
    FILE_PATH_PATTERN,
    INLINE_CODE_PATTERN,
    PLAIN_LANGUAGE_BLOCK_PREFIX,
    PLAIN_LANGUAGE_NOTICE,
    PLAIN_LANGUAGE_TERM_SEPARATOR,
    URL_PATTERN,
)
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)


def strip_non_prose_regions(text: str) -> str:
    """Remove exact code, URL, and path regions before scanning prose."""
    without_fenced_code = FENCED_CODE_PATTERN.sub(" ", text)
    without_inline_code = INLINE_CODE_PATTERN.sub(" ", without_fenced_code)
    without_urls = URL_PATTERN.sub(" ", without_inline_code)
    return FILE_PATH_PATTERN.sub(" ", without_urls)

def find_banned_terms(text: str) -> list[tuple[str, str]]:
    """Return each detected formal term and its familiar replacement."""
    prose_text = strip_non_prose_regions(text)
    all_matches: list[tuple[str, str]] = []
    seen_terms: set[str] = set()
    for each_pattern, each_replacement in ALL_PLAIN_LANGUAGE_TERM_PATTERNS:
        match = each_pattern.search(prose_text)
        if match is None:
            continue
        matched_term = match.group(0).lower()
        if matched_term in seen_terms:
            continue
        seen_terms.add(matched_term)
        all_matches.append((matched_term, each_replacement))
    return all_matches


def _question_prose(payload_by_key: Mapping[str, object]) -> list[str]:
    """Return question and option-description prose from a tool payload."""
    raw_tool_input = payload_by_key.get("tool_input", {})
    if not isinstance(raw_tool_input, Mapping):
        return []
    raw_questions = raw_tool_input.get("questions", [])
    if not isinstance(raw_questions, Sequence) or isinstance(
        raw_questions, (str, bytes)
    ):
        return []
    all_prose: list[str] = []
    for each_raw_question in raw_questions:
        if not isinstance(each_raw_question, Mapping):
            continue
        question = each_raw_question.get("question")
        if isinstance(question, str):
            all_prose.append(question)
        raw_options = each_raw_question.get("options", [])
        if not isinstance(raw_options, Sequence) or isinstance(
            raw_options, (str, bytes)
        ):
            continue
        for each_raw_option in raw_options:
            if not isinstance(each_raw_option, Mapping):
                continue
            description = each_raw_option.get("description")
            if isinstance(description, str):
                all_prose.append(description)
    return all_prose


def evaluate(payload_by_key: Mapping[str, object]) -> str | None:
    """Return a deny reason for formal AskUserQuestion prose."""
    if not prose_style_enforcement_enabled_in_environment():
        return None
    if payload_by_key.get("tool_name") != ASK_USER_QUESTION_TOOL_NAME:
        return None
    all_matches: list[tuple[str, str]] = []
    for each_prose in _question_prose(payload_by_key):
        for each_match in find_banned_terms(each_prose):
            if each_match not in all_matches:
                all_matches.append(each_match)
    if not all_matches:
        return None
    return build_block_reason(all_matches)


def build_block_reason(all_matches: Sequence[tuple[str, str]]) -> str:
    """Build a concise denial reason with one replacement per detected term."""
    swaps = PLAIN_LANGUAGE_TERM_SEPARATOR.join(
        f"{term} -> {replacement}" for term, replacement in all_matches
    )
    return f"{PLAIN_LANGUAGE_BLOCK_PREFIX}{swaps}."


def build_deny_payload(deny_reason: str) -> dict[str, object]:
    """Build the standard PreToolUse deny response."""
    log_hook_block(
        calling_hook_name="plain_language_blocker.py",
        hook_event="PreToolUse",
        block_reason=deny_reason,
        tool_name=ASK_USER_QUESTION_TOOL_NAME,
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason,
        },
        "systemMessage": PLAIN_LANGUAGE_NOTICE,
        "suppressOutput": True,
    }


def main() -> None:
    """Read one hook payload and emit a deny response when needed."""
    payload_by_key = read_hook_input_dictionary_from_stdin()
    if payload_by_key is None:
        return
    deny_reason = evaluate(payload_by_key)
    if deny_reason is None:
        return
    sys.stdout.write(json.dumps(build_deny_payload(deny_reason)) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
