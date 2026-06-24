"""Tests for session_handoff_blocker hook response shape."""

import importlib.util
import json
import os
import subprocess
import sys

HOOK_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "session_handoff_blocker.py")
_HOOKS_DIR = os.path.dirname(HOOK_SCRIPT_PATH)
_HOOKS_ROOT = os.path.join(_HOOKS_DIR, "..")
_HOOK_CONFIG_DIR = os.path.join(_HOOKS_ROOT, "hooks_constants")
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)
if _HOOKS_ROOT not in sys.path:
    sys.path.insert(0, _HOOKS_ROOT)
import session_handoff_blocker
from hooks_constants.messages import USER_FACING_CONTEXT_REASSURANCE_NOTICE
from hooks_constants.text_stripping import strip_code_and_quotes


def test_blocker_uses_shared_strip_code_and_quotes() -> None:
    assert session_handoff_blocker.strip_code_and_quotes is strip_code_and_quotes


NEW_SESSION_PROPOSAL_MESSAGE = (
    "I recommend we continue this in a fresh session to keep things manageable."
)
RUNNING_LOW_ON_CONTEXT_MESSAGE = (
    "We are running low on context, so let me summarize where things stand."
)
SHORT_ON_TOKENS_MESSAGE = "I'm getting short on tokens, so I'll wrap up here."
CONSERVE_CONTEXT_MESSAGE = "To conserve context, let me stop and hand off the remaining work."
CONTEXT_WINDOW_HANDOFF_MESSAGE = (
    "The context window is filling up, so I'll wrap up and we can continue later."
)
BENIGN_TOPICAL_MESSAGE = "The function accepts a context manager and a token string."
CLEAN_MESSAGE = "The parser handles every fixture and returns a deduplicated list."
TECHNICAL_TERMINAL_SESSION_MESSAGE = (
    "Consider starting a new session in your terminal to pick up the env vars."
)
LOAD_TEST_SESSION_MESSAGE = "We can spin up a fresh session for the load test."
DATABASE_SESSION_MESSAGE = "Open a new database session before running the query."
HANDOFF_NEW_SESSION_MESSAGE = (
    "Let's wrap up and continue this in a fresh session to pick this up later."
)
LOW_ON_CONTEXT_WITHOUT_CUE_MESSAGE = (
    "I am low on context for this edge case in the parser."
)
SAVE_TOKENS_REPORT_MESSAGE = "To save tokens, I inlined the constant."
LOW_ON_CONTEXT_WITH_HANDOFF_CUE_MESSAGE = (
    "I'm low on context, so let me wrap up and hand off."
)
NEW_SESSION_TOKEN_MESSAGE = (
    "To continue this task I need the new session token from the API."
)
RESUME_TRAFFIC_FRESH_SESSION_POOL_MESSAGE = (
    "After deploy, resume traffic in a fresh session pool."
)
THIRD_PERSON_RUNS_LOW_DESIGN_MESSAGE = (
    "The agent should stop when it runs low on context, per the old design."
)
DOCUMENT_RUNNING_LOW_MESSAGE = (
    "Document that agents running low on tokens should not stop."
)
USER_ADVICE_NEW_SESSION_MESSAGE = (
    "To save tokens, you could start a new session for the unrelated task."
)
CONTEXT_WINDOW_SUMMARIZE_MESSAGE = (
    "The context window is getting full, so let me summarize where we are."
)
BENIGN_SUMMARIZE_REPORT_MESSAGE = "I should summarize the findings for the report."
BENIGN_STOP_PLUS_UNRELATED_RUNNING_LOW_MESSAGE = (
    "Let me pause the animation timer. The job fails when it is running low on tokens."
)
BENIGN_STOP_PLUS_USER_DIRECTED_NEW_SESSION_MESSAGE = (
    "Let me stop the timer. The user can continue this in a fresh session."
)
EMPTY_MESSAGE = ""


def run_hook_with_message(assistant_message: str) -> subprocess.CompletedProcess:
    hook_input_payload = json.dumps({"last_assistant_message": assistant_message})
    return subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=hook_input_payload,
        capture_output=True,
        text=True,
        check=False,
    )


def run_hook_with_payload(hook_input_payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=json.dumps(hook_input_payload),
        capture_output=True,
        text=True,
        check=False,
    )


def test_user_facing_notice_matches_config_messages_module():
    config_messages_path = os.path.join(_HOOK_CONFIG_DIR, "messages.py")
    specification = importlib.util.spec_from_file_location("messages", config_messages_path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)

    assert module.USER_FACING_CONTEXT_REASSURANCE_NOTICE == USER_FACING_CONTEXT_REASSURANCE_NOTICE
    assert (
        session_handoff_blocker.USER_FACING_CONTEXT_REASSURANCE_NOTICE
        == module.USER_FACING_CONTEXT_REASSURANCE_NOTICE
    )


