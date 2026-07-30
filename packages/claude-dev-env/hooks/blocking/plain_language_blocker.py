#!/usr/bin/env python3
"""PreToolUse hook guarding AskUserQuestion prose and .md writes.

Two checks run. The word check reaches for the everyday word over the formal
one: `use` over `utilize`, `start` over `initiate`, `enough` over `sufficient`.
It reads both guarded surfaces -- AskUserQuestion (its question and option
prose) and Write/Edit/MultiEdit targeting a .md file -- with code fences,
inline code, blockquotes, URLs, and file paths stripped first, so exact
identifiers and paths are never flagged.

The lean-block check reads the AskUserQuestion surface alone. AskUserQuestion
renders as one plain text block, so the question text and each option
description stay short and unformatted: a fenced block, a heading, a table row,
a bullet or numbered list marker, a second paragraph, or prose past the
sentence and word caps all belong in chat text before the call. Structure is
read at block level on the raw text, with line endings folded to one spelling
first; an inline code span naming a path, a flag, or a command weighs one word
against the length caps.

See the plain-language and ask-user-question-required rules for the full
guidance this hook enforces.
"""

import json
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from blocking.code_rules_shared import is_ephemeral_path  # noqa: E402
from blocking.config.prose_style_enforcement_constants import (  # noqa: E402
    prose_style_enforcement_enabled_in_environment,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.plain_language_blocker_constants import (  # noqa: E402
    ALL_CHAT_DETAIL_MARKERS,
    ALL_LINE_ENDING_REPLACEMENTS,
    ALL_SOFTWARE_TERMS,
    ALL_TERM_PATTERNS,
    ALL_WRITE_EDIT_TOOL_NAMES,
    ASK_USER_QUESTION_TOOL_NAME,
    BLOCKQUOTE_LINE_PATTERN,
    COUNTABLE_WORD_PATTERN,
    DOT_CLAUDE_DIRECTORY_NAME,
    FENCED_CODE_BLOCK_PATTERN,
    FILE_PATH_PATTERN,
    INLINE_CODE_PATTERN,
    INLINE_CODE_PLACEHOLDER,
    INLINE_CODE_SPAN_PATTERN,
    LEAN_QUESTION_BLOCK_GUIDANCE,
    LEAN_QUESTION_BLOCK_PREFIX,
    LEAN_QUESTION_VIOLATION_SEPARATOR,
    MARKDOWN_EXTENSION,
    MAXIMUM_OPTION_DESCRIPTION_SENTENCE_COUNT,
    MAXIMUM_OPTION_DESCRIPTION_WORD_COUNT,
    MAXIMUM_QUESTION_SENTENCE_COUNT,
    MAXIMUM_QUESTION_WORD_COUNT,
    OPTION_DESCRIPTION_SURFACE_NAME,
    PROJECT_ALLOWLIST_FILENAME,
    PROJECT_ROOT_WALK_LIMIT,
    QUESTION_SURFACE_NAME,
    REPOSITORY_MARKER_NAME,
    SENTENCE_BOUNDARY_PATTERN,
    URL_PATTERN,
    USER_FACING_LEAN_QUESTION_NOTICE,
    USER_FACING_PLAIN_LANGUAGE_NOTICE,
)
from hooks_constants.prose_matcher_precision_constants import (  # noqa: E402
    ADVISORY_CONTEXT_SNIPPET_MAX_CHARS,
    MATCHER_ID_PLAIN_LANGUAGE_HEAVY_WORD,
    MAXIMUM_ADVISORY_EMITS_PER_CALL,
)
from observability.prose_matcher_advisory import emit_advisory_candidate  # noqa: E402


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


def find_banned_terms(
    text: str, all_allowlisted_terms: frozenset[str] = frozenset()
) -> list[tuple[str, str]]:
    """Return each (matched term, suggested replacement) found in the prose.

    Each term appears at most once, in first-seen order. Matching is
    case-insensitive and respects word boundaries; multi-word phrases match as
    whole units. Terms in the software-term allowlist and terms in the
    caller-supplied per-project allowlist are exempt and never flagged.

    Args:
        text: The prose to scan.
        all_allowlisted_terms: Lowercased project-vocabulary terms to exempt, on top
            of the built-in software-term allowlist.

    Returns:
        The (matched term, suggested replacement) pairs, in first-seen order.
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
        if normalized_term in all_allowlisted_terms:
            continue
        seen_terms.add(normalized_term)
        all_matches.append((normalized_term, each_replacement))
    return all_matches


def _allowlist_start_directory(
    tool_name: str, tool_input: dict, payload_by_key: dict[str, object]
) -> Path | None:
    """Return the directory to begin the project-allowlist search from.

    A Write/Edit/MultiEdit on a file starts at that file's parent directory; an
    AskUserQuestion (or a write with no path) starts at the session working
    directory the payload carries.

    Args:
        tool_name: The intercepted tool's name.
        tool_input: The intercepted tool's input payload.
        payload_by_key: The full PreToolUse payload carrying ``cwd``.

    Returns:
        The starting directory, or None when neither a file path nor a working
        directory is available.
    """
    if tool_name in ALL_WRITE_EDIT_TOOL_NAMES:
        file_path = tool_input.get("file_path", "")
        if isinstance(file_path, str) and file_path:
            return Path(file_path).parent
    working_directory = payload_by_key.get("cwd", "")
    if isinstance(working_directory, str) and working_directory:
        return Path(working_directory)
    return None


def _find_project_allowlist_file(start_directory: Path) -> Path | None:
    """Walk ancestors from start_directory for a repo-scoped project allowlist file.

    ::

        parent/                      .claude/allow  -> ignored (above the repo root)
        parent/repo/     <- .git     .claude/allow  -> applied (repo root reached)
        parent/repo/pkg/             .claude/allow  -> applied (inside the repo tree)

    The allowlist must live inside the repository so it is reviewed like any
    other committed config. The walk checks each directory for the allowlist,
    then for the ``.git`` repository marker; it accepts an allowlist at or below
    the first ``.git``-bearing directory, stops at that repository root, and
    never ascends past it. When no ``.git`` marker appears within the walk
    limit, the directory is not inside a repository and no allowlist applies, so
    a global file such as ``~/.claude/plain-language-allow.json`` never loosens
    the gate for every project.

    Args:
        start_directory: The directory to begin the upward walk from.

    Returns:
        The nearest in-repository ``.claude/plain-language-allow.json`` at or
        below the repository root, or None when the walk finds no repository
        root or no allowlist within it.
    """
    nearest_allowlist: Path | None = None
    current_directory = start_directory
    for _ in range(PROJECT_ROOT_WALK_LIMIT):
        candidate = current_directory / DOT_CLAUDE_DIRECTORY_NAME / PROJECT_ALLOWLIST_FILENAME
        if nearest_allowlist is None and candidate.is_file():
            nearest_allowlist = candidate
        if (current_directory / REPOSITORY_MARKER_NAME).exists():
            return nearest_allowlist
        if current_directory.parent == current_directory:
            break
        current_directory = current_directory.parent
    return None


def _parse_project_allowlist_file(allowlist_path: Path) -> frozenset[str]:
    """Read a JSON array of allowlist words into a lowercased term set.

    Malformed JSON, an unreadable file, or any non-list shape yields an empty
    set, so the hook falls back to the standard check rather than crashing.

    Args:
        allowlist_path: The allowlist file to read.

    Returns:
        The lowercased string entries, or an empty set on any read/parse fault.
    """
    try:
        raw_text = allowlist_path.read_text(encoding="utf-8")
        parsed_entries = json.loads(raw_text)
    except (OSError, ValueError):
        return frozenset()
    if not isinstance(parsed_entries, list):
        return frozenset()
    return frozenset(
        each_entry.lower() for each_entry in parsed_entries if isinstance(each_entry, str)
    )


def _load_project_allowlist(
    tool_name: str, tool_input: dict, payload_by_key: dict[str, object]
) -> frozenset[str]:
    """Load the per-project domain-vocabulary allowlist for the write's project.

    Args:
        tool_name: The intercepted tool's name.
        tool_input: The intercepted tool's input payload.
        payload_by_key: The full PreToolUse payload carrying ``cwd``.

    Returns:
        The lowercased allowlist terms for the project the write targets, or an
        empty set when no allowlist applies.
    """
    start_directory = _allowlist_start_directory(tool_name, tool_input, payload_by_key)
    if start_directory is None:
        return frozenset()
    allowlist_path = _find_project_allowlist_file(start_directory)
    if allowlist_path is None:
        return frozenset()
    return _parse_project_allowlist_file(allowlist_path)


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


def _normalize_line_endings(prose_text: str) -> str:
    """Return the prose with every line ending spelled as a bare line feed.

    ::

        in:  "Which gate?\\r\\n\\r\\nThe write gate reads it."
        out: "Which gate?\\n\\nThe write gate reads it."

    The structure markers read line boundaries, so a payload carrying carriage
    returns is normalized once here rather than at each pattern.

    Args:
        prose_text: One question text or one option description.

    Returns:
        The prose with carriage returns folded into line feeds.
    """
    normalized_text = prose_text
    for each_line_ending, each_replacement in ALL_LINE_ENDING_REPLACEMENTS:
        normalized_text = normalized_text.replace(each_line_ending, each_replacement)
    return normalized_text


def _mask_inline_code(prose_text: str) -> str:
    """Return the prose with each inline code span collapsed to a single word.

    ::

        in:  "Does `git diff --cached` list it?"
        out: "Does code list it?"

    A span names a path, a flag, or a command the reader needs verbatim, so it
    weighs one word against the length caps. Only the length counts read the
    masked prose: the structure markers read the raw text, so a one-line closed
    fence still reads as a fence rather than as a span.

    Args:
        prose_text: One question text or one option description.

    Returns:
        The prose with every single-line inline code span replaced.
    """
    return INLINE_CODE_SPAN_PATTERN.sub(INLINE_CODE_PLACEHOLDER, prose_text)


def _count_prose_sentences(prose_text: str) -> int:
    """Return how many sentences one piece of question-block prose carries.

    ::

        in:  "Which gate runs first? Both read the same lines."
        out: 2

    A sentence closes on `.`, `!`, or `?` followed by a capitalized word or the
    end of the text, so an abbreviation mid-sentence closes nothing.

    Args:
        prose_text: One question text or one option description.

    Returns:
        The count of sentence closings the prose carries.
    """
    return len(SENTENCE_BOUNDARY_PATTERN.findall(prose_text))


def _count_prose_words(prose_text: str) -> int:
    """Return how many reader-visible words one piece of prose carries.

    Args:
        prose_text: One question text or one option description.

    Returns:
        The count of whitespace-separated tokens carrying a letter or digit.
    """
    return len(COUNTABLE_WORD_PATTERN.findall(prose_text))


def _find_chat_detail_markers(prose_text: str) -> list[str]:
    """Return the name of each chat-detail marker the prose carries.

    ::

        ok:   "Which gate should run first?"        -> []
        flag: "Which gate?\\n- write\\n- commit"      -> ["a bullet or numbered
              list marker"]

    Args:
        prose_text: One question text or one option description.

    Returns:
        One marker name per marker found, in the order the markers are tried.
    """
    return [
        each_marker_name
        for each_pattern, each_marker_name in ALL_CHAT_DETAIL_MARKERS
        if each_pattern.search(prose_text)
    ]


def _find_lean_block_violations(
    prose_text: str,
    surface_name: str,
    maximum_sentence_count: int,
    maximum_word_count: int,
) -> list[str]:
    """Return every lean-block rule one piece of question-block prose breaks.

    Args:
        prose_text: One question text or one option description.
        surface_name: How the violation text names this piece of prose.
        maximum_sentence_count: The sentence cap this piece answers to.
        maximum_word_count: The word cap this piece answers to.

    Returns:
        One violation text per broken rule, empty when the prose is lean.

    The structure markers read the line-ending-normalized prose; the sentence
    and word counts read that prose with its inline code spans masked.
    """
    normalized_text = _normalize_line_endings(prose_text)
    masked_text = _mask_inline_code(normalized_text)
    all_violations = [
        f"{surface_name} carries {each_marker_name}"
        for each_marker_name in _find_chat_detail_markers(normalized_text)
    ]
    sentence_count = _count_prose_sentences(masked_text)
    if sentence_count > maximum_sentence_count:
        all_violations.append(
            f"{surface_name} runs {sentence_count} sentences, over the "
            f"{maximum_sentence_count}-sentence cap"
        )
    word_count = _count_prose_words(masked_text)
    if word_count > maximum_word_count:
        all_violations.append(
            f"{surface_name} runs {word_count} words, over the "
            f"{maximum_word_count}-word cap"
        )
    return all_violations


def _violations_for_one_question(question_by_key: dict) -> list[str]:
    """Return the lean-block violations one question entry carries.

    Args:
        question_by_key: One entry of the AskUserQuestion questions list.

    Returns:
        One violation text per broken rule across the question text and every
        option description the entry carries.
    """
    all_violations: list[str] = []
    question_text = question_by_key.get("question", "")
    if isinstance(question_text, str):
        all_violations.extend(
            _find_lean_block_violations(
                question_text,
                QUESTION_SURFACE_NAME,
                MAXIMUM_QUESTION_SENTENCE_COUNT,
                MAXIMUM_QUESTION_WORD_COUNT,
            )
        )
    all_options = question_by_key.get("options", [])
    if not isinstance(all_options, list):
        return all_violations
    for each_option in all_options:
        if not isinstance(each_option, dict):
            continue
        option_description = each_option.get("description", "")
        if not isinstance(option_description, str):
            continue
        all_violations.extend(
            _find_lean_block_violations(
                option_description,
                OPTION_DESCRIPTION_SURFACE_NAME,
                MAXIMUM_OPTION_DESCRIPTION_SENTENCE_COUNT,
                MAXIMUM_OPTION_DESCRIPTION_WORD_COUNT,
            )
        )
    return all_violations


def find_question_block_violations(tool_input: dict) -> list[str]:
    """Return every lean-block violation an AskUserQuestion payload carries.

    ::

        ok:   "Which gate should run first?" + "Runs on every write." -> []
        flag: a question with a three-bullet plan under it
              -> ["the question carries a bullet or numbered list marker"]

    Each violation text appears once, so two options breaking the same cap read
    as one line.

    Args:
        tool_input: The AskUserQuestion tool input carrying the questions list.

    Returns:
        One violation text per broken rule, in first-seen order, empty when the
        whole question block is lean.
    """
    all_questions = tool_input.get("questions", [])
    if not isinstance(all_questions, list):
        return []
    all_violations: list[str] = []
    for each_question in all_questions:
        if isinstance(each_question, dict):
            all_violations.extend(_violations_for_one_question(each_question))
    return list(dict.fromkeys(all_violations))


def build_lean_block_reason(all_violations: list[str]) -> str:
    """Return a deny reason naming each chat detail and where the detail belongs.

    Args:
        all_violations: The violation texts the question block earned.

    Returns:
        The full deny reason the model rewrites its question block against.
    """
    violation_list = LEAN_QUESTION_VIOLATION_SEPARATOR.join(all_violations)
    return f"{LEAN_QUESTION_BLOCK_PREFIX}{violation_list}. {LEAN_QUESTION_BLOCK_GUIDANCE}"


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


def _notice_for_deny_reason(deny_reason: str) -> str:
    """Return the short notice matching the check that produced a deny reason.

    Args:
        deny_reason: The permissionDecisionReason text for the denial.

    Returns:
        The lean-block notice for a question-block denial, the word-swap notice
        otherwise.
    """
    if deny_reason.startswith(LEAN_QUESTION_BLOCK_PREFIX):
        return USER_FACING_LEAN_QUESTION_NOTICE
    return USER_FACING_PLAIN_LANGUAGE_NOTICE


def build_deny_payload(deny_reason: str) -> dict[str, object]:
    """Build the full deny payload the hook writes for a deny-reason string.

    The payload carries the core permission decision plus the user-facing notice
    and output suppression, so a caller routing this hook through a dispatcher
    reproduces the same deny shape the standalone hook writes.

    Args:
        deny_reason: The permissionDecisionReason text for the denial.

    Returns:
        The deny payload dictionary the hook serializes to stdout.
    """
    log_hook_block(
        calling_hook_name="plain_language_blocker.py",
        hook_event="PreToolUse",
        block_reason=deny_reason,
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason,
        },
        "systemMessage": _notice_for_deny_reason(deny_reason),
        "suppressOutput": True,
    }


def _emit_deny(deny_reason: str, output_stream: TextIO) -> None:
    output_stream.write(json.dumps(build_deny_payload(deny_reason)))
    output_stream.flush()


def _emit_plain_language_advisory_candidates(
    surface: str,
    all_matches: list[tuple[str, str]],
    prose_text: str,
) -> None:
    """Record privacy-safe advisory hits when enforcement is off (fail open)."""
    try:
        for each_match in all_matches[:MAXIMUM_ADVISORY_EMITS_PER_CALL]:
            each_term = each_match[0]
            emit_advisory_candidate(
                MATCHER_ID_PLAIN_LANGUAGE_HEAVY_WORD,
                surface,
                f"{each_term}:{prose_text[:ADVISORY_CONTEXT_SNIPPET_MAX_CHARS]}",
            )
    except (ImportError, OSError, TypeError, ValueError):
        return


def evaluate(payload_by_key: dict[str, object]) -> str | None:
    """Decide whether a payload carries a question block or heavy words to block.

    An AskUserQuestion payload meets the lean-block check first, so a question
    text or an option description carrying chat detail returns a LEAN_QUESTION
    deny reason. When prose-style enforcement is on, the word scan returns a
    PLAIN_LANGUAGE deny reason for heavy words. When enforcement is off, heavy
    word hits are recorded as privacy-safe advisory candidates only.

    Args:
        payload_by_key: The PreToolUse payload with tool_name and tool_input.

    Returns:
        The permissionDecisionReason text when the payload is denied, or None
        when it is allowed.
    """
    raw_tool_name = payload_by_key.get("tool_name", "")
    raw_tool_input = payload_by_key.get("tool_input", {})
    if not isinstance(raw_tool_name, str) or not isinstance(raw_tool_input, dict):
        return None

    if raw_tool_name in ALL_WRITE_EDIT_TOOL_NAMES:
        target_file_path = raw_tool_input.get("file_path", "")
        if isinstance(target_file_path, str) and is_ephemeral_path(
            target_file_path, payload_by_key
        ):
            return None

    if raw_tool_name == ASK_USER_QUESTION_TOOL_NAME:
        all_block_violations = find_question_block_violations(raw_tool_input)
        if all_block_violations:
            return build_lean_block_reason(all_block_violations)

    prose_text = _collect_prose_for_tool(raw_tool_name, raw_tool_input)
    if not prose_text:
        return None

    all_allowlisted_terms = _load_project_allowlist(
        raw_tool_name, raw_tool_input, payload_by_key
    )
    all_matches = find_banned_terms(prose_text, all_allowlisted_terms)
    if not all_matches:
        return None

    if not prose_style_enforcement_enabled_in_environment():
        _emit_plain_language_advisory_candidates(raw_tool_name, all_matches, prose_text)
        return None

    return build_block_reason(all_matches)


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if not isinstance(input_data, dict):
        sys.exit(0)

    deny_reason = evaluate(input_data)
    if deny_reason is None:
        sys.exit(0)

    _emit_deny(deny_reason, sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
