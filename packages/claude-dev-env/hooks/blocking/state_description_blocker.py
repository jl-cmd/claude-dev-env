#!/usr/bin/env python3
"""PreToolUse hook: blocks Write/Edit containing historical/comparative language in comments, Python docstrings, and .md files.

Enforces the "describe current state only" rule — no "instead of", "previously",
"now uses", or similar transitional framing. Comments, docstrings, and
documentation should describe what IS, not what WAS or what CHANGED. Inside a
docstring, a phrase wrapped in double quotes or backticks is a mention rather
than a use, so quoted spans are stripped before the scan.
"""

import ast
import json
import os
import sys
from pathlib import Path
from re import Pattern
from typing import TextIO

try:
    _hooks_dir = str(Path(__file__).resolve().parent.parent)
    if _hooks_dir not in sys.path:
        sys.path.insert(0, _hooks_dir)

    from blocking.code_rules_shared import is_ephemeral_path
    from hooks_constants.hook_block_logger import log_hook_block
    from hooks_constants.multi_edit_reconstruction import joined_new_strings
    from hooks_constants.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin
    from hooks_constants.state_description_blocker_constants import (
        ALL_BLOCK_COMMENT_EXTENSIONS,
        ALL_BLOCK_COMMENT_ONLY_EXTENSIONS,
        ALL_COMMENT_BEARING_EXTENSIONS,
        ALL_COMMENT_TRANSITION_PATTERNS,
        ALL_DEFINITION_HEADER_PREFIXES,
        ALL_HASH_AND_SLASH_EXTENSIONS,
        ALL_HASH_ONLY_EXTENSIONS,
        ALL_MARKDOWN_EXTENSIONS,
        BLOCK_COMMENT_CLOSE_MARKER,
        BLOCK_COMMENT_OPEN_MARKER,
        DOUBLE_QUOTE_BODY_GROUP,
        DOUBLE_QUOTED_SPAN_PATTERN,
        INLINE_CODE_PATTERN,
        PYTHON_EXTENSION,
        SINGLE_QUOTE_BODY_GROUP,
        TRIPLE_QUOTED_BLOCK_PATTERN,
    )
except ImportError as import_error:
    raise ImportError(
        "state_description_blocker: cannot import its sibling modules"
    ) from import_error


def _content_to_check(tool_name: str, all_tool_input: dict) -> str:
    """Return the text a Write, Edit, or MultiEdit payload introduces."""
    if tool_name == "MultiEdit":
        return joined_new_strings(all_tool_input)
    content_key = "content" if tool_name == "Write" else "new_string"
    raw_content = all_tool_input.get(content_key, "")
    return raw_content if isinstance(raw_content, str) else ""


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


def _consume_block_comment_open(
    each_line_number: int, stripped: str
) -> tuple[list[tuple[int, str]], str | None, bool]:
    """Extract the comment span a ``/*``-opening line carries.

    Returns the extracted entries, the leftover code text to keep scanning
    on this same line (``None`` when the whole line was consumed), and
    whether the comment is still open past this line.
    """
    slash_star_index = stripped.find(BLOCK_COMMENT_OPEN_MARKER)
    close_star_index = stripped.find(
        BLOCK_COMMENT_CLOSE_MARKER, slash_star_index + len(BLOCK_COMMENT_OPEN_MARKER)
    )
    if close_star_index < 0:
        return [(each_line_number, stripped[slash_star_index:])], None, True
    close_end = close_star_index + len(BLOCK_COMMENT_CLOSE_MARKER)
    entry = (each_line_number, stripped[slash_star_index:close_end])
    after_close = stripped[close_end:].lstrip()
    return [entry], (after_close or None), False


def _consume_block_comment_continuation(
    each_line_number: int, stripped: str
) -> tuple[list[tuple[int, str]], bool, bool]:
    """Extract the comment span a line inside an already-open block carries.

    Returns the extracted entries, whether the comment is still open past
    this line, and whether the caller should move to the next source line.
    """
    close_index = stripped.find(BLOCK_COMMENT_CLOSE_MARKER)
    if close_index < 0:
        return [(each_line_number, stripped)], True, True
    close_end = close_index + len(BLOCK_COMMENT_CLOSE_MARKER)
    return [(each_line_number, stripped[:close_end])], False, False


