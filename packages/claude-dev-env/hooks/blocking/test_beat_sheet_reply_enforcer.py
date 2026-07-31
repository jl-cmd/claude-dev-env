"""Tests for beat_sheet_reply_enforcer hook response shape and detection."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "beat_sheet_reply_enforcer.py")
_HOOKS_DIR = os.path.dirname(HOOK_SCRIPT_PATH)
_HOOKS_ROOT = os.path.join(_HOOKS_DIR, "..")
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)
if _HOOKS_ROOT not in sys.path:
    sys.path.insert(0, _HOOKS_ROOT)
import beat_sheet_reply_enforcer
import eli11_reply_enforcer
import plain_language_blocker
from hooks_constants.beat_sheet_reply_enforcer_constants import (
    BEAT_MAXIMUM_LINE_COUNT,
    BEAT_MAXIMUM_WORDS_PER_LINE,
)

EARLIER_PROMPT_ID = "11111111-1111-1111-1111-111111111111"
CURRENT_PROMPT_ID = "22222222-2222-2222-2222-222222222222"

GOOD_BEAT_REPLY = (
    "**Ship the fix now.**\n"
    "\n"
    "The build broke on a missing import.\n"
    "\n"
    "Added the import and reran the suite.\n"
    "\n"
    "Every test passes on the new build.\n"
)

OVERPACKED_LINE_REPLY = (
    "**Title line.**\n"
    "\n"
    + " ".join(f"word{each_index}" for each_index in range(BEAT_MAXIMUM_WORDS_PER_LINE + 5))
    + "\n"
)

MISSING_BLANK_LINE_REPLY = "Ship the fix today.\nTests pass now.\n"

TOO_MANY_BEATS_REPLY = "\n\n".join(
    f"Beat number {each_index} lands here." for each_index in range(BEAT_MAXIMUM_LINE_COUNT + 2)
)

JARGON_REPLY = "**Update.**\n\nWe need to utilize the new config to leverage the change.\n"


def user_entry(prompt_id: str, text: str = "hello") -> dict:
    """Return a synthetic `user`-role transcript entry carrying a promptId."""
    return {
        "type": "user",
        "promptId": prompt_id,
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
    }


def beat_sheet_invocation_entry() -> dict:
    """Return a synthetic assistant entry invoking the `beat-sheet` Skill.

    Mirrors the real record shape confirmed from a live session transcript:
    an `assistant` entry whose `message.content` holds one `tool_use` block
    naming the `Skill` tool with `{"skill": "beat-sheet"}` as its input, and
    no `promptId` of its own (only `user`-role entries carry one).
    """
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "name": "Skill",
                    "input": {"skill": "beat-sheet"},
                }
            ],
        },
    }


def assistant_text_entry(text: str = "some other tool result") -> dict:
    """Return a synthetic assistant entry carrying plain text, no tool_use."""
    return {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }


def write_transcript(entries: list[dict]) -> str:
    """Write a synthetic JSONL transcript and return its path."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as transcript_file:
        for each_entry in entries:
            transcript_file.write(json.dumps(each_entry) + "\n")
        return transcript_file.name


def run_hook(
    assistant_message: str, transcript_path: str = "", cwd: str = ""
) -> subprocess.CompletedProcess:
    hook_input_payload = json.dumps(
        {
            "last_assistant_message": assistant_message,
            "transcript_path": transcript_path,
            "cwd": cwd,
        }
    )
    return subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=hook_input_payload,
        capture_output=True,
        text=True,
        check=False,
    )


def test_stop_hook_active_short_circuits() -> None:
    hook_input_payload = json.dumps(
        {"stop_hook_active": True, "last_assistant_message": OVERPACKED_LINE_REPLY}
    )
    completed_run = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=hook_input_payload,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed_run.stdout.strip() == ""


def test_empty_assistant_message_short_circuits() -> None:
    completed_run = run_hook("")
    assert completed_run.stdout.strip() == ""


def test_long_form_escape_skips_the_check() -> None:
    escaped_reply = "Long form: " + OVERPACKED_LINE_REPLY
    transcript_path = write_transcript(
        [user_entry(CURRENT_PROMPT_ID), beat_sheet_invocation_entry()]
    )
    completed_run = run_hook(escaped_reply, transcript_path)
    assert completed_run.stdout.strip() == ""


def test_silent_when_beat_sheet_was_not_invoked_this_turn() -> None:
    transcript_path = write_transcript([user_entry(CURRENT_PROMPT_ID)])
    completed_run = run_hook(OVERPACKED_LINE_REPLY, transcript_path)
    assert completed_run.stdout.strip() == ""


