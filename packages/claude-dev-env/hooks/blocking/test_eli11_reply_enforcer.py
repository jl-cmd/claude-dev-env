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
from hooks_constants.eli11_reply_enforcer_constants import (
    MAXIMUM_BULLET_LINE_COUNT,
    MAXIMUM_OVERPACKED_LINE_COUNT,
    MAXIMUM_REPLY_WORD_COUNT,
    MAXIMUM_WORDS_PER_LINE,
    MINIMUM_ENFORCED_WORD_COUNT,
    TARGET_BULLET_LINE_COUNT,
)
from hooks_constants.text_stripping import strip_code_and_quotes

SAFE_LINE_WORD_COUNT = MAXIMUM_WORDS_PER_LINE // 2
OVERPACKED_LINE_WORD_COUNT = MAXIMUM_WORDS_PER_LINE + 5


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


def build_reply_of_exactly(total_word_count: int) -> str:
    """Return a filler reply holding exactly the requested words, no line overpacked.

    ::

        in:  22  ->  three lines of 10, 10, and 2 filler words

    Args:
        total_word_count: How many countable words the whole reply carries.

    Returns:
        A newline-joined reply whose every line stays under the per-line cap.
    """
    all_lines = []
    remaining_word_count = total_word_count
    while remaining_word_count > 0:
        line_word_count = min(SAFE_LINE_WORD_COUNT, remaining_word_count)
        all_lines.append(build_filler_prose(line_word_count))
        remaining_word_count -= line_word_count
    return "\n".join(all_lines)


SHORT_REPLY_WORD_COUNT = MINIMUM_ENFORCED_WORD_COUNT // 2
OVERLONG_REPLY_WORD_COUNT = MAXIMUM_REPLY_WORD_COUNT * 2
JUST_OVER_WORD_CAP_WORD_COUNT = MAXIMUM_REPLY_WORD_COUNT + 1
UNDER_FLOOR_WORD_COUNT = MINIMUM_ENFORCED_WORD_COUNT - 1

SHORT_REPLY = build_reply_of_exactly(SHORT_REPLY_WORD_COUNT)
OVERLONG_REPLY = build_reply_of_exactly(OVERLONG_REPLY_WORD_COUNT)
UNDER_FLOOR_REPLY = build_reply_of_exactly(UNDER_FLOOR_WORD_COUNT)
JUST_OVER_WORD_CAP_REPLY = build_reply_of_exactly(JUST_OVER_WORD_CAP_WORD_COUNT)
THREE_OVERPACKED_LINE_REPLY = build_prose_block(
    MAXIMUM_OVERPACKED_LINE_COUNT + 1, OVERPACKED_LINE_WORD_COUNT
)
TWO_OVERPACKED_LINES = build_prose_block(
    MAXIMUM_OVERPACKED_LINE_COUNT, OVERPACKED_LINE_WORD_COUNT
)
TWO_OVERPACKED_LINE_REPLY = (
    f"{TWO_OVERPACKED_LINES}\n{build_filler_prose(SAFE_LINE_WORD_COUNT)}"
)
SEVEN_BULLET_JUST_OVER_FLOOR_REPLY = build_bullet_block(
    MAXIMUM_BULLET_LINE_COUNT + 1, SAFE_LINE_WORD_COUNT
)
LONG_FORM_OVERLONG_REPLY = f"Long form: the audit report follows.\n\n{OVERLONG_REPLY}"
BOLD_LONG_FORM_OVERLONG_REPLY = f"**Long form:** the audit report follows.\n\n{OVERLONG_REPLY}"
QUOTED_LONG_FORM_OVERLONG_REPLY = f"> Long form: the audit report follows.\n\n{OVERLONG_REPLY}"
HEADING_LONG_FORM_OVERLONG_REPLY = f"# Long form: the audit report follows.\n\n{OVERLONG_REPLY}"

INSTRUCTION_LINE = "Run the migration script."
INSTRUCTION_LINE_WORD_COUNT = len(INSTRUCTION_LINE.split())

