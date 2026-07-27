"""Tests for eli11_reply_enforcer hook response shape and reply-shape detection."""

import json
import os
import subprocess
import sys

HOOK_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "eli11_reply_enforcer.py")
_HOOKS_DIR = os.path.dirname(HOOK_SCRIPT_PATH)
_HOOKS_ROOT = os.path.join(_HOOKS_DIR, "..")
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)
if _HOOKS_ROOT not in sys.path:
    sys.path.insert(0, _HOOKS_ROOT)
import eli11_reply_enforcer
from hooks_constants.text_stripping import strip_code_and_quotes


def build_filler_prose(word_count: int) -> str:
    """Return a single prose line holding exactly the requested number of words."""
    return " ".join(f"finding{each_index}" for each_index in range(word_count))


def build_bullet_block(bullet_count: int, words_per_bullet: int) -> str:
    """Return a bullet list of the requested size, each bullet a filler line."""
    return "\n".join(
        f"- {build_filler_prose(words_per_bullet)}" for _ in range(bullet_count)
    )


def build_prose_block(line_count: int, words_per_line: int) -> str:
    """Return a block of plain prose lines, each holding the requested words."""
    return "\n".join(build_filler_prose(words_per_line) for _ in range(line_count))


SHORT_REPLY = build_filler_prose(40)
OVERLONG_REPLY = build_filler_prose(260)
UNDER_FLOOR_REPLY = build_prose_block(3, 18)
JUST_OVER_WORD_CAP_REPLY = build_prose_block(13, 10)
THREE_OVERPACKED_LINE_REPLY = build_prose_block(3, 25)
TWO_OVERPACKED_LINE_REPLY = f"{build_prose_block(2, 25)}\n{build_filler_prose(15)}"
SEVEN_BULLET_JUST_OVER_FLOOR_REPLY = build_bullet_block(7, 10)
LONG_FORM_OVERLONG_REPLY = f"Long form: the audit report follows.\n\n{OVERLONG_REPLY}"
ACTION_WITHOUT_STEPS_FIRST_REPLY = (
    f"{build_filler_prose(90)}\n\nRun the migration script.\n\nMerge the branch."
)
ACTION_WITH_STEPS_FIRST_REPLY = (
    "1. **Run** the migration script.\n"
    "2. **Merge** the branch.\n\n"
    f"{build_filler_prose(90)}"
)
SEVEN_BULLET_REPLY = build_bullet_block(7, 13)
SIX_BULLET_REPLY = build_bullet_block(6, 15)
FENCED_CODE_REPLY = (
    f"{SHORT_REPLY}\n\n```python\n{build_filler_prose(300)}\n```\n"
)
BLOCKQUOTE_REPLY = f"{SHORT_REPLY}\n\n> {build_filler_prose(300)}\n"
TABLE_REPLY = "{}\n\n{}\n".format(
    SHORT_REPLY,
    "\n".join(f"| {build_filler_prose(20)} | cell |" for _ in range(15)),
)


def run_hook_with_payload(payload: dict) -> subprocess.CompletedProcess:
    """Run the hook script with the given Stop payload and capture its output."""
    hook_input_payload = json.dumps(payload)
    return subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=hook_input_payload,
        capture_output=True,
        text=True,
        check=False,
    )


def run_hook_with_message(assistant_message: str) -> subprocess.CompletedProcess:
    """Run the hook against a single assistant message."""
    return run_hook_with_payload({"last_assistant_message": assistant_message})


def test_blocker_uses_shared_strip_code_and_quotes() -> None:
    """The hook reuses the shared stripper rather than re-implementing it."""
    assert eli11_reply_enforcer.strip_code_and_quotes is strip_code_and_quotes


def test_short_reply_passes_through() -> None:
    """A reply under the enforced word floor is never judged."""
    completed_process = run_hook_with_message(SHORT_REPLY)
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_empty_message_passes_through() -> None:
    """A tool-only turn carries no assistant prose and passes."""
    completed_process = run_hook_with_message("")
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_stop_hook_active_flag_passes_through() -> None:
    """A re-entrant Stop invocation never blocks again."""
    completed_process = run_hook_with_payload(
        {"last_assistant_message": OVERLONG_REPLY, "stop_hook_active": True}
    )
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_reply_over_word_cap_emits_block() -> None:
    """A reply past the word cap blocks with the count and the cap named."""
    completed_process = run_hook_with_message(OVERLONG_REPLY)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"
    assert "260" in parsed_response["reason"]
    assert "120" in parsed_response["reason"]


