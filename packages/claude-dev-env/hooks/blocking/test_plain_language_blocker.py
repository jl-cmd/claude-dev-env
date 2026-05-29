"""Tests for the plain_language_blocker PreToolUse hook.

Covers the shared prose scanner (fenced code, inline code, blockquotes, URLs,
file paths), the word-boundary guard, multi-word phrase matching, case
insensitivity, the term -> replacement block message, and both registered
PreToolUse surfaces (AskUserQuestion and Write|Edit on .md targets).
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

HOOK_SCRIPT_PATH = Path(__file__).parent / "plain_language_blocker.py"
_HOOKS_DIR = str(Path(__file__).resolve().parent)
_HOOKS_ROOT = str(Path(__file__).resolve().parent.parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)
if _HOOKS_ROOT not in sys.path:
    sys.path.insert(0, _HOOKS_ROOT)


def _load_hook_module() -> object:
    module_spec = importlib.util.spec_from_file_location(
        "plain_language_blocker_under_test", HOOK_SCRIPT_PATH
    )
    assert module_spec is not None and module_spec.loader is not None
    loaded_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


hook_module = _load_hook_module()
find_banned_terms = hook_module.find_banned_terms
strip_non_prose_regions = hook_module.strip_non_prose_regions
build_block_reason = hook_module.build_block_reason


def _run_hook_with_payload(payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )


def _decision_from(completed: subprocess.CompletedProcess[str]) -> str | None:
    if not completed.stdout:
        return None
    parsed = json.loads(completed.stdout)
    return parsed.get("hookSpecificOutput", {}).get("permissionDecision")


def test_canonical_hook_script_exists_at_expected_path() -> None:
    assert HOOK_SCRIPT_PATH.is_file()


def test_bare_prose_banned_term_is_detected() -> None:
    matched = find_banned_terms("We initiate the worker pool at boot.")
    assert any(each_term == "initiate" for each_term, _replacement in matched)


def test_banned_term_inside_fenced_code_is_exempt() -> None:
    prose = "Start the pool at boot.\n\n```python\nutilize(pool)\n```\n"
    assert find_banned_terms(prose) == []


def test_banned_term_inside_inline_code_is_exempt() -> None:
    prose = "Call the `utilize` helper from the legacy module to migrate."
    assert find_banned_terms(prose) == []


def test_banned_term_inside_blockquote_is_exempt() -> None:
    prose = "> The old guide said to utilize the pool.\n\nUse the pool directly now."
    assert find_banned_terms(prose) == []


def test_banned_term_inside_url_is_exempt() -> None:
    prose = "See https://example.com/initiate-flow for the original write-up."
    assert find_banned_terms(prose) == []


def test_banned_term_inside_file_path_is_exempt() -> None:
    prose = "Edit src/utilize_helpers/initiate.py to wire the new path."
    assert find_banned_terms(prose) == []


def test_word_boundary_guard_does_not_match_substring() -> None:
    assert find_banned_terms("The reinitialize routine reruns the seed.") == []


def test_case_insensitive_match() -> None:
    matched_lower = find_banned_terms("utilize the cache.")
    matched_upper = find_banned_terms("Utilize the cache.")
    assert any(term == "utilize" for term, _ in matched_lower)
    assert any(term == "utilize" for term, _ in matched_upper)


def test_multi_word_phrase_matches_as_unit() -> None:
    matched = find_banned_terms("Run the migration prior to the deploy step.")
    assert any(term == "prior to" for term, _ in matched)


def test_strip_non_prose_regions_removes_code_and_paths() -> None:
    prose = "Use `utilize` and src/initiate.py and https://x.test/utilize here."
    stripped = strip_non_prose_regions(prose)
    assert "utilize" not in stripped
    assert "initiate" not in stripped


def test_block_reason_names_term_and_replacement() -> None:
    reason = build_block_reason([("initiate", "start")])
    assert "initiate" in reason
    assert "start" in reason


def test_ask_user_question_with_banned_term_is_denied() -> None:
    payload = {
        "tool_name": "AskUserQuestion",
        "tool_input": {
            "questions": [
                {
                    "question": "Should we utilize the new allocator now?",
                    "header": "Allocator",
                    "options": [{"label": "Yes", "description": "Switch now."}],
                }
            ]
        },
    }
    completed = _run_hook_with_payload(payload)
    assert _decision_from(completed) == "deny"


def test_ask_user_question_banned_term_in_option_label_is_denied() -> None:
    payload = {
        "tool_name": "AskUserQuestion",
        "tool_input": {
            "questions": [
                {
                    "question": "Which path should we take?",
                    "header": "Path",
                    "options": [{"label": "Utilize the cache", "description": "Go fast."}],
                }
            ]
        },
    }
    completed = _run_hook_with_payload(payload)
    assert _decision_from(completed) == "deny"


def test_clean_ask_user_question_passes_through() -> None:
    payload = {
        "tool_name": "AskUserQuestion",
        "tool_input": {
            "questions": [
                {
                    "question": "Should we switch the allocator now?",
                    "header": "Allocator",
                    "options": [{"label": "Yes", "description": "Switch now."}],
                }
            ]
        },
    }
    completed = _run_hook_with_payload(payload)
    assert _decision_from(completed) is None


def test_write_markdown_with_banned_term_is_denied(tmp_path: Path) -> None:
    target = tmp_path / "notes.md"
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(target),
            "content": "This guide explains how to utilize the new cache layer.",
        },
    }
    completed = _run_hook_with_payload(payload)
    assert _decision_from(completed) == "deny"


def test_write_non_markdown_is_ignored(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": str(target),
            "content": "This guide explains how to utilize the new cache layer.",
        },
    }
    completed = _run_hook_with_payload(payload)
    assert _decision_from(completed) is None


def test_edit_markdown_clean_content_passes_through(tmp_path: Path) -> None:
    target = tmp_path / "notes.md"
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(target),
            "new_string": "This guide explains how to use the new cache layer.",
        },
    }
    completed = _run_hook_with_payload(payload)
    assert _decision_from(completed) is None


def test_multiedit_markdown_with_banned_term_is_denied(tmp_path: Path) -> None:
    target = tmp_path / "notes.md"
    payload = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": str(target),
            "edits": [
                {"old_string": "intro", "new_string": "This section reads cleanly."},
                {"old_string": "body", "new_string": "Then we utilize the new cache."},
            ],
        },
    }
    completed = _run_hook_with_payload(payload)
    assert _decision_from(completed) == "deny"


def test_other_tool_is_ignored() -> None:
    payload = {"tool_name": "Bash", "tool_input": {"command": "echo utilize"}}
    completed = _run_hook_with_payload(payload)
    assert _decision_from(completed) is None


def test_software_allowlisted_term_is_not_flagged() -> None:
    assert find_banned_terms("Run this command to start the worker.") == []


def test_non_allowlisted_formal_term_still_flagged() -> None:
    matched = find_banned_terms("Please utilize the cache now.")
    assert any(term == "utilize" for term, _ in matched)


def test_prose_slash_token_is_not_stripped_as_path() -> None:
    assert "client/server" in strip_non_prose_regions("Use a client/server split here.")


def test_real_file_path_is_still_stripped() -> None:
    assert "initiate" not in strip_non_prose_regions("Edit src/initiate.py to wire it.")
