#!/usr/bin/env python3
"""
Stop hook that blocks a beat-sheet reply breaking its single-line-beat shape.

The `beat-sheet` skill asks a reply it formats to read as single-line beats:
each line under 12 words, a blank line between every beat, at most 10 beats,
and plain everyday words in place of jargon. This hook only runs its checks
when the live transcript shows the `beat-sheet` Skill was invoked earlier in
the current turn — an ordinary reply that never engaged the skill is left
alone. When beat-sheet was invoked, the hook reads the final assistant
message, strips code fences and quotes, then checks the per-line word cap,
the beat-count cap, blank-line separation between beats, and the shared
plain-language wordlist. A reply opening with "Long form:" opts out, matching
the same escape the `eli11_reply_enforcer` Stop hook honors.
"""

import json
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from eli11_reply_enforcer import opens_with_long_form_escape  # noqa: E402
from plain_language_blocker import (  # noqa: E402
    _find_project_allowlist_file,
    _parse_project_allowlist_file,
    find_banned_terms,
    strip_non_prose_regions,
)

from hooks_constants.beat_sheet_reply_enforcer_constants import (  # noqa: E402
    ALL_BEAT_SHEET_SKILL_SEARCH_PATHS,
    BEAT_MAXIMUM_LINE_COUNT,
    BEAT_MAXIMUM_WORDS_PER_LINE,
    BEAT_SHEET_SKILL_TARGET_NAME,
    SKILL_TOOL_NAME,
    TRANSCRIPT_CONTENT_KEY,
    TRANSCRIPT_MESSAGE_KEY,
    TRANSCRIPT_PROMPT_ID_KEY,
    TRANSCRIPT_TOOL_INPUT_KEY,
    TRANSCRIPT_TOOL_INPUT_SKILL_KEY,
    TRANSCRIPT_TOOL_NAME_KEY,
    TRANSCRIPT_TOOL_USE_CONTENT_TYPE,
    USER_FACING_BEAT_SHEET_NOTICE,
    VIOLATION_SEPARATOR,
)
from hooks_constants.eli11_reply_enforcer_constants import (  # noqa: E402
    COUNTABLE_WORD_PATTERN,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.text_stripping import strip_code_and_quotes  # noqa: E402


def read_transcript_entries(transcript_path: str) -> list[dict]:
    """Return each parsed JSONL entry from the live session transcript.

    Args:
        transcript_path: The live session's transcript path from the payload.

    Returns:
        One dict per parseable line, in file order; empty when the path is
        blank, unreadable, or holds no parseable JSON line.
    """
    if not transcript_path:
        return []
    try:
        transcript_lines = (
            Path(transcript_path).read_text(encoding="utf-8", errors="replace").splitlines()
        )
    except OSError:
        return []
    all_entries: list[dict] = []
    for each_line in transcript_lines:
        if not each_line.strip():
            continue
        try:
            parsed_entry = json.loads(each_line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed_entry, dict):
            all_entries.append(parsed_entry)
    return all_entries


def _content_blocks(transcript_entry: dict) -> list[dict]:
    """Return the message content blocks of one transcript entry, if any."""
    message_record = transcript_entry.get(TRANSCRIPT_MESSAGE_KEY)
    if not isinstance(message_record, dict):
        return []
    content_blocks = message_record.get(TRANSCRIPT_CONTENT_KEY)
    if not isinstance(content_blocks, list):
        return []
    return [each_block for each_block in content_blocks if isinstance(each_block, dict)]


def current_turn_entries(all_entries: list[dict]) -> list[dict]:
    """Return the transcript entries belonging to the current turn.

    ::

        ok:   [.. promptId=A .., promptId=B, .. promptId=B ..] -> the promptId=B tail
        flag: every entry carries the same promptId (or none)  -> the whole list

    Only `user`-role entries carry a `promptId`; every intermediate
    assistant/tool-result/attachment entry the harness writes for one human
    turn carries none, including a Skill invocation's own injected reply
    text. A turn boundary is the most recent entry whose `promptId` differs
    from the current turn's id, walking from the end of the file.

    Args:
        all_entries: Every parsed transcript entry, in file order.

    Returns:
        The entries from the current turn's earliest `promptId` entry
        onward; the whole list when every entry shares one turn (or none
        carries a `promptId` at all).
    """
    current_turn_prompt_id: str | None = None
    boundary_index = 0
    for each_index in range(len(all_entries) - 1, -1, -1):
        prompt_id = all_entries[each_index].get(TRANSCRIPT_PROMPT_ID_KEY)
        if prompt_id is None:
            continue
        if current_turn_prompt_id is None:
            current_turn_prompt_id = prompt_id
            boundary_index = each_index
        elif prompt_id != current_turn_prompt_id:
            break
        else:
            boundary_index = each_index
    return all_entries[boundary_index:]


def _tool_use_blocks(transcript_entry: dict) -> list[dict]:
    """Return the tool_use content blocks of one transcript entry, if any."""
    return [
        each_block
        for each_block in _content_blocks(transcript_entry)
        if each_block.get("type") == TRANSCRIPT_TOOL_USE_CONTENT_TYPE
    ]


def invokes_beat_sheet_skill(transcript_entry: dict) -> bool:
    """Return True when an entry carries a `Skill` call targeting beat-sheet.

    Args:
        transcript_entry: One parsed JSONL transcript entry.

    Returns:
        True when any tool_use block in the entry names the `Skill` tool with
        `beat-sheet` as its target.
    """
    for each_block in _tool_use_blocks(transcript_entry):
        if each_block.get(TRANSCRIPT_TOOL_NAME_KEY) != SKILL_TOOL_NAME:
            continue
        tool_input = each_block.get(TRANSCRIPT_TOOL_INPUT_KEY)
        if not isinstance(tool_input, dict):
            continue
        if tool_input.get(TRANSCRIPT_TOOL_INPUT_SKILL_KEY) == BEAT_SHEET_SKILL_TARGET_NAME:
            return True
    return False


def was_beat_sheet_invoked_this_turn(transcript_path: str) -> bool:
    """Return True when beat-sheet ran earlier in the current turn.

    Args:
        transcript_path: The live session's transcript path from the payload.

    Returns:
        True when a `Skill` call targeting `beat-sheet` appears in the
        current turn's entries; False on any read fault or when it does not.
    """
    all_entries = read_transcript_entries(transcript_path)
    if not all_entries:
        return False
    return any(
        invokes_beat_sheet_skill(each_entry) for each_entry in current_turn_entries(all_entries)
    )


def resolve_beat_sheet_skill_path() -> str | None:
    """Return the first existing beat-sheet `SKILL.md` search-path candidate."""
    for each_candidate_path in ALL_BEAT_SHEET_SKILL_SEARCH_PATHS:
        if Path(each_candidate_path).exists():
            return each_candidate_path
    return None


def _extract_beat_lines(assistant_message: str) -> list[str]:
    """Return the reply's beat lines, code fences and quotes stripped.

    Args:
        assistant_message: The raw final assistant message.

    Returns:
        Every line of the stripped message, blank lines included, in order.
    """
    return strip_code_and_quotes(assistant_message).splitlines()


def _count_line_words(prose_line: str) -> int:
    """Return the countable word count of one beat line."""
    return len(COUNTABLE_WORD_PATTERN.findall(prose_line))


def describe_overpacked_beat_violation(line_number: int, word_count: int) -> str:
    """Return the violation text naming the offending beat line and its count."""
    return (
        f"line {line_number} carries {word_count} words, over the "
        f"{BEAT_MAXIMUM_WORDS_PER_LINE}-word beat cap"
    )


def describe_beat_count_violation(beat_count: int) -> str:
    """Return the violation text naming the beat count and the cap."""
    return f"{beat_count} beats, over the {BEAT_MAXIMUM_LINE_COUNT}-beat cap"


def describe_missing_blank_line_violation(line_number: int) -> str:
    """Return the violation text naming a beat with no blank line before it."""
    return f"line {line_number} has no blank line before it, breaking the one-beat-per-line shape"


def find_beat_shape_violations(assistant_message: str) -> list[str]:
    """Return every beat-shape violation the final assistant message carries.

    ::

        ok:   "Ship the fix.\\n\\nTests pass." -> []
        flag: "Ship the fix.\\nTests pass."    -> ["line 2 has no blank line..."]

    Args:
        assistant_message: The raw final assistant message.

    Returns:
        One violation text per broken rule, empty when the reply is in shape.
    """
    all_lines = _extract_beat_lines(assistant_message)
    all_violations: list[str] = []
    beat_count = 0
    previous_line_blank = True
    for each_index, each_line in enumerate(all_lines):
        if not each_line.strip():
            previous_line_blank = True
            continue
        beat_count += 1
        if not previous_line_blank:
            all_violations.append(describe_missing_blank_line_violation(each_index + 1))
        line_word_count = _count_line_words(each_line)
        if line_word_count > BEAT_MAXIMUM_WORDS_PER_LINE:
            all_violations.append(
                describe_overpacked_beat_violation(each_index + 1, line_word_count)
            )
        previous_line_blank = False
    if beat_count > BEAT_MAXIMUM_LINE_COUNT:
        all_violations.append(describe_beat_count_violation(beat_count))
    return all_violations


def find_jargon_violations(assistant_message: str, cwd: str) -> list[str]:
    """Return one violation text per heavy word the shared wordlist flags.

    Args:
        assistant_message: The raw final assistant message.
        cwd: The live session's working directory from the payload.

    Returns:
        One `"word" -> replacement` violation text per flagged term, in
        first-seen order; empty when the reply carries none.
    """
    prose_text = strip_non_prose_regions(assistant_message)
    allowlist_path = _find_project_allowlist_file(Path(cwd)) if cwd else None
    all_allowlisted_terms = (
        _parse_project_allowlist_file(allowlist_path) if allowlist_path else frozenset()
    )
    all_matches = find_banned_terms(prose_text, all_allowlisted_terms)
    return [f'"{matched_term}" -> "{replacement}"' for matched_term, replacement in all_matches]


def build_block_reason(all_violations: list[str], skill_path: str | None) -> str:
    """Return the corrective message naming each violation and the skill path.

    Args:
        all_violations: The violation texts the reply earned.
        skill_path: The resolved beat-sheet `SKILL.md` path, or None when no
            search-path candidate exists on disk.

    Returns:
        The full block reason the model rewrites its reply against.
    """
    formatted_violation_list = VIOLATION_SEPARATOR.join(all_violations)
    if skill_path is not None:
        skill_reference = f"under the beat-sheet shape defined in:\n\n{skill_path}"
    else:
        skill_reference = (
            "under the beat-sheet shape (single-line beats, a blank line between "
            "each one, under 12 words per beat, at most 10 beats, plain everyday "
            "words in place of jargon; no beat-sheet SKILL.md found on disk)"
        )
    return (
        f"BEAT-SHEET REPLY SHAPE: Your reply breaks the beat-sheet shape "
        f"({formatted_violation_list}).\n\n"
        f"Rewrite it {skill_reference}\n\n"
        f'When the user asked for a full report, start the reply with "Long '
        f'form:" to opt out of this check.\n\n'
        f"You MUST re-output the complete, revised response with the corrections "
        f"applied."
    )


def main() -> None:
    """Read the Stop payload and block a beat-sheet reply that breaks shape."""
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if hook_input.get("stop_hook_active", False):
        sys.exit(0)

    assistant_message = hook_input.get("last_assistant_message", "")
    if not assistant_message:
        sys.exit(0)

    if opens_with_long_form_escape(assistant_message):
        sys.exit(0)

    transcript_path = hook_input.get("transcript_path", "")
    if not was_beat_sheet_invoked_this_turn(transcript_path):
        sys.exit(0)

    all_violations = find_beat_shape_violations(assistant_message)
    all_violations.extend(find_jargon_violations(assistant_message, hook_input.get("cwd", "")))

    if not all_violations:
        sys.exit(0)

    block_reason = build_block_reason(all_violations, resolve_beat_sheet_skill_path())
    block_response = {
        "decision": "block",
        "reason": block_reason,
        "systemMessage": USER_FACING_BEAT_SHEET_NOTICE,
        "suppressOutput": True,
    }
    log_hook_block(
        calling_hook_name="beat_sheet_reply_enforcer.py",
        hook_event="Stop",
        block_reason=block_reason,
    )
    print(json.dumps(block_response))
    sys.exit(0)


if __name__ == "__main__":
    main()
