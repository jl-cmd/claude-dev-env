"""Tests for hedging_language_blocker hook response shape."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HOOK_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "hedging_language_blocker.py")
_HOOKS_DIR = os.path.dirname(HOOK_SCRIPT_PATH)
_CONFIG_DIR = os.path.join(_HOOKS_DIR, "..", "config")
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)
if _CONFIG_DIR not in sys.path:
    sys.path.insert(0, _CONFIG_DIR)
import hedging_language_blocker
from messages import USER_FACING_NOTICE

RESEARCH_MODE_SKILL_BODY_MARKER = "Three anti-hallucination constraints are ALWAYS active."
HEDGING_MESSAGE = "This is likely correct."
CLEAN_MESSAGE = "This is verified by the source document."
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


def run_hook_with_patched_search_paths(
    assistant_message: str,
    search_paths: list[str],
) -> subprocess.CompletedProcess:
    """Run the hook with RESEARCH_MODE_SKILL_SEARCH_PATHS overridden via a wrapper script."""
    wrapper_script = (
        "import sys, json, os\n"
        f"sys.path.insert(0, {repr(os.path.dirname(HOOK_SCRIPT_PATH))})\n"
        "import hedging_language_blocker as blocker\n"
        f"blocker.RESEARCH_MODE_SKILL_SEARCH_PATHS = {repr(search_paths)}\n"
        "blocker.main()\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as wrapper_file:
        wrapper_file.write(wrapper_script)
        wrapper_file_path = wrapper_file.name

    hook_input_payload = json.dumps({"last_assistant_message": assistant_message})
    try:
        completed_process = subprocess.run(
            [sys.executable, wrapper_file_path],
            input=hook_input_payload,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        os.unlink(wrapper_file_path)
    return completed_process


def test_user_facing_notice_importable_from_config_messages():
    config_messages_path = os.path.join(_CONFIG_DIR, "messages.py")
    specification = importlib.util.spec_from_file_location("messages", config_messages_path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)

    assert module.USER_FACING_NOTICE == USER_FACING_NOTICE


def test_hedging_message_emits_block_with_short_user_notice():
    completed_process = run_hook_with_message(HEDGING_MESSAGE)

    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)

    assert parsed_response["decision"] == "block"
    assert parsed_response["systemMessage"] == USER_FACING_NOTICE
    assert parsed_response["suppressOutput"] is True
    assert "likely" in parsed_response["reason"]


def test_hedging_reason_contains_not_installed_notice_when_skill_absent():
    completed_process = run_hook_with_patched_search_paths(
        HEDGING_MESSAGE,
        ["/nonexistent/path/one/SKILL.md", "/nonexistent/path/two/SKILL.md"],
    )

    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)

    assert parsed_response["decision"] == "block"
    assert "no research-mode skill installed" in parsed_response["reason"]
    assert "verify with sources or reply" in parsed_response["reason"]
    assert "SKILL.md" not in parsed_response["reason"]
    assert RESEARCH_MODE_SKILL_BODY_MARKER not in parsed_response["reason"]


def test_hedging_reason_contains_skill_path_when_skill_present():
    with tempfile.TemporaryDirectory() as skill_dir:
        skill_file_path = os.path.join(skill_dir, "SKILL.md")
        with open(skill_file_path, "w") as skill_file:
            skill_file.write("# Research Mode Skill\n")

        completed_process = run_hook_with_patched_search_paths(
            HEDGING_MESSAGE,
            ["/nonexistent/path/SKILL.md", skill_file_path],
        )

    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)

    assert parsed_response["decision"] == "block"
    assert "SKILL.md" in parsed_response["reason"]
    assert "no research-mode skill installed" not in parsed_response["reason"]
    assert RESEARCH_MODE_SKILL_BODY_MARKER not in parsed_response["reason"]


def test_clean_message_passes_through_with_no_output():
    completed_process = run_hook_with_message(CLEAN_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_empty_message_passes_through_with_no_output():
    completed_process = run_hook_with_message(EMPTY_MESSAGE)

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""
