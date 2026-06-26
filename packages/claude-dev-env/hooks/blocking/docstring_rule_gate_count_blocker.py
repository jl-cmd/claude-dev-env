#!/usr/bin/env python3
"""PreToolUse hook: blocks a stale gate-validator count in the docstring-prose rule.

The rule ``docstring-prose-matches-implementation.md`` enumerates the
``check_docstring_*`` gate validators that cover deterministic slices of docstring
prose, both as a spelled-out count ("Four more gate validators", "five gated
slices") and as a backticked list of the validator names. When a new gate
validator is registered but the count word is left unchanged, the rule's stated
count drifts from the validators it actually names — the same companion-doc drift
the rule itself governs. This hook fires on a Write, Edit, or MultiEdit targeting
that rule file and blocks the write when the spelled-out "<count> more gate
validators" count disagrees with the number of distinct free-form validators the
prose names, or when the "<count> gated slices" total is not that count plus one
(the count plus the ``Args:`` gate). An edit that leaves the count words and the
named-validator list in step is allowed.
"""

import json
import os
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.docstring_rule_gate_count_blocker_constants import (  # noqa: E402
    ALL_NUMBER_WORDS_BY_VALUE,
    ARGS_GATE_VALIDATOR_NAME,
    CODE_FENCE_PATTERN,
    FREE_FORM_GATE_COUNT_PATTERN,
    GATE_COUNT_ADDITIONAL_CONTEXT,
    GATE_COUNT_MESSAGE_TEMPLATE,
    GATE_COUNT_SYSTEM_MESSAGE,
    GATE_VALIDATOR_NAME_PATTERN,
    MAX_GATE_COUNT_ISSUES,
    TARGET_RULE_BASENAME,
    TOTAL_GATED_SLICE_COUNT_PATTERN,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.multi_edit_reconstruction import (  # noqa: E402
    apply_edits,
    edits_for_tool,
)
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)


def is_target_rule_file(file_path: str) -> bool:
    """Return whether *file_path* names the docstring-prose rule this hook guards.

    Args:
        file_path: The destination path of the write or edit.

    Returns:
        True when the path's basename is the target rule basename.
    """
    return os.path.basename(file_path) == TARGET_RULE_BASENAME


def _lines_outside_code_fences(content: str) -> list[str]:
    """Return the rule lines that sit outside any fenced code block.

    A line inside a ``` or ~~~ fence pair is example or sample text, not a live
    enumeration, so it is dropped. This mirrors the fence handling in the sibling
    inventory and orphan-file blockers.

    Args:
        content: The full rule-file text being written.

    Returns:
        The lines that lie outside every code fence, in document order.
    """
    live_lines: list[str] = []
    is_inside_code_fence = False
    for each_line in content.splitlines():
        if CODE_FENCE_PATTERN.match(each_line) is not None:
            is_inside_code_fence = not is_inside_code_fence
            continue
        if is_inside_code_fence:
            continue
        live_lines.append(each_line)
    return live_lines


def _named_free_form_validators(enumeration_window: str) -> list[str]:
    """Return the distinct free-form gate validators an enumeration window names.

    The window is the prose between the "<count> more gate validators" phrase and
    the "<count> gated slices" total — the span where the rule enumerates its
    free-form gates. Every backticked ``check_*`` token in that window is
    collected, the ``Args:`` gate (``check_docstring_args_match_signature``) is
    removed since it is counted separately as part of the total rather than the
    "more gate validators" tally, and duplicates are dropped while first-seen order
    is preserved. Scoping to the window keeps a validator named only in the
    worked-example or enforcement sections from inflating the count.

    Args:
        enumeration_window: The prose between the two count clauses.

    Returns:
        Each distinct free-form gate validator name, in first-seen order.
    """
    all_named_validators: list[str] = []
    already_seen: set[str] = set()
    for each_match in GATE_VALIDATOR_NAME_PATTERN.finditer(enumeration_window):
        validator_name = each_match.group(1)
        if validator_name == ARGS_GATE_VALIDATOR_NAME:
            continue
        if validator_name in already_seen:
            continue
        already_seen.add(validator_name)
        all_named_validators.append(validator_name)
    return all_named_validators


def _count_word_value(count_word: str) -> int | None:
    """Return the integer a spelled-out count word names, or None when unknown.

    Args:
        count_word: The captured count word, such as ``four``.

    Returns:
        The integer the word maps to, or None when the word is not a known
        spelled-out number.
    """
    return ALL_NUMBER_WORDS_BY_VALUE.get(count_word.strip().lower())