ACTION_WITHOUT_STEPS_FIRST_REPLY = (
    f"{build_reply_of_exactly(MAXIMUM_REPLY_WORD_COUNT // 2)}\n\n"
    f"{INSTRUCTION_LINE}\n\nMerge the branch."
)
ACTION_WITH_STEPS_FIRST_REPLY = (
    "1. **Run** the migration script.\n"
    "2. **Merge** the branch.\n\n"
    f"{build_reply_of_exactly(MAXIMUM_REPLY_WORD_COUNT // 2)}"
)
AT_FLOOR_ACTION_REPLY = (
    f"{build_reply_of_exactly(MINIMUM_ENFORCED_WORD_COUNT - INSTRUCTION_LINE_WORD_COUNT)}"
    f"\n\n{INSTRUCTION_LINE}"
)
SEVEN_BULLET_REPLY = build_bullet_block(
    MAXIMUM_BULLET_LINE_COUNT + 1, SAFE_LINE_WORD_COUNT + 3
)
SIX_BULLET_REPLY = build_bullet_block(
    MAXIMUM_BULLET_LINE_COUNT, SAFE_LINE_WORD_COUNT + 5
)
FENCED_CODE_REPLY = f"{SHORT_REPLY}\n\n```python\n{OVERLONG_REPLY}\n```\n"
BLOCKQUOTE_REPLY = f"{SHORT_REPLY}\n\n> {build_filler_prose(OVERLONG_REPLY_WORD_COUNT)}\n"
TABLE_REPLY = "{}\n\n{}\n".format(
    SHORT_REPLY,
    "\n".join(
        f"| {build_filler_prose(MAXIMUM_WORDS_PER_LINE)} | cell |" for _ in range(15)
    ),
)

