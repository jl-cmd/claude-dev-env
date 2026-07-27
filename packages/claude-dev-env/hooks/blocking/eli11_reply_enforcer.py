#!/usr/bin/env python3
"""
Stop hook that blocks a final reply breaking the short action-first reply shape.

The `eli11-replies` rule asks every chat reply to lead with the action, keep
findings to a few bullets, and stay short. This hook reads the final assistant
message, strips code fences, inline code, blockquotes, table rows, and link
targets, then judges what a reader actually sees: the word count against a hard
cap, whether numbered steps lead a reply that tells the user to act, and the
number of bullet lines. A reply opening with "Long form:" opts out, so a
user-requested full report still goes through.
"""

import json
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.eli11_reply_enforcer_constants import (  # noqa: E402
    ACTION_FIRST_LEAD_LINE_COUNT,
    ALL_IMPERATIVE_INSTRUCTION_VERBS,
    ALPHABETIC_WORD_PATTERN,
    BULLET_LINE_PATTERN,
    COUNTABLE_WORD_PATTERN,
    LINK_TARGET_PATTERN,
    LIST_MARKER_PREFIX_PATTERN,
    LONG_FORM_ESCAPE_PREFIX,
    MAXIMUM_BULLET_LINE_COUNT,
    MAXIMUM_REPLY_WORD_COUNT,
    MINIMUM_ENFORCED_WORD_COUNT,
    NUMBERED_STEP_PATTERN,
    TABLE_ROW_PATTERN,
    TARGET_BULLET_LINE_COUNT,
    USER_FACING_ELI11_NOTICE,
    VIOLATION_SEPARATOR,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.text_stripping import strip_code_and_quotes  # noqa: E402


def extract_reply_prose(assistant_message: str) -> str:
    """Return the reader-visible prose of a reply.

    ::

        in:  "See https://example.com/a now"
        out: "See  now"

    Fenced code, inline code, and blockquotes come off through the shared
    stripper; table rows and link targets come off here.

    Args:
        assistant_message: The raw final assistant message.

    Returns:
        The message with code, quotes, table rows, and link targets removed.
    """
    prose_text = strip_code_and_quotes(assistant_message)
    prose_text = TABLE_ROW_PATTERN.sub("", prose_text)
    return LINK_TARGET_PATTERN.sub("", prose_text)


def count_reply_words(prose_text: str) -> int:
    """Return the number of reader-visible words in the stripped prose.

    Args:
        prose_text: Prose already cleaned of code, quotes, tables, and links.

    Returns:
        The count of whitespace-separated tokens carrying a letter or digit.
    """
    return len(COUNTABLE_WORD_PATTERN.findall(prose_text))


def collect_non_empty_lines(prose_text: str) -> list[str]:
    """Return every line of the stripped prose that carries visible text.

    Args:
        prose_text: Prose already cleaned of code, quotes, tables, and links.

    Returns:
        The lines with content, in order, blank lines dropped.
    """
    return [
        each_line for each_line in prose_text.splitlines() if each_line.strip()
    ]


def leading_word_of(prose_line: str) -> str:
    """Return the first word of a line once list and bold markers come off.

    ::

        in:  "- **Click** Save"
        out: "click"

    Args:
        prose_line: One non-empty line of reply prose.

    Returns:
        The lowercased first alphabetic word, or an empty string when the line
        carries no letters.
    """
    unmarked_line = LIST_MARKER_PREFIX_PATTERN.sub("", prose_line, count=1)
    all_leading_words = ALPHABETIC_WORD_PATTERN.findall(unmarked_line)
    if not all_leading_words:
        return ""
    return all_leading_words[0].lower()


def has_imperative_instruction_line(all_prose_lines: list[str]) -> bool:
    """Return True when any line opens with a verb telling the user to act.

    Args:
        all_prose_lines: The non-empty lines of reply prose.

    Returns:
        True when a line starts with one of the tracked instruction verbs.
    """
    return any(
        leading_word_of(each_line) in ALL_IMPERATIVE_INSTRUCTION_VERBS
        for each_line in all_prose_lines
    )


def has_leading_numbered_step(all_prose_lines: list[str]) -> bool:
    """Return True when a numbered step appears among the lead lines.

    Args:
        all_prose_lines: The non-empty lines of reply prose.

    Returns:
        True when one of the first lead lines opens a numbered list.
    """
    all_lead_lines = all_prose_lines[:ACTION_FIRST_LEAD_LINE_COUNT]
    return any(
        NUMBERED_STEP_PATTERN.match(each_line) for each_line in all_lead_lines
    )


def count_bullet_lines(all_prose_lines: list[str]) -> int:
    """Return how many lines of the reply are bullets.

    Args:
        all_prose_lines: The non-empty lines of reply prose.

    Returns:
        The count of lines opening with a bullet marker.
    """
    return sum(
        1 for each_line in all_prose_lines if BULLET_LINE_PATTERN.match(each_line)
    )


def opens_with_long_form_escape(assistant_message: str) -> bool:
    """Return True when the reply opts out through the Long form prefix.

    Args:
        assistant_message: The raw final assistant message.

    Returns:
        True when the first line with content starts with the escape prefix.
    """
    for each_line in assistant_message.splitlines():
        if not each_line.strip():
            continue
        return each_line.strip().lower().startswith(LONG_FORM_ESCAPE_PREFIX)
    return False


def describe_word_cap_violation(reply_word_count: int) -> str:
    """Return the violation text naming the reply length and the cap."""
    return (
        f"{reply_word_count} words, over the {MAXIMUM_REPLY_WORD_COUNT}-word cap"
    )


def describe_bullet_cap_violation(bullet_line_count: int) -> str:
    """Return the violation text naming the bullet count and the target."""
    return (
        f"{bullet_line_count} bullets, over the {MAXIMUM_BULLET_LINE_COUNT}-bullet "
        f"cap - cut findings to {TARGET_BULLET_LINE_COUNT} bullets"
    )


def describe_action_first_violation() -> str:
    """Return the violation text for instructions buried under prose."""
    return (
        "the reply tells the user to act but leads with prose - put the steps "
        "first, as a numbered list"
    )


def is_action_first_violation(
    reply_word_count: int, all_prose_lines: list[str]
) -> bool:
    """Return True when instructions sit below the lead of a long reply.

    Args:
        reply_word_count: The reader-visible word count of the reply.
        all_prose_lines: The non-empty lines of reply prose.

    Returns:
        True when the reply is long, carries instruction lines, and shows no
        numbered step among its lead lines.
    """
    if reply_word_count <= MINIMUM_ENFORCED_WORD_COUNT:
        return False
    if not has_imperative_instruction_line(all_prose_lines):
        return False
    return not has_leading_numbered_step(all_prose_lines)


def collect_shape_violations(
    reply_word_count: int, all_prose_lines: list[str]
) -> list[str]:
    """Return the violation texts for every reply-shape rule the reply breaks.

    Args:
        reply_word_count: The reader-visible word count of the reply.
        all_prose_lines: The non-empty lines of reply prose.

    Returns:
        One violation text per broken rule, empty when the reply is in shape.
    """
    all_violations: list[str] = []
    if reply_word_count > MAXIMUM_REPLY_WORD_COUNT:
        all_violations.append(describe_word_cap_violation(reply_word_count))
    if is_action_first_violation(reply_word_count, all_prose_lines):
        all_violations.append(describe_action_first_violation())
    bullet_line_count = count_bullet_lines(all_prose_lines)
    if bullet_line_count > MAXIMUM_BULLET_LINE_COUNT:
        all_violations.append(describe_bullet_cap_violation(bullet_line_count))
    return all_violations


def find_reply_shape_violations(assistant_message: str) -> list[str]:
    """Return every reply-shape violation the final assistant message carries.

    ::

        ok:   a 40-word outcome sentence -> []
        flag: a 260-word wall            -> ["260 words, over the 220-word cap"]

    A reply opening with the escape prefix, and a reply under the enforced word
    floor, are both returned as in shape.

    Args:
        assistant_message: The raw final assistant message.

    Returns:
        One violation text per broken rule, empty when the reply is in shape.
    """
    if opens_with_long_form_escape(assistant_message):
        return []
    prose_text = extract_reply_prose(assistant_message)
    reply_word_count = count_reply_words(prose_text)
    if reply_word_count < MINIMUM_ENFORCED_WORD_COUNT:
        return []
    return collect_shape_violations(
        reply_word_count, collect_non_empty_lines(prose_text)
    )


def build_block_reason(all_violations: list[str]) -> str:
    """Return the corrective message naming each violation and the escape hatch.

    Args:
        all_violations: The violation texts the reply earned.

    Returns:
        The full block reason the model rewrites its reply against.
    """
    formatted_violation_list = VIOLATION_SEPARATOR.join(all_violations)
    return (
        f"ELI11 REPLY SHAPE: Your reply breaks the short action-first shape "
        f"({formatted_violation_list}).\n\n"
        f"Rewrite it short. When the user must act, open with numbered "
        f"click-by-click steps, one short line each. When nothing is needed, open "
        f"with the outcome in one sentence. Keep findings to at most "
        f"{TARGET_BULLET_LINE_COUNT} short bullets and stay under "
        f"{MAXIMUM_REPLY_WORD_COUNT} words. Code fences, blockquotes, tables, and "
        f"links are already exempt from the count.\n\n"
        f"When the user asked for a full report, start the reply with "
        f'"Long form:" to opt out of this check.\n\n'
        f"You MUST re-output the complete, revised response with the correction "
        f"applied."
    )


def main() -> None:
    """Read the Stop payload and block a reply that breaks the ELI11 shape."""
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if hook_input.get("stop_hook_active", False):
        sys.exit(0)

    assistant_message = hook_input.get("last_assistant_message", "")

    if not assistant_message:
        sys.exit(0)

    all_violations = find_reply_shape_violations(assistant_message)

    if not all_violations:
        sys.exit(0)

    block_reason = build_block_reason(all_violations)
    block_response = {
        "decision": "block",
        "reason": block_reason,
        "systemMessage": USER_FACING_ELI11_NOTICE,
        "suppressOutput": True,
    }
    log_hook_block(
        calling_hook_name="eli11_reply_enforcer.py",
        hook_event="Stop",
        block_reason=block_reason,
    )
    print(json.dumps(block_response))
    sys.exit(0)


if __name__ == "__main__":
    main()
