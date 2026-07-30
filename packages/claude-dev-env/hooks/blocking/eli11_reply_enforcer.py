#!/usr/bin/env python3
"""
Stop hook that blocks egregious reply-shape failures (action-first, bullets).

The `eli11-replies` and `opus5-communication-contract` rules ask every chat
reply to lead with the action when the user must act, keep findings to a few
bullets, and stay scannable. This hook reads the final assistant message,
strips code fences, inline code, blockquotes, table rows, and link targets,
then judges shape only: multi-line instructions need numbered steps first,
bullet count stays bounded, and list lines stay one-idea short. There is no
minimum-word floor and no universal word ceiling — a concise answer and a
requested full report both pass when shape is clean.
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
    ALL_IMPERATIVE_OBJECT_LEAD_WORDS,
    ALPHABETIC_WORD_PATTERN,
    BULLET_LINE_PATTERN,
    COUNTABLE_WORD_PATTERN,
    IMPERATIVE_OBJECT_TOKEN_PATTERN,
    LINK_TARGET_PATTERN,
    LIST_MARKER_PREFIX_PATTERN,
    MARKDOWN_LEAD_MARKER_PATTERN,
    MAXIMUM_BULLET_LINE_COUNT,
    MAXIMUM_OVERPACKED_LIST_LINE_COUNT,
    MAXIMUM_WORDS_PER_LIST_LINE,
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


def object_word_after_leading_verb(prose_line: str) -> str:
    """Return the word a line puts right after its opening verb.

    ::

        in:  "Run the migration script."
        out: "the"

    Args:
        prose_line: One non-empty line of reply prose.

    Returns:
        The lowercased token following the first alphabetic word, or an empty
        string when the line carries no such token.
    """
    unmarked_line = LIST_MARKER_PREFIX_PATTERN.sub("", prose_line, count=1)
    leading_word_match = ALPHABETIC_WORD_PATTERN.search(unmarked_line)
    if leading_word_match is None:
        return ""
    all_trailing_tokens = COUNTABLE_WORD_PATTERN.findall(
        unmarked_line[leading_word_match.end():]
    )
    if not all_trailing_tokens:
        return ""
    return all_trailing_tokens[0].lower()


def names_imperative_object(object_word: str) -> bool:
    """Return True when a word reads as the thing an imperative acts on.

    ::

        ok:   "the" (Run the script), "3" (Do 3 things), "scripts/run.py"
        flag: "questions" (Open questions remain), "is" (Merge is complete)

    An imperative names its object through a determiner, a count, a path, or a
    filename; a narrative sentence puts a bare subject noun there instead.

    Args:
        object_word: The lowercased word following a line's opening verb.

    Returns:
        True when the word marks the opening verb as a real imperative.
    """
    if not object_word:
        return False
    if object_word in ALL_IMPERATIVE_OBJECT_LEAD_WORDS:
        return True
    return IMPERATIVE_OBJECT_TOKEN_PATTERN.search(object_word) is not None


def is_imperative_instruction_line(prose_line: str) -> bool:
    """Return True when a line tells the user to act.

    ::

        ok:   "Open questions remain about the stripper." -> False
        flag: "Open the pull request."                    -> True

    Args:
        prose_line: One non-empty line of reply prose.

    Returns:
        True when the line opens with a tracked instruction verb naming an
        object an imperative acts on.
    """
    if leading_word_of(prose_line) not in ALL_IMPERATIVE_INSTRUCTION_VERBS:
        return False
    return names_imperative_object(object_word_after_leading_verb(prose_line))


def has_imperative_instruction_line(all_prose_lines: list[str]) -> bool:
    """Return True when any line opens with a verb telling the user to act.

    Args:
        all_prose_lines: The non-empty lines of reply prose.

    Returns:
        True when a line reads as an imperative instruction.
    """
    return any(
        is_imperative_instruction_line(each_line) for each_line in all_prose_lines
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


def count_words_in_line(prose_line: str) -> int:
    """Return the countable words a line carries once its list marker comes off.

    ::

        in:  "- **Save** the draft"
        out: 3

    Args:
        prose_line: One non-empty line of reply prose.

    Returns:
        The count of tokens carrying a letter or digit, marker text excluded.
    """
    unmarked_line = LIST_MARKER_PREFIX_PATTERN.sub("", prose_line, count=1)
    return len(COUNTABLE_WORD_PATTERN.findall(unmarked_line))


def strip_markdown_lead_markers(prose_line: str) -> str:
    """Return a line with its opening blockquote, heading, and bold markers off.

    ::

        in:  "> **Bold lead:** the report follows"
        out: "Bold lead:** the report follows"

    Args:
        prose_line: One line of raw reply text.

    Returns:
        The line with every leading markdown marker and its padding removed.
    """
    return MARKDOWN_LEAD_MARKER_PATTERN.sub("", prose_line.strip(), count=1)


def is_list_item_line(prose_line: str) -> bool:
    """Return True when a line is a bullet or numbered list item.

    Args:
        prose_line: One non-empty line of reply prose.

    Returns:
        True when the line opens with a bullet or numbered-step marker.
    """
    if BULLET_LINE_PATTERN.match(prose_line):
        return True
    return NUMBERED_STEP_PATTERN.match(prose_line) is not None


def count_overpacked_list_lines(all_prose_lines: list[str]) -> int:
    """Return how many list lines carry more words than one idea needs.

    Plain paragraphs are not counted so a requested full report can use long
    prose lines without a word ceiling.

    Args:
        all_prose_lines: The non-empty lines of reply prose.

    Returns:
        The count of bullet/numbered lines over the per-list-line word cap.
    """
    return sum(
        1
        for each_line in all_prose_lines
        if is_list_item_line(each_line)
        and count_words_in_line(each_line) > MAXIMUM_WORDS_PER_LIST_LINE
    )


def describe_bullet_cap_violation(bullet_line_count: int) -> str:
    """Return the violation text naming the bullet count and the target."""
    return (
        f"{bullet_line_count} bullets, over the {MAXIMUM_BULLET_LINE_COUNT}-bullet "
        f"cap - put findings in at most {TARGET_BULLET_LINE_COUNT} bullets"
    )


def describe_overpacked_list_line_violation(overpacked_line_count: int) -> str:
    """Return the violation text for overpacked list lines."""
    return (
        f"{overpacked_line_count} list lines carry too many words - one idea per "
        f"bullet or step, at most {MAXIMUM_WORDS_PER_LIST_LINE} words each"
    )


def describe_action_first_violation() -> str:
    """Return the violation text for instructions buried under prose."""
    return (
        "the reply tells the user to act but leads with prose - open with "
        "numbered steps, one short line each"
    )


def is_action_first_violation(all_prose_lines: list[str]) -> bool:
    """Return True when multi-line instructions lack leading numbered steps.

    ::

        ok:   single-line "Run the migration." -> False
        ok:   numbered steps first, then prose -> False
        flag: prose then "Install the package." -> True

    Args:
        all_prose_lines: The non-empty lines of reply prose.

    Returns:
        True when the reply has more than one line, carries instruction
        lines, and shows no numbered step among its lead lines.
    """
    if len(all_prose_lines) <= 1:
        return False
    if not has_imperative_instruction_line(all_prose_lines):
        return False
    return not has_leading_numbered_step(all_prose_lines)


def collect_shape_violations(all_prose_lines: list[str]) -> list[str]:
    """Return the violation texts for every reply-shape rule the reply breaks.

    Args:
        all_prose_lines: The non-empty lines of reply prose.

    Returns:
        One violation text per broken rule, empty when the reply is in shape.
    """
    all_violations: list[str] = []
    if is_action_first_violation(all_prose_lines):
        all_violations.append(describe_action_first_violation())
    bullet_line_count = count_bullet_lines(all_prose_lines)
    if bullet_line_count > MAXIMUM_BULLET_LINE_COUNT:
        all_violations.append(describe_bullet_cap_violation(bullet_line_count))
    overpacked_list_line_count = count_overpacked_list_lines(all_prose_lines)
    if overpacked_list_line_count > MAXIMUM_OVERPACKED_LIST_LINE_COUNT:
        all_violations.append(
            describe_overpacked_list_line_violation(overpacked_list_line_count)
        )
    return all_violations


def find_reply_shape_violations(assistant_message: str) -> list[str]:
    """Return every reply-shape violation the final assistant message carries.

    ::

        ok:   a short outcome sentence              -> []
        ok:   a long requested audit with few bullets -> []
        flag: prose then buried "Install the package." -> [action-first]

    There is no minimum-word floor and no universal word ceiling.

    Args:
        assistant_message: The raw final assistant message.

    Returns:
        One violation text per broken rule, empty when the reply is in shape.
    """
    prose_text = extract_reply_prose(assistant_message)
    return collect_shape_violations(collect_non_empty_lines(prose_text))


def build_block_reason(all_violations: list[str]) -> str:
    """Return the corrective message naming each violation and the rewrite path.

    Args:
        all_violations: The violation texts the reply earned.

    Returns:
        The full block reason the model rewrites its reply against.
    """
    formatted_violation_list = VIOLATION_SEPARATOR.join(all_violations)
    return (
        f"ELI11 REPLY SHAPE: Rewrite the reply into a short action-first shape "
        f"({formatted_violation_list}).\n\n"
        f"When the user must act, open with numbered click-by-click steps, one "
        f"short line each. When nothing is needed, open with the outcome in one "
        f"sentence. Keep findings to at most {TARGET_BULLET_LINE_COUNT} short "
        f"bullets. A requested full report may run long; keep list lines short "
        f"and lead with the outcome. Code fences, blockquotes, tables, and "
        f"links are already exempt from shape counting.\n\n"
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