def test_new_session_proposal_emits_block_with_short_user_notice():
    completed_process = run_hook_with_message(NEW_SESSION_PROPOSAL_MESSAGE)

    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)

    assert parsed_response["decision"] == "block"
    assert parsed_response["systemMessage"] == USER_FACING_CONTEXT_REASSURANCE_NOTICE
    assert parsed_response["suppressOutput"] is True
    assert "ample context remaining" in parsed_response["reason"]
    assert "long-horizon-autonomy" in parsed_response["reason"]


def test_running_low_on_context_emits_block():
    completed_process = run_hook_with_message(RUNNING_LOW_ON_CONTEXT_MESSAGE)

    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)

    assert parsed_response["decision"] == "block"
    assert parsed_response["systemMessage"] == USER_FACING_CONTEXT_REASSURANCE_NOTICE


def test_short_on_tokens_emits_block():
    completed_process = run_hook_with_message(SHORT_ON_TOKENS_MESSAGE)

    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)

    assert parsed_response["decision"] == "block"


def test_conserve_context_emits_block():
    completed_process = run_hook_with_message(CONSERVE_CONTEXT_MESSAGE)

    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)

    assert parsed_response["decision"] == "block"


def test_context_window_co_occurring_handoff_cue_emits_block():
    completed_process = run_hook_with_message(CONTEXT_WINDOW_HANDOFF_MESSAGE)

    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)

    assert parsed_response["decision"] == "block"


def test_benign_topical_mention_passes_through_with_no_output():
    completed_process = run_hook_with_message(BENIGN_TOPICAL_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_technical_terminal_session_passes_through_with_no_output():
    completed_process = run_hook_with_message(TECHNICAL_TERMINAL_SESSION_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_load_test_session_passes_through_with_no_output():
    completed_process = run_hook_with_message(LOAD_TEST_SESSION_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_database_session_passes_through_with_no_output():
    completed_process = run_hook_with_message(DATABASE_SESSION_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_new_session_with_handoff_framing_emits_block():
    completed_process = run_hook_with_message(HANDOFF_NEW_SESSION_MESSAGE)

    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)

    assert parsed_response["decision"] == "block"
    assert parsed_response["systemMessage"] == USER_FACING_CONTEXT_REASSURANCE_NOTICE


def test_low_on_context_without_handoff_cue_passes_through_with_no_output():
    completed_process = run_hook_with_message(LOW_ON_CONTEXT_WITHOUT_CUE_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_save_tokens_work_report_passes_through_with_no_output():
    completed_process = run_hook_with_message(SAVE_TOKENS_REPORT_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_low_on_context_with_handoff_cue_emits_block():
    completed_process = run_hook_with_message(LOW_ON_CONTEXT_WITH_HANDOFF_CUE_MESSAGE)

    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)

    assert parsed_response["decision"] == "block"
    assert parsed_response["systemMessage"] == USER_FACING_CONTEXT_REASSURANCE_NOTICE


def test_new_session_token_passes_through_with_no_output():
    completed_process = run_hook_with_message(NEW_SESSION_TOKEN_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_resume_traffic_fresh_session_pool_passes_through_with_no_output():
    completed_process = run_hook_with_message(RESUME_TRAFFIC_FRESH_SESSION_POOL_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_third_person_runs_low_description_passes_through_with_no_output():
    completed_process = run_hook_with_message(THIRD_PERSON_RUNS_LOW_DESIGN_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_document_running_low_instruction_passes_through_with_no_output():
    completed_process = run_hook_with_message(DOCUMENT_RUNNING_LOW_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_user_directed_new_session_advice_passes_through_with_no_output():
    completed_process = run_hook_with_message(USER_ADVICE_NEW_SESSION_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_context_window_summarize_handoff_emits_block():
    completed_process = run_hook_with_message(CONTEXT_WINDOW_SUMMARIZE_MESSAGE)

    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)

    assert parsed_response["decision"] == "block"
    assert parsed_response["systemMessage"] == USER_FACING_CONTEXT_REASSURANCE_NOTICE


def test_benign_summarize_report_passes_through_with_no_output():
    completed_process = run_hook_with_message(BENIGN_SUMMARIZE_REPORT_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_benign_stop_with_unrelated_running_low_sentence_passes_through_with_no_output():
    completed_process = run_hook_with_message(
        BENIGN_STOP_PLUS_UNRELATED_RUNNING_LOW_MESSAGE
    )

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_benign_stop_with_user_directed_new_session_sentence_passes_through_with_no_output():
    completed_process = run_hook_with_message(
        BENIGN_STOP_PLUS_USER_DIRECTED_NEW_SESSION_MESSAGE
    )

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_clean_message_passes_through_with_no_output():
    completed_process = run_hook_with_message(CLEAN_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_empty_message_passes_through_with_no_output():
    completed_process = run_hook_with_message(EMPTY_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_stop_hook_active_short_circuits_with_no_output():
    completed_process = run_hook_with_payload(
        {"last_assistant_message": NEW_SESSION_PROPOSAL_MESSAGE, "stop_hook_active": True}
    )

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""
