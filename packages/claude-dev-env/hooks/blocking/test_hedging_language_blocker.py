"""Tests for hedging_language_blocker hook response shape."""

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile

import pytest

HOOK_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "hedging_language_blocker.py")
_HOOKS_DIR = os.path.dirname(HOOK_SCRIPT_PATH)
_HOOKS_ROOT = os.path.join(_HOOKS_DIR, "..")
_HOOK_CONFIG_DIR = os.path.join(_HOOKS_ROOT, "hooks_constants")
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)
if _HOOKS_ROOT not in sys.path:
    sys.path.insert(0, _HOOKS_ROOT)
import hedging_language_blocker
from hooks_constants.messages import USER_FACING_NOTICE
from hooks_constants.text_stripping import strip_code_and_quotes


def test_blocker_uses_shared_strip_code_and_quotes() -> None:
    assert hedging_language_blocker.strip_code_and_quotes is strip_code_and_quotes


RESEARCH_MODE_SKILL_BODY_MARKER = "Three anti-hallucination constraints are ALWAYS active."
HEDGING_MESSAGE = "This is likely correct."
CLEAN_MESSAGE = "This is verified by the source document."
EMPTY_MESSAGE = ""


def run_hook_with_message(
    assistant_message: str, *, is_prose_style_enabled: bool = True
) -> subprocess.CompletedProcess:
    hook_input_payload = json.dumps({"last_assistant_message": assistant_message})
    environment_by_key = os.environ.copy()
    if is_prose_style_enabled:
        environment_by_key["CLAUDE_PROSE_STYLE_ENFORCEMENT"] = "1"
    else:
        environment_by_key.pop("CLAUDE_PROSE_STYLE_ENFORCEMENT", None)
    return subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=hook_input_payload,
        capture_output=True,
        text=True,
        check=False,
        env=environment_by_key,
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
    environment_by_key = os.environ.copy()
    environment_by_key["CLAUDE_PROSE_STYLE_ENFORCEMENT"] = "1"
    try:
        completed_process = subprocess.run(
            [sys.executable, wrapper_file_path],
            input=hook_input_payload,
            capture_output=True,
            text=True,
            check=False,
            env=environment_by_key,
        )
    finally:
        os.unlink(wrapper_file_path)
    return completed_process


def test_user_facing_notice_matches_config_messages_module():
    config_messages_path = os.path.join(_HOOK_CONFIG_DIR, "messages.py")
    specification = importlib.util.spec_from_file_location("messages", config_messages_path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)

    assert module.USER_FACING_NOTICE == USER_FACING_NOTICE


def test_hedging_scan_is_default_off() -> None:
    completed_process = run_hook_with_message(
        HEDGING_MESSAGE, is_prose_style_enabled=False
    )

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_default_off_emits_privacy_safe_advisory_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_emitted: list[tuple[str, str, str]] = []

    def _record_advisory(
        matcher_id: str, surface: str, context_text: str, **_kwargs: object
    ) -> dict[str, object]:
        all_emitted.append((matcher_id, surface, context_text))
        return {}

    monkeypatch.setattr(
        hedging_language_blocker, "emit_advisory_candidate", _record_advisory
    )
    monkeypatch.setattr(
        hedging_language_blocker,
        "prose_style_enforcement_enabled_in_environment",
        lambda: False,
    )
    monkeypatch.setattr(
        hedging_language_blocker.sys,
        "stdin",
        io.StringIO(json.dumps({"last_assistant_message": HEDGING_MESSAGE})),
    )
    with pytest.raises(SystemExit) as exit_info:
        hedging_language_blocker.main()
    assert exit_info.value.code == 0
    assert all_emitted
    matcher_id, surface, context_text = all_emitted[0]
    assert matcher_id == "hedging_word"
    assert surface == "Stop"
    assert "likely" in context_text


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
    assert "verify with sources or prompt the user via AskUserQuestion" in parsed_response["reason"]
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


def test_explicit_unverified_label_in_same_sentence_passes() -> None:
    completed_process = run_hook_with_message(
        "This claim is unverified; the deploy is probably blocked."
    )

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_i_dont_know_label_in_same_sentence_passes() -> None:
    completed_process = run_hook_with_message(
        "I don't know whether the port is probably open."
    )

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_supported_probability_without_hedge_word_passes() -> None:
    completed_process = run_hook_with_message(
        "The suite reports 0.92 precision on the labeled fixture set in "
        "test_prose_matcher_advisory.py."
    )

    assert completed_process.returncode == 0
    assert completed_process.stdout == ""


def test_label_in_one_sentence_does_not_exempt_bare_hedge_in_another() -> None:
    completed_process = run_hook_with_message(
        "This claim is unverified. The deploy is probably blocked."
    )

    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"
    assert "probably" in parsed_response["reason"]
    assert "explicit uncertainty label" in parsed_response["reason"]


def test_bare_probably_still_blocks_with_positive_corrective() -> None:
    completed_process = run_hook_with_message("The deploy is probably blocked.")

    assert completed_process.returncode == 0
    parsed_response = json.loads(completed_process.stdout)
    assert parsed_response["decision"] == "block"
    assert "probably" in parsed_response["reason"]
    assert "label that claim unverified" in parsed_response["reason"]
    assert "AskUserQuestion" in parsed_response["reason"]


def test_find_blocking_hedging_terms_is_sentence_scoped() -> None:
    bare = hedging_language_blocker.find_blocking_hedging_terms(
        "This claim is unverified. The deploy is probably blocked."
    )
    labeled = hedging_language_blocker.find_blocking_hedging_terms(
        "This claim is unverified; the deploy is probably blocked."
    )
    assert bare == ["probably"]
    assert labeled == []