def test_reply_just_over_word_cap_emits_block() -> None:
    """A 130-word reply sits past the 120-word cap and blocks on length alone."""
    completed_process = run_hook_with_message(JUST_OVER_WORD_CAP_REPLY)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"
    assert "130 words, over the 120-word cap" in parsed_response["reason"]


def test_reply_under_word_floor_passes_through() -> None:
    """A 54-word reply sits under the 60-word floor and is never judged."""
    completed_process = run_hook_with_message(UNDER_FLOOR_REPLY)
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_reply_just_over_word_floor_is_judged() -> None:
    """A 70-word reply clears the 60-word floor and earns its bullet violation."""
    completed_process = run_hook_with_message(SEVEN_BULLET_JUST_OVER_FLOOR_REPLY)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"
    assert "cut findings to 3 bullets" in parsed_response["reason"]


def test_three_overpacked_lines_emit_block() -> None:
    """A third line carrying more than 20 words blocks on one idea per line."""
    completed_process = run_hook_with_message(THREE_OVERPACKED_LINE_REPLY)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"
    assert "lines carry too many words - one idea per line" in (
        parsed_response["reason"]
    )


def test_two_overpacked_lines_pass_through() -> None:
    """Two over-packed lines sit at the cap and pass."""
    completed_process = run_hook_with_message(TWO_OVERPACKED_LINE_REPLY)
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_bullet_marker_is_not_counted_as_a_line_word() -> None:
    """A 20-word bullet stays under the per-line cap once its marker comes off."""
    twenty_word_bullet_lines = build_bullet_block(4, 20)
    all_violations = eli11_reply_enforcer.find_reply_shape_violations(
        twenty_word_bullet_lines
    )
    assert all_violations == []


def test_long_form_prefix_exempts_an_overlong_reply() -> None:
    """The Long form escape hatch clears every reply-shape check."""
    completed_process = run_hook_with_message(LONG_FORM_OVERLONG_REPLY)
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_instruction_lines_without_leading_steps_emit_block() -> None:
    """Imperative instructions buried under prose block with a steps-first message."""
    completed_process = run_hook_with_message(ACTION_WITHOUT_STEPS_FIRST_REPLY)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"
    assert "put the steps first" in parsed_response["reason"]


def test_numbered_steps_in_lead_lines_pass_through() -> None:
    """Numbered steps inside the lead lines satisfy the action-first check."""
    completed_process = run_hook_with_message(ACTION_WITH_STEPS_FIRST_REPLY)
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_more_than_six_bullets_emits_block() -> None:
    """A seventh bullet blocks with the cut-to-three-bullets message."""
    completed_process = run_hook_with_message(SEVEN_BULLET_REPLY)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"
    assert "cut findings to 3 bullets" in parsed_response["reason"]


def test_six_bullets_pass_through() -> None:
    """Six bullets sit at the cap and pass."""
    completed_process = run_hook_with_message(SIX_BULLET_REPLY)
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_fenced_code_words_are_not_counted() -> None:
    """Words inside a fenced code block never push a reply past the cap."""
    completed_process = run_hook_with_message(FENCED_CODE_REPLY)
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_blockquote_words_are_not_counted() -> None:
    """Quoted lines are the user's words and never push a reply past the cap."""
    completed_process = run_hook_with_message(BLOCKQUOTE_REPLY)
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_table_rows_are_not_counted() -> None:
    """Table rows carry reference data and never push a reply past the cap."""
    completed_process = run_hook_with_message(TABLE_REPLY)
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_urls_are_removed_from_counted_prose() -> None:
    """A link target is stripped before the words are counted."""
    prose_text = eli11_reply_enforcer.extract_reply_prose(
        "The draft is at https://github.com/owner/repo/pull/704 now"
    )
    assert "github.com" not in prose_text
    assert "draft" in prose_text


def test_block_response_json_shape() -> None:
    """The block payload carries the Stop-hook keys and names the escape hatch."""
    completed_process = run_hook_with_message(OVERLONG_REPLY)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"
    assert parsed_response["suppressOutput"] is True
    assert parsed_response["systemMessage"]
    assert "Long form:" in parsed_response["reason"]