def _extract_comment_lines(text: str, extension: str = "") -> list[tuple[int, str]]:
    """Return each comment line as ``(source_line_number, comment_text)``.

    Covers Python (``#``), JS/TS/C/Rust/Go (``//``), and block comments, and
    tags every extracted line with the source line it came from so a
    matching pattern can be pinned to that line rather than searched for
    again.
    """
    all_comment_lines: list[tuple[int, str]] = []

    is_in_block_comment = False
    has_block_comments = extension in ALL_BLOCK_COMMENT_EXTENSIONS
    all_inline_markers = _get_inline_markers(extension)
    for each_line_number, each_line in enumerate(text.splitlines(), 1):
        stripped = each_line.strip()

        if has_block_comments:
            if any(
                stripped.startswith(each_marker)
                for each_marker in all_inline_markers
            ):
                all_comment_lines.append((each_line_number, stripped))
                continue
            if BLOCK_COMMENT_OPEN_MARKER in stripped and not is_in_block_comment:
                entries, leftover, is_in_block_comment = _consume_block_comment_open(
                    each_line_number, stripped
                )
                all_comment_lines.extend(entries)
                if leftover is None:
                    continue
                stripped = leftover
            if is_in_block_comment:
                entries, is_in_block_comment, should_continue = (
                    _consume_block_comment_continuation(each_line_number, stripped)
                )
                all_comment_lines.extend(entries)
                if should_continue:
                    continue

        if any(
            stripped.startswith(each_marker) for each_marker in all_inline_markers
        ):
            all_comment_lines.append((each_line_number, stripped))
            continue

        inline_index = _find_inline_comment_start(stripped, all_inline_markers)
        if inline_index is not None and inline_index > 0:
            all_comment_lines.append((each_line_number, stripped[inline_index:]))
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