ALL_NARRATIVE_OPENER_LINES = (
    "Open questions remain about the stripper edge cases.",
    "Run time stays under one second on the package suite.",
    "Merge is complete on main.",
)
NARRATIVE_OPENER_REPLY = "{}\n\n{}".format(
    "\n".join(ALL_NARRATIVE_OPENER_LINES),
    build_reply_of_exactly(MINIMUM_ENFORCED_WORD_COUNT),
)
INSTALL_WITHOUT_STEPS_FIRST_REPLY = (
    f"{build_reply_of_exactly(MINIMUM_ENFORCED_WORD_COUNT)}\n\n"
    "Install the package from the registry."
)
DO_THINGS_WITH_STEPS_FIRST_REPLY = (
    "Do 3 things:\n"
    "1. Install the package.\n"
    "2. Restart the daemon.\n"
    "3. Save the file.\n\n"
    f"{build_reply_of_exactly(MINIMUM_ENFORCED_WORD_COUNT)}"
)
DO_THINGS_WITHOUT_STEPS_FIRST_REPLY = (
    f"{build_reply_of_exactly(MINIMUM_ENFORCED_WORD_COUNT)}\n\n"
    "Do 3 things: install, restart, save."
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
    assert str(OVERLONG_REPLY_WORD_COUNT) in parsed_response["reason"]
    assert str(MAXIMUM_REPLY_WORD_COUNT) in parsed_response["reason"]


def test_reply_just_over_word_cap_emits_block() -> None:
    """A reply one word past the cap blocks on length alone."""
    completed_process = run_hook_with_message(JUST_OVER_WORD_CAP_REPLY)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"
    assert (
        f"{JUST_OVER_WORD_CAP_WORD_COUNT} words, over the "
        f"{MAXIMUM_REPLY_WORD_COUNT}-word cap"
    ) in parsed_response["reason"]


def test_reply_under_word_floor_passes_through() -> None:
    """A reply one word under the floor is never judged."""
    completed_process = run_hook_with_message(UNDER_FLOOR_REPLY)
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_reply_at_the_word_floor_is_judged_for_action_first() -> None:
    """A reply of exactly the floor word count earns its action-first violation."""
    completed_process = run_hook_with_message(AT_FLOOR_ACTION_REPLY)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"
    assert "put the steps first" in parsed_response["reason"]


def test_reply_just_over_word_floor_is_judged() -> None:
    """A bullet-heavy reply just over the floor earns its bullet violation."""
    completed_process = run_hook_with_message(SEVEN_BULLET_JUST_OVER_FLOOR_REPLY)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"
    assert (
        f"cut findings to {TARGET_BULLET_LINE_COUNT} bullets"
        in parsed_response["reason"]
    )


def test_three_overpacked_lines_emit_block() -> None:
    """One line past the overpacked-line cap blocks on one idea per line."""
    completed_process = run_hook_with_message(THREE_OVERPACKED_LINE_REPLY)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"
    assert "lines carry too many words - one idea per line" in (
        parsed_response["reason"]
    )


def test_two_overpacked_lines_pass_through() -> None:
    """Over-packed lines at the cap pass."""
    completed_process = run_hook_with_message(TWO_OVERPACKED_LINE_REPLY)
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_bullet_marker_is_not_counted_as_a_line_word() -> None:
    """A bullet at the per-line cap stays under it once its marker comes off."""
    capped_bullet_lines = build_bullet_block(
        MAXIMUM_BULLET_LINE_COUNT - 2, MAXIMUM_WORDS_PER_LINE
    )
    all_violations = eli11_reply_enforcer.find_reply_shape_violations(
        capped_bullet_lines
    )
    assert all_violations == []


def test_long_form_prefix_exempts_an_overlong_reply() -> None:
    """The Long form escape hatch clears every reply-shape check."""
    completed_process = run_hook_with_message(LONG_FORM_OVERLONG_REPLY)
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_bold_long_form_prefix_exempts_an_overlong_reply() -> None:
    """A bold-wrapped Long form prefix still opts the reply out."""
    completed_process = run_hook_with_message(BOLD_LONG_FORM_OVERLONG_REPLY)
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_quoted_long_form_prefix_exempts_an_overlong_reply() -> None:
    """A blockquoted Long form prefix still opts the reply out."""
    completed_process = run_hook_with_message(QUOTED_LONG_FORM_OVERLONG_REPLY)
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_heading_long_form_prefix_exempts_an_overlong_reply() -> None:
    """A heading-wrapped Long form prefix still opts the reply out."""
    completed_process = run_hook_with_message(HEADING_LONG_FORM_OVERLONG_REPLY)
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


def test_narrative_lines_opening_with_a_tracked_verb_pass_through() -> None:
    """Narrative openers such as "Open questions remain" are not instructions."""
    completed_process = run_hook_with_message(NARRATIVE_OPENER_REPLY)
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_each_narrative_opener_is_not_an_instruction_line() -> None:
    """Every narrative opener reads as a sentence subject, not an imperative."""
    for each_line in ALL_NARRATIVE_OPENER_LINES:
        assert not eli11_reply_enforcer.is_imperative_instruction_line(each_line)


def test_object_word_after_leading_verb_reads_the_second_word() -> None:
    """The word after the opening verb comes back, list markers ignored."""
    assert eli11_reply_enforcer.object_word_after_leading_verb(
        "1. **Run** the migration script."
    ) == "the"
    assert eli11_reply_enforcer.object_word_after_leading_verb("Merge") == ""


def test_names_imperative_object_accepts_determiners_counts_and_paths() -> None:
    """A determiner, a count, or a path marks a real imperative object."""
    assert eli11_reply_enforcer.names_imperative_object("the")
    assert eli11_reply_enforcer.names_imperative_object("3")
    assert eli11_reply_enforcer.names_imperative_object("scripts/deploy.py")
    assert not eli11_reply_enforcer.names_imperative_object("questions")
    assert not eli11_reply_enforcer.names_imperative_object("")


def test_strip_markdown_lead_markers_removes_every_wrapper() -> None:
    """Blockquote, heading, and bold wrappers come off the front of a line."""
    assert eli11_reply_enforcer.strip_markdown_lead_markers(
        "> **Long form:** the report follows"
    ) == "Long form:** the report follows"
    assert eli11_reply_enforcer.strip_markdown_lead_markers(
        "# Long form: the report follows"
    ) == "Long form: the report follows"


def test_install_instruction_without_leading_steps_emits_block() -> None:
    """An install instruction buried under prose blocks on action-first."""
    completed_process = run_hook_with_message(INSTALL_WITHOUT_STEPS_FIRST_REPLY)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"
    assert "put the steps first" in parsed_response["reason"]


def test_do_three_things_without_leading_steps_emits_block() -> None:
    """The canonical "Do 3 things:" opener counts as an instruction line."""
    completed_process = run_hook_with_message(DO_THINGS_WITHOUT_STEPS_FIRST_REPLY)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"
    assert "put the steps first" in parsed_response["reason"]


def test_do_three_things_with_numbered_steps_passes_through() -> None:
    """The canonical action-first opener with its numbered steps passes."""
    completed_process = run_hook_with_message(DO_THINGS_WITH_STEPS_FIRST_REPLY)
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_decimal_and_year_openers_are_not_numbered_steps() -> None:
    """A decimal or a year opening a line is prose, not a numbered step."""
    assert not eli11_reply_enforcer.has_leading_numbered_step(
        ["1.5% of hosts still fail."]
    )
    assert not eli11_reply_enforcer.has_leading_numbered_step(
        ["2024. Revenue doubled."]
    )


def test_numbered_step_opener_is_a_numbered_step() -> None:
    """A digit, a period, and a space open a real numbered step."""
    assert eli11_reply_enforcer.has_leading_numbered_step(["1. Run the script"])


def test_more_than_six_bullets_emits_block() -> None:
    """One bullet past the cap blocks with the cut-to-target-bullets message."""
    completed_process = run_hook_with_message(SEVEN_BULLET_REPLY)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"
    assert (
        f"cut findings to {TARGET_BULLET_LINE_COUNT} bullets"
        in parsed_response["reason"]
    )


def test_six_bullets_pass_through() -> None:
    """Bullets at the cap pass."""
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
