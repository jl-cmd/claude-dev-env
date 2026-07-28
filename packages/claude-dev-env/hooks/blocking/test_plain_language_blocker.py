"""Tests for the plain_language_blocker PreToolUse hook.

Covers the shared prose scanner (fenced code, inline code, blockquotes, URLs,
file paths), the word-boundary guard, multi-word phrase matching, case
insensitivity, the term -> replacement block message, both registered
PreToolUse surfaces (AskUserQuestion and Write|Edit on .md targets), and the
lean-question-block check that keeps chat detail out of an AskUserQuestion call.
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

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
find_question_block_violations = hook_module.find_question_block_violations
build_lean_block_reason = hook_module.build_lean_block_reason
evaluate = hook_module.evaluate

from pre_tool_use_dispatcher import NativeHook, run_native_hook  # noqa: E402


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


def test_write_markdown_at_ephemeral_path_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", raising=False)
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/tmp/notes.md",
            "content": "This guide explains how to utilize the new cache layer.",
        },
    }
    completed = _run_hook_with_payload(payload)
    assert _decision_from(completed) is None


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


def test_native_dispatch_path_logs_the_block(tmp_path: Path) -> None:
    """A deny routed through the dispatcher's native path logs one record.

    On the Write|Edit|MultiEdit surface this hook runs only through
    pre_tool_use_dispatcher's native path, which calls evaluate() and
    build_deny_payload() — never _emit_deny() or main(). The block must still
    land in the hook-blocks log, so the log call lives on build_deny_payload,
    the function the native path executes.
    """
    deny_payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(tmp_path / "notes.md"),
            "new_string": "This guide explains how to utilize the new cache layer.",
        },
    }
    native_hook = NativeHook(
        evaluate=hook_module.evaluate,
        build_deny_payload=hook_module.build_deny_payload,
    )

    with patch.object(Path, "home", return_value=tmp_path):
        hosted_result = run_native_hook(native_hook, deny_payload, is_blocking=True)

    assert hosted_result.captured_stdout
    log_path = tmp_path / ".claude" / "logs" / "hook-blocks.log"
    all_records = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(all_records) == 1
    logged_record = json.loads(all_records[0])
    assert logged_record["hook"] == "plain_language_blocker.py"
    assert logged_record["event"] == "PreToolUse"


LEAN_QUESTION = "Which gate should run first?"
LEAN_DESCRIPTION = "Runs on every write."
QUESTION_AT_THE_WORD_CAP = (
    "Should we keep the gate on the write path where it reads the whole file "
    "each time, or move it to the commit path where it reads only the lines "
    "that a change has already staged for the current review?"
)
QUESTION_OVER_THE_WORD_CAP = (
    "Should we keep the gate on the write path where it reads the whole file "
    "each time it runs, or move the gate to the commit path where it reads "
    "only the staged lines and skips the files that no one on the team ever "
    "touched?"
)
DESCRIPTION_AT_THE_WORD_CAP = (
    "Runs the gate at commit time so it reads only the lines a change staged."
)
DESCRIPTION_OVER_THE_WORD_CAP = (
    "Runs the gate at commit time so it reads only the lines the change "
    "actually staged for review."
)
QUESTION_WITH_INLINE_CODE_AT_THE_WORD_CAP = (
    "Should we keep the gate on the write path where it reads the whole file "
    "each time, or move it to the commit path where it reads only what "
    "`git diff --cached --name-only HEAD` lists for the current review before "
    "the team sees it?"
)
QUESTION_WITH_INLINE_CODE_OVER_THE_WORD_CAP = (
    "Should we keep the gate on the write path where it reads the whole file "
    "each time, or move it to the commit path where it reads only what "
    "`git diff --cached --name-only HEAD` lists for the current review before "
    "the whole team sees it?"
)
DESCRIPTION_WITH_INLINE_CODE_AT_THE_WORD_CAP = (
    "Runs the gate at commit time so it reads only what "
    "`git diff --cached --name-only HEAD` lists for review."
)
DESCRIPTION_WITH_INLINE_CODE_OVER_THE_WORD_CAP = (
    "Runs the gate at commit time so it reads only what "
    "`git diff --cached --name-only HEAD` lists for the review."
)


def _ask_payload(question_text: str, all_descriptions: list[str]) -> dict[str, object]:
    return {
        "tool_name": "AskUserQuestion",
        "tool_input": {
            "questions": [
                {
                    "question": question_text,
                    "header": "Gate",
                    "options": [
                        {"label": f"Gate {each_index}", "description": each_description}
                        for each_index, each_description in enumerate(all_descriptions)
                    ],
                }
            ]
        },
    }


def test_question_carrying_a_list_marker_plan_is_denied() -> None:
    plan_question = f"{LEAN_QUESTION}\n- Split the file\n- Wire the gate\n- Run the suite"

    deny_reason = evaluate(_ask_payload(plan_question, [LEAN_DESCRIPTION]))

    assert deny_reason is not None
    assert "a bullet or numbered list marker" in deny_reason


def test_question_carrying_a_fenced_block_is_denied() -> None:
    fenced_question = f"{LEAN_QUESTION}\n```\nrun_gate()\n```"

    deny_reason = evaluate(_ask_payload(fenced_question, [LEAN_DESCRIPTION]))

    assert deny_reason is not None
    assert "a fenced code block" in deny_reason


def test_question_carrying_a_second_paragraph_is_denied() -> None:
    two_paragraph_question = f"{LEAN_QUESTION}\n\nThe write gate reads every file."

    deny_reason = evaluate(_ask_payload(two_paragraph_question, [LEAN_DESCRIPTION]))

    assert deny_reason is not None
    assert "more than one paragraph" in deny_reason


def test_question_carrying_a_heading_is_denied() -> None:
    headed_question = f"{LEAN_QUESTION}\n## The write gate\nIt reads every file."

    deny_reason = evaluate(_ask_payload(headed_question, [LEAN_DESCRIPTION]))

    assert deny_reason is not None
    assert "a heading" in deny_reason


def test_option_description_carrying_a_table_row_is_denied() -> None:
    deny_reason = evaluate(_ask_payload(LEAN_QUESTION, ["| gate | 12 ms |"]))

    assert deny_reason is not None
    assert "a table row" in deny_reason


def test_question_over_the_word_cap_is_denied() -> None:
    deny_reason = evaluate(_ask_payload(QUESTION_OVER_THE_WORD_CAP, [LEAN_DESCRIPTION]))

    assert deny_reason is not None
    assert "46 words, over the 40-word cap" in deny_reason


def test_question_over_the_sentence_cap_is_denied() -> None:
    three_sentence_question = (
        "Which gate runs first? The write gate reads every file. "
        "The commit gate reads staged lines only."
    )

    deny_reason = evaluate(_ask_payload(three_sentence_question, [LEAN_DESCRIPTION]))

    assert deny_reason is not None
    assert "3 sentences, over the 2-sentence cap" in deny_reason


def test_option_description_over_the_word_cap_is_denied() -> None:
    deny_reason = evaluate(_ask_payload(LEAN_QUESTION, [DESCRIPTION_OVER_THE_WORD_CAP]))

    assert deny_reason is not None
    assert "18 words, over the 15-word cap" in deny_reason


def test_option_description_over_the_sentence_cap_is_denied() -> None:
    deny_reason = evaluate(_ask_payload(LEAN_QUESTION, ["Runs on write. Reads every file."]))

    assert deny_reason is not None
    assert "2 sentences, over the 1-sentence cap" in deny_reason


def test_lean_question_with_three_short_options_is_allowed() -> None:
    all_descriptions = [
        LEAN_DESCRIPTION,
        "Runs at commit time.",
        "Runs in both places.",
    ]

    assert evaluate(_ask_payload(LEAN_QUESTION, all_descriptions)) is None


def test_two_sentence_question_at_the_sentence_cap_is_allowed() -> None:
    two_sentence_question = f"{LEAN_QUESTION} Both gates read the same lines."

    assert evaluate(_ask_payload(two_sentence_question, [LEAN_DESCRIPTION])) is None


def test_question_at_the_word_cap_is_allowed() -> None:
    assert evaluate(_ask_payload(QUESTION_AT_THE_WORD_CAP, [LEAN_DESCRIPTION])) is None


def test_option_description_at_the_word_cap_is_allowed() -> None:
    assert evaluate(_ask_payload(LEAN_QUESTION, [DESCRIPTION_AT_THE_WORD_CAP])) is None


def test_question_with_an_inline_code_span_is_allowed() -> None:
    question_text = QUESTION_WITH_INLINE_CODE_AT_THE_WORD_CAP

    assert len(question_text.split()) > 40
    assert evaluate(_ask_payload(question_text, [LEAN_DESCRIPTION])) is None


def test_inline_code_span_counts_as_one_word() -> None:
    deny_reason = evaluate(
        _ask_payload(QUESTION_WITH_INLINE_CODE_OVER_THE_WORD_CAP, [LEAN_DESCRIPTION])
    )

    assert deny_reason is not None
    assert "41 words, over the 40-word cap" in deny_reason


def test_option_description_with_an_inline_code_span_is_allowed() -> None:
    option_description = DESCRIPTION_WITH_INLINE_CODE_AT_THE_WORD_CAP

    assert len(option_description.split()) > 15
    assert evaluate(_ask_payload(LEAN_QUESTION, [option_description])) is None


def test_inline_code_span_counts_as_one_word_in_an_option_description() -> None:
    deny_reason = evaluate(
        _ask_payload(LEAN_QUESTION, [DESCRIPTION_WITH_INLINE_CODE_OVER_THE_WORD_CAP])
    )

    assert deny_reason is not None
    assert "16 words, over the 15-word cap" in deny_reason


def test_markdown_write_keeps_its_bullets_and_tables(tmp_path: Path) -> None:
    bulleted_prose = "- Split the file\n- Wire the gate\n\n| gate | 12 ms |\n"
    target_path = str(tmp_path / "notes.md")
    heavy_payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": target_path,
            "content": f"{bulleted_prose}Then utilize the cache.",
        },
    }
    clean_payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": target_path, "content": bulleted_prose},
    }

    assert evaluate(heavy_payload) is not None
    assert evaluate(clean_payload) is None


def test_find_question_block_violations_reports_one_line_per_repeated_fault() -> None:
    tool_input = {
        "questions": [
            {
                "question": LEAN_QUESTION,
                "options": [
                    {"label": "Write", "description": DESCRIPTION_OVER_THE_WORD_CAP},
                    {"label": "Commit", "description": DESCRIPTION_OVER_THE_WORD_CAP},
                ],
            }
        ]
    }

    all_violations = find_question_block_violations(tool_input)

    assert all_violations == [
        "an option description runs 18 words, over the 15-word cap"
    ]


def test_lean_block_reason_names_the_fault_and_the_fix() -> None:
    reason = build_lean_block_reason(["the question carries a table row"])

    assert "the question carries a table row" in reason
    assert "in chat text" in reason


def test_each_denial_carries_its_own_user_notice() -> None:
    plan_question = f"{LEAN_QUESTION}\n- Split the file\n- Wire the gate"
    lean_denial = _run_hook_with_payload(_ask_payload(plan_question, [LEAN_DESCRIPTION]))
    heavy_denial = _run_hook_with_payload(
        _ask_payload("Should we utilize the cache?", [LEAN_DESCRIPTION])
    )

    lean_notice = json.loads(lean_denial.stdout)["systemMessage"]
    heavy_notice = json.loads(heavy_denial.stdout)["systemMessage"]

    assert "question" in lean_notice.lower()
    assert "word" in heavy_notice.lower()
    assert lean_notice != heavy_notice
