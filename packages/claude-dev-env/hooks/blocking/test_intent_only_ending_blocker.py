"""Tests for intent_only_ending_blocker hook response shape."""

import importlib.util
import json
import os
import subprocess
import sys

HOOK_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "intent_only_ending_blocker.py")
_HOOKS_DIR = os.path.dirname(HOOK_SCRIPT_PATH)
_HOOKS_ROOT = os.path.join(_HOOKS_DIR, "..")
_HOOK_CONFIG_DIR = os.path.join(_HOOKS_ROOT, "hooks_constants")
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)
if _HOOKS_ROOT not in sys.path:
    sys.path.insert(0, _HOOKS_ROOT)
import intent_only_ending_blocker
from hooks_constants.messages import USER_FACING_INTENT_ENDING_NOTICE

INTENT_ENDING_MESSAGE = "I'll now run the test suite and fix any failures that come up."
NEXT_STEPS_MESSAGE = "Next steps:"
COMPLETED_WORK_MESSAGE = "Done - all tests pass. The fix is in place."
BENIGN_PAST_TENSE_MESSAGE = "I implemented the parser and verified it against the fixtures."
CLEAN_MESSAGE = "The function returns the parsed payload to its caller."
COMMITMENT_PHRASING_MESSAGE = "I'll commit to keeping the API stable across the next release."
NAMING_COMMITMENT_MESSAGE = "Let me commit to a clear naming convention for these helpers."
GIT_COMMIT_INTENT_MESSAGE = "I'll commit the changes once the tests pass."
DEFERRED_TO_USER_CI_RUNS_MESSAGE = (
    "Let me know if this looks right. The CI will run automatically on push."
)
DEFERRED_TO_USER_EITHER_WAY_MESSAGE = (
    "Let me know which option you want. I can check either way."
)
USER_DIRECTED_NEXT_STEPS_MESSAGE = (
    "All done. The PR is merged.\n\nNext steps: you should deploy when ready."
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

    assert module.USER_FACING_INTENT_ENDING_NOTICE == USER_FACING_INTENT_ENDING_NOTICE
    assert (
        intent_only_ending_blocker.USER_FACING_INTENT_ENDING_NOTICE
        == module.USER_FACING_INTENT_ENDING_NOTICE
    )


def test_intent_ending_message_emits_block_with_short_user_notice():
    completed_process = run_hook_with_message(INTENT_ENDING_MESSAGE)

    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)

    assert parsed_response["decision"] == "block"
    assert parsed_response["systemMessage"] == USER_FACING_INTENT_ENDING_NOTICE
    assert parsed_response["suppressOutput"] is True
    assert "long-horizon-autonomy" in parsed_response["reason"]


def test_next_steps_lead_in_emits_block():
    completed_process = run_hook_with_message(NEXT_STEPS_MESSAGE)

    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)

    assert parsed_response["decision"] == "block"
    assert parsed_response["systemMessage"] == USER_FACING_INTENT_ENDING_NOTICE


def test_completed_work_summary_passes_through_with_no_output():
    completed_process = run_hook_with_message(COMPLETED_WORK_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_past_tense_summary_passes_through_with_no_output():
    completed_process = run_hook_with_message(BENIGN_PAST_TENSE_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_commitment_phrasing_passes_through_with_no_output():
    completed_process = run_hook_with_message(COMMITMENT_PHRASING_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_naming_commitment_passes_through_with_no_output():
    completed_process = run_hook_with_message(NAMING_COMMITMENT_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_git_commit_intent_emits_block():
    completed_process = run_hook_with_message(GIT_COMMIT_INTENT_MESSAGE)

    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)

    assert parsed_response["decision"] == "block"
    assert parsed_response["systemMessage"] == USER_FACING_INTENT_ENDING_NOTICE


def test_benign_opener_with_unrelated_work_verb_passes_through_with_no_output():
    completed_process = run_hook_with_message(DEFERRED_TO_USER_CI_RUNS_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_deferral_to_user_with_later_verb_passes_through_with_no_output():
    completed_process = run_hook_with_message(DEFERRED_TO_USER_EITHER_WAY_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_user_directed_next_steps_passes_through_with_no_output():
    completed_process = run_hook_with_message(USER_DIRECTED_NEXT_STEPS_MESSAGE)

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
        {"last_assistant_message": INTENT_ENDING_MESSAGE, "stop_hook_active": True}
    )

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""