def _extract_parsed_docstrings(tree: ast.Module) -> list[tuple[int, str]]:
    """Return each docstring as ``(start_line, docstring_text)``.

    Args:
        tree: The parsed module tree to walk.

    Returns:
        One entry per docstring found on the module and its class/function
        definitions, tagged with the source line the docstring's opening
        quotes start on.
    """
    all_found_docstrings: list[tuple[int, str]] = []
    for each_node in ast.walk(tree):
        if not isinstance(
            each_node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        maybe_docstring = ast.get_docstring(each_node, clean=False)
        if maybe_docstring:
            docstring_statement = each_node.body[0]
            all_found_docstrings.append((docstring_statement.lineno, maybe_docstring))
    return all_found_docstrings


def _is_docstring_position(leading_text: str) -> bool:
    """Decide whether the text before a triple-quoted block marks a docstring slot.

    A triple-quoted block counts as a docstring when it opens the fragment
    (only whitespace before it) or when the nearest preceding non-blank line
    is a def/class header ending in a colon. A block assigned to a name or
    sitting elsewhere in the fragment is data.
    """
    if not leading_text.strip():
        return True
    if leading_text.rpartition("\n")[2].strip():
        return False
    all_preceding_lines = [
        each_line for each_line in leading_text.splitlines() if each_line.strip()
    ]
    if not all_preceding_lines:
        return False
    last_preceding_line = all_preceding_lines[-1].strip()
    return last_preceding_line.startswith(
        ALL_DEFINITION_HEADER_PREFIXES
    ) and last_preceding_line.endswith(":")


def _extract_fragment_docstrings(text: str) -> list[tuple[int, str]]:
    """Return docstring-positioned triple-quoted blocks from an unparseable fragment.

    Args:
        text: The Python source fragment that failed to parse.

    Returns:
        One ``(start_line, body_text)`` pair per docstring-positioned
        triple-quoted block, tagged with the source line its opening quotes
        start on.
    """
    all_found_docstrings: list[tuple[int, str]] = []
    for each_match in TRIPLE_QUOTED_BLOCK_PATTERN.finditer(text):
        body = (
            each_match.group(DOUBLE_QUOTE_BODY_GROUP)
            if each_match.group(DOUBLE_QUOTE_BODY_GROUP) is not None
            else each_match.group(SINGLE_QUOTE_BODY_GROUP)
        )
        start_line = text.count("\n", 0, each_match.start()) + 1
        leading_text = text[: each_match.start()]
        if _is_docstring_position(leading_text):
            all_found_docstrings.append((start_line, body))
    return all_found_docstrings


def _docstring_scan_lines(text: str) -> list[tuple[int, str]]:
    """Return each docstring's prose as ``(source_line_number, line_text)`` pairs.

    Parses the source when valid, or falls back to the docstring-positioned
    triple-quoted blocks of a mid-edit fragment. Double-quoted and backticked
    spans inside each docstring are mentions rather than uses, so both are
    stripped before the docstring is split back into its own source lines.

    Args:
        text: The Python source or fragment under scan.

    Returns:
        One entry per physical line of docstring prose, numbered against the
        source file so a pattern match on that line carries the line the
        rule matched rather than an unrelated occurrence elsewhere in the
        file.
    """
    try:
        all_found_docstrings = _extract_parsed_docstrings(ast.parse(text))
    except (SyntaxError, ValueError):
        all_found_docstrings = _extract_fragment_docstrings(text)
    all_scan_lines: list[tuple[int, str]] = []
    for each_start_line, each_docstring in all_found_docstrings:
        prose = DOUBLE_QUOTED_SPAN_PATTERN.sub(
            "", INLINE_CODE_PATTERN.sub("", each_docstring)
        )
        for each_offset, each_prose_line in enumerate(prose.split("\n")):
            all_scan_lines.append((each_start_line + each_offset, each_prose_line))
    return all_scan_lines


def _markdown_scan_lines(text: str) -> list[tuple[int, str]]:
    """Return each Markdown source line as ``(line_number, scannable_text)``.

    A fenced code block's content is data rather than prose, so a line
    between a pair of ``` fence markers is skipped. An inline code span is a
    mention rather than a use, so it is blanked out of the line it appears
    on, the same way it is blanked from Python docstring prose.

    Args:
        text: The Markdown source to scan.

    Returns:
        One entry per source line outside a fenced code block, with its
        inline code spans removed.
    """
    all_scan_lines: list[tuple[int, str]] = []
    is_inside_fence = False
    for each_line_number, each_line in enumerate(text.splitlines(), 1):
        if each_line.strip().startswith("```"):
            is_inside_fence = not is_inside_fence
            continue
        if is_inside_fence:
            continue
        all_scan_lines.append(
            (each_line_number, INLINE_CODE_PATTERN.sub("", each_line))
        )
    return all_scan_lines


def _first_pattern_match(
    pattern: Pattern[str], all_scan_lines: list[tuple[int, str]]
) -> tuple[str, int] | None:
    """Return the first line a pattern matches, or None when it matches none."""
    for each_line_number, each_line_text in all_scan_lines:
        each_match = pattern.search(each_line_text)
        if each_match is not None:
            return (each_match.group(0).strip().lower(), each_line_number)
    return None


def _scan_lines_for_file(
    text: str, extension: str, file_path: str
) -> list[tuple[int, str]] | None:
    """Return the file's scannable lines, or ``None`` when its kind carries no prose.

    A ``.md`` file scans every source line outside a fenced code block. A
    code file scans its comment lines, and a Python file also scans its
    module, class, and function docstrings.
    """
    if is_markdown_file(file_path):
        return _markdown_scan_lines(text)
    if not is_comment_bearing_file(file_path):
        return None
    all_scan_lines = _extract_comment_lines(text, extension)
    if extension == PYTHON_EXTENSION:
        return all_scan_lines + _docstring_scan_lines(text)
    return all_scan_lines


def _matched_transition_patterns(
    all_scan_lines: list[tuple[int, str]],
) -> list[tuple[str, int]]:
    """Return each transition pattern the scan lines match, with its line."""
    all_detected: list[tuple[str, int]] = []
    for each_pattern in ALL_COMMENT_TRANSITION_PATTERNS:
        matched_entry = _first_pattern_match(each_pattern, all_scan_lines)
        if matched_entry is not None:
            all_detected.append(matched_entry)
    return all_detected


def find_violations_with_lines(text: str, file_path: str) -> list[tuple[str, int]]:
    """Return each violated pattern with the source line the rule matched.

    ::

        # config.py
        1  fixture_text = "the field was `previously` required"
        4  def read_field():
        5      \"\"\"Read the field.
        7      `The field was previously required.`
        8      \"\"\"
        flag: ("previously", 7) and ("was previously", 7)  -- one per pattern
        ok:   line 1 never reported  -- a plain string literal is fixture data, not prose

    Each match is paired with the line it matched on, not an earlier mention
    of the same words.

    Args:
        text: The file content to scan.
        file_path: The path that selects the scan strategy for the file.

    Returns:
        One ``(matched_phrase, source_line_number)`` pair per matched
        pattern, in pattern-declaration order, at most one match each.
    """
    extension = _get_file_extension(file_path)
    all_scan_lines = _scan_lines_for_file(text, extension, file_path)
    if all_scan_lines is None:
        return []
    return _matched_transition_patterns(all_scan_lines)


def find_violations(text: str, file_path: str) -> list[str]:
    """Return all violated patterns found in text for the given file.

    For .md files, scans the entire text. For code files, scans comment lines,
    and for Python files also scans module/class/function docstrings.
    Returns a list of matched pattern source strings.
    """
    return [
        each_phrase
        for each_phrase, _each_line_number in find_violations_with_lines(text, file_path)
    ]


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
    historical phrase is found, or None to allow. The check is unconditional.

    Args:
        payload_by_key: The PreToolUse payload with tool_name and tool_input.

    Returns:
        The permissionDecisionReason text when the write is denied, or None when
        the write is allowed.
    """
    raw_tool_name = payload_by_key.get("tool_name", "")
    tool_name = raw_tool_name if isinstance(raw_tool_name, str) else ""
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        return None

    raw_tool_input = payload_by_key.get("tool_input", {})
    tool_input = raw_tool_input if isinstance(raw_tool_input, dict) else {}

    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not file_path:
        return None
    if is_ephemeral_path(file_path, payload_by_key):
        return None
    if not (is_markdown_file(file_path) or is_comment_bearing_file(file_path)):
        return None

    content_to_check = _content_to_check(tool_name, tool_input)
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
                "Apply ~/.claude/rules/asd-ste100-language.md for user-facing language."
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