def test_silent_when_beat_sheet_was_invoked_only_in_an_earlier_turn() -> None:
    """A beat-sheet run in a prior turn must not leak into a later Stop check."""
    transcript_path = write_transcript(
        [
            user_entry(EARLIER_PROMPT_ID),
            beat_sheet_invocation_entry(),
            assistant_text_entry(),
            user_entry(CURRENT_PROMPT_ID),
            assistant_text_entry(),
        ]
    )
    completed_run = run_hook(OVERPACKED_LINE_REPLY, transcript_path)
    assert completed_run.stdout.strip() == ""


def test_blocks_overpacked_beat_line_when_invoked_this_turn() -> None:
    transcript_path = write_transcript(
        [user_entry(CURRENT_PROMPT_ID), beat_sheet_invocation_entry()]
    )
    completed_run = run_hook(OVERPACKED_LINE_REPLY, transcript_path)
    parsed_response = json.loads(completed_run.stdout)
    assert parsed_response["decision"] == "block"
    assert "over the" in parsed_response["reason"]
    assert f"{BEAT_MAXIMUM_WORDS_PER_LINE}-word beat cap" in parsed_response["reason"]


def test_blocks_missing_blank_line_when_invoked_this_turn() -> None:
    transcript_path = write_transcript(
        [user_entry(CURRENT_PROMPT_ID), beat_sheet_invocation_entry()]
    )
    completed_run = run_hook(MISSING_BLANK_LINE_REPLY, transcript_path)
    parsed_response = json.loads(completed_run.stdout)
    assert parsed_response["decision"] == "block"
    assert "no blank line before it" in parsed_response["reason"]


def test_blocks_too_many_beats_when_invoked_this_turn() -> None:
    transcript_path = write_transcript(
        [user_entry(CURRENT_PROMPT_ID), beat_sheet_invocation_entry()]
    )
    completed_run = run_hook(TOO_MANY_BEATS_REPLY, transcript_path)
    parsed_response = json.loads(completed_run.stdout)
    assert parsed_response["decision"] == "block"
    assert f"{BEAT_MAXIMUM_LINE_COUNT}-beat cap" in parsed_response["reason"]


def test_blocks_jargon_word_and_names_the_swap() -> None:
    transcript_path = write_transcript(
        [user_entry(CURRENT_PROMPT_ID), beat_sheet_invocation_entry()]
    )
    completed_run = run_hook(JARGON_REPLY, transcript_path)
    parsed_response = json.loads(completed_run.stdout)
    assert parsed_response["decision"] == "block"
    assert '"utilize" -> "use"' in parsed_response["reason"]


def test_good_beat_reply_passes_when_invoked_this_turn() -> None:
    transcript_path = write_transcript(
        [user_entry(CURRENT_PROMPT_ID), beat_sheet_invocation_entry()]
    )
    completed_run = run_hook(GOOD_BEAT_REPLY, transcript_path)
    assert completed_run.stdout.strip() == ""


def test_good_beat_reply_also_passes_the_eli11_shape_checker() -> None:
    """A well-formed beat-sheet reply must not double-trip the eli11 gate."""
    assert eli11_reply_enforcer.find_reply_shape_violations(GOOD_BEAT_REPLY) == []
    assert beat_sheet_reply_enforcer.find_beat_shape_violations(GOOD_BEAT_REPLY) == []


def test_current_turn_entries_bounds_to_the_trailing_prompt_id() -> None:
    all_entries = [
        user_entry(EARLIER_PROMPT_ID),
        beat_sheet_invocation_entry(),
        assistant_text_entry(),
        user_entry(CURRENT_PROMPT_ID),
        assistant_text_entry(),
    ]
    turn_entries = beat_sheet_reply_enforcer.current_turn_entries(all_entries)
    assert turn_entries == all_entries[3:]


def test_current_turn_entries_returns_everything_with_one_prompt_id() -> None:
    all_entries = [user_entry(CURRENT_PROMPT_ID), beat_sheet_invocation_entry()]
    assert beat_sheet_reply_enforcer.current_turn_entries(all_entries) == all_entries


def test_find_jargon_violations_honors_the_project_allowlist(tmp_path: Path) -> None:
    """Pins the cross-module import to real behavior: an upstream rename to
    either helper breaks this test with an import error, not a silent runtime
    gap, and the allowlisted term is proven to actually clear the reply.
    """
    git_directory = tmp_path / ".git"
    git_directory.mkdir()
    (git_directory / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    claude_directory = tmp_path / ".claude"
    claude_directory.mkdir()
    (claude_directory / "plain-language-allow.json").write_text(
        json.dumps(["utilize"]), encoding="utf-8"
    )

    all_violations = beat_sheet_reply_enforcer.find_jargon_violations(
        JARGON_REPLY, str(tmp_path)
    )

    assert not any("utilize" in each_violation for each_violation in all_violations)
    assert plain_language_blocker._find_project_allowlist_file(tmp_path) is not None
