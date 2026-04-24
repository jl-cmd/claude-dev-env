"""Tests for question_to_user_enforcer hook response shape and detection logic."""

import json
import os
import subprocess
import sys

HOOK_SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__), "question_to_user_enforcer.py"
)
_HOOKS_DIR = os.path.dirname(HOOK_SCRIPT_PATH)
_HOOKS_ROOT = os.path.join(_HOOKS_DIR, "..")
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)
if _HOOKS_ROOT not in sys.path:
    sys.path.insert(0, _HOOKS_ROOT)
from config.messages import USER_FACING_ASKUSERQUESTION_NOTICE

CLEAN_DECLARATIVE_MESSAGE = "I applied the rename across both files. The tests pass."
TRAILING_QUESTION_MESSAGE = (
    "I applied the rename across both files. Should this also propagate to the docs?"
)
WANT_ME_TO_MESSAGE = "I finished the refactor.\n\nWant me to open the PR now?"
SHOULD_I_STATEMENT_MESSAGE = (
    "The diff is ready.\n\nShould I proceed with committing it."
)
FENCED_CODE_QUESTION_MESSAGE = (
    "Here is the diagnostic snippet:\n\n"
    "```python\n"
    "print('does this work?')\n"
    "```\n\n"
    "The snippet confirms the behavior."
)
RHETORICAL_MIDDLE_MESSAGE = (
    "Consider the failure mode.\n\n"
    "What happens if the queue is empty? The handler short-circuits cleanly.\n\n"
    "That covers the edge case."
)
QUESTION_WITH_TRAILING_DOUBLE_QUOTE_MESSAGE = (
    'I renamed the flag.\n\nDid you mean "enable_fast_path?"'
)
QUESTION_WITH_TRAILING_SINGLE_QUOTE_MESSAGE = (
    "I renamed the flag.\n\nDid you mean 'enable_fast_path?'"
)
QUESTION_WITH_TRAILING_PAREN_MESSAGE = (
    "I finished the refactor.\n\nShould I also bump the version (minor or patch?)"
)
QUESTION_WITH_TRAILING_BRACKET_MESSAGE = (
    "I finished the refactor.\n\nShould I also bump the version [minor or patch?]"
)
QUESTION_WITH_TRAILING_SPACE_MESSAGE = (
    "I finished the refactor.\n\nShould I also bump the version? "
)


def run_hook_with_payload(payload: dict) -> subprocess.CompletedProcess:
    hook_input_payload = json.dumps(payload)
    return subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=hook_input_payload,
        capture_output=True,
        text=True,
        check=False,
    )


def run_hook_with_message(assistant_message: str) -> subprocess.CompletedProcess:
    return run_hook_with_payload({"last_assistant_message": assistant_message})


def test_clean_declarative_message_passes_through():
    completed_process = run_hook_with_message(CLEAN_DECLARATIVE_MESSAGE)
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_final_paragraph_ending_with_question_mark_emits_block():
    completed_process = run_hook_with_message(TRAILING_QUESTION_MESSAGE)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"


def test_want_me_to_preamble_in_final_paragraph_emits_block():
    completed_process = run_hook_with_message(WANT_ME_TO_MESSAGE)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"


def test_should_i_preamble_without_question_mark_emits_block():
    completed_process = run_hook_with_message(SHOULD_I_STATEMENT_MESSAGE)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"


def test_question_mark_inside_fenced_code_block_passes_through():
    completed_process = run_hook_with_message(FENCED_CODE_QUESTION_MESSAGE)
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_stop_hook_active_flag_passes_through():
    completed_process = run_hook_with_payload(
        {
            "last_assistant_message": TRAILING_QUESTION_MESSAGE,
            "stop_hook_active": True,
        }
    )
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_rhetorical_middle_paragraph_with_declarative_final_passes_through():
    completed_process = run_hook_with_message(RHETORICAL_MIDDLE_MESSAGE)
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_block_response_json_shape():
    completed_process = run_hook_with_message(TRAILING_QUESTION_MESSAGE)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"
    assert "AskUserQuestion" in parsed_response["reason"]
    assert parsed_response["systemMessage"] == USER_FACING_ASKUSERQUESTION_NOTICE
    assert parsed_response["suppressOutput"] is True


def test_question_followed_by_double_quote_emits_block():
    completed_process = run_hook_with_message(QUESTION_WITH_TRAILING_DOUBLE_QUOTE_MESSAGE)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"


def test_question_followed_by_single_quote_emits_block():
    completed_process = run_hook_with_message(QUESTION_WITH_TRAILING_SINGLE_QUOTE_MESSAGE)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"


def test_question_followed_by_closing_paren_emits_block():
    completed_process = run_hook_with_message(QUESTION_WITH_TRAILING_PAREN_MESSAGE)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"


def test_question_followed_by_closing_bracket_emits_block():
    completed_process = run_hook_with_message(QUESTION_WITH_TRAILING_BRACKET_MESSAGE)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"


def test_question_followed_by_trailing_space_emits_block():
    completed_process = run_hook_with_message(QUESTION_WITH_TRAILING_SPACE_MESSAGE)
    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"