def find_gate_count_drift(content: str) -> list[str]:
    """Return one issue per gate-count word that drifts from the named validators.

    Requires both count clauses to be present and in document order, since the
    validators are enumerated in the window between them: the "<count> more gate
    validators" phrase first, then the "<count> gated slices" total. When either
    clause is absent, or the total clause does not sit after the free-form clause,
    the content is not a judgeable enumeration, so no issue results. The free-form
    validators are the
    distinct backticked ``check_*`` tokens in that window, excluding the ``Args:``
    gate. When the "<count> more gate validators" spelled-out count disagrees with
    the number of validators named in the window, it is an issue; when the
    "<count> gated slices" total is not that count plus one (plus the ``Args:``
    gate), it is an issue. A count word that is not a known spelled-out number
    yields no issue.

    Args:
        content: The full rule-file text being written.

    Returns:
        Each drift issue message, capped at the issue budget.
    """
    prose_text = "\n".join(_lines_outside_code_fences(content))
    free_form_match = FREE_FORM_GATE_COUNT_PATTERN.search(prose_text)
    total_match = TOTAL_GATED_SLICE_COUNT_PATTERN.search(prose_text)
    if free_form_match is None or total_match is None:
        return []
    if total_match.start() <= free_form_match.end():
        return []
    enumeration_window = prose_text[free_form_match.end() : total_match.start()]
    all_named_validators = _named_free_form_validators(enumeration_window)
    named_count = len(all_named_validators)
    issues: list[str] = []
    stated_free_form = _count_word_value(free_form_match.group(1))
    if stated_free_form is not None and stated_free_form != named_count:
        issues.append(
            _format_issue(
                free_form_match.group(0), stated_free_form, all_named_validators, named_count
            )
        )
    stated_total = _count_word_value(total_match.group(1))
    if stated_total is not None and stated_total != named_count + 1:
        issues.append(
            _format_issue(total_match.group(0), stated_total, all_named_validators, named_count)
        )
    return issues[:MAX_GATE_COUNT_ISSUES]


def _format_issue(
    stated_phrase: str,
    stated_count: int,
    all_named_validators: list[str],
    named_count: int,
) -> str:
    """Build one drift-issue message for a stale count clause.

    Args:
        stated_phrase: The matched count clause text, such as ``four gated slices``.
        stated_count: The integer the clause's count word names.
        all_named_validators: The distinct free-form validators the prose names.
        named_count: The number of distinct free-form validators named.

    Returns:
        The formatted block-reason message for this drift.
    """
    formatted_validators = ", ".join(f"`{each_name}`" for each_name in all_named_validators)
    return GATE_COUNT_MESSAGE_TEMPLATE.format(
        rule_basename=TARGET_RULE_BASENAME,
        stated_phrase=stated_phrase,
        stated_count=stated_count,
        named_count=named_count,
        named_validators=formatted_validators,
        total_count=named_count + 1,
    )


def _read_existing_file_content(file_path: str) -> str | None:
    """Return the current on-disk content of *file_path*, or None when unreadable.

    Args:
        file_path: The path of the file the edit targets.

    Returns:
        The file's text, or None when the file is missing or cannot be decoded.
    """
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _post_edit_content(tool_name: str, tool_input: dict, file_path: str) -> str | None:
    """Return the content the write or edit would leave on disk, or None.

    For Write the content is the full new payload. For Edit and MultiEdit the
    existing file is read and the replacements applied, so a count clause on a line
    the edit does not touch still participates in the check. When the existing file
    cannot be read, None results so the hook stays silent rather than judging a
    partial fragment.

    Args:
        tool_name: The intercepted tool — ``Write``, ``Edit``, or ``MultiEdit``.
        tool_input: The tool's input payload.
        file_path: The destination path of the write or edit.

    Returns:
        The reconstructed post-edit content, or None when it cannot be built.
    """
    if tool_name == "Write":
        content = tool_input.get("content", "")
        return content if isinstance(content, str) and content else None
    existing_content = _read_existing_file_content(file_path)
    if existing_content is None:
        return None
    return apply_edits(existing_content, edits_for_tool(tool_name, tool_input))


def _build_block_payload(all_issues: list[str]) -> dict:
    """Build the PreToolUse deny payload carrying each gate-count drift issue.

    Args:
        all_issues: The drift-issue messages the check produced.

    Returns:
        The hook-result dictionary the harness reads to deny the write.
    """
    reason = " | ".join(all_issues)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": GATE_COUNT_ADDITIONAL_CONTEXT,
        },
        "systemMessage": GATE_COUNT_SYSTEM_MESSAGE,
        "suppressOutput": True,
    }


def _emit_hook_result(all_hook_data: dict, output_stream: TextIO) -> None:
    """Write the hook result JSON to the given output stream.

    Args:
        all_hook_data: The hook-result dictionary to serialize.
        output_stream: The stream the harness reads the decision from.
    """
    output_stream.write(json.dumps(all_hook_data) + "\n")
    output_stream.flush()


def main() -> None:
    """Read the PreToolUse payload from stdin and block a stale gate-count edit."""
    input_data = read_hook_input_dictionary_from_stdin()
    if input_data is None:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if not isinstance(tool_name, str) or tool_name not in ("Write", "Edit", "MultiEdit"):
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not is_target_rule_file(file_path):
        sys.exit(0)

    post_edit_content = _post_edit_content(tool_name, tool_input, file_path)
    if post_edit_content is None:
        sys.exit(0)

    gate_count_issues = find_gate_count_drift(post_edit_content)
    if not gate_count_issues:
        sys.exit(0)

    block_payload = _build_block_payload(gate_count_issues)
    log_hook_block(
        calling_hook_name="docstring_rule_gate_count_blocker.py",
        hook_event="PreToolUse",
        block_reason=block_payload["hookSpecificOutput"]["permissionDecisionReason"],
        tool_name=tool_name,
        offending_input_preview=file_path,
    )
    _emit_hook_result(block_payload, sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
