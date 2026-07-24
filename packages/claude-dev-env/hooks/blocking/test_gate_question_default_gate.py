"""Tests for the gate_question_default_gate PreToolUse hook.

Covers the tight gate trigger (prose holds "gate" and a block word), the
first-option refactor-to-pass requirement, the recommended mark requirement,
and the pass-through for an unrelated question.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

HOOK_SCRIPT_PATH = Path(__file__).parent / "gate_question_default_gate.py"
_HOOKS_DIR = str(Path(__file__).resolve().parent)
_HOOKS_ROOT = str(Path(__file__).resolve().parent.parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)
if _HOOKS_ROOT not in sys.path:
    sys.path.insert(0, _HOOKS_ROOT)

ASK_USER_QUESTION_TOOL_NAME = "AskUserQuestion"
COMPLIANT_FIRST_LABEL = "Refactor to pass the gate (Recommended)"
SKIP_FIRST_LABEL = "Write a skip token so the write goes through"
UNMARKED_REFACTOR_LABEL = "Refactor to pass the gate"
GATE_QUESTION_TEXT = "The gate denied this edit for a CODE_RULES violation. What now?"
UNRELATED_QUESTION_TEXT = "Which colour theme do you want for the dashboard?"


def _load_hook_module() -> ModuleType:
    module_spec = importlib.util.spec_from_file_location(
        "gate_question_default_gate_under_test", HOOK_SCRIPT_PATH
    )
    assert module_spec is not None and module_spec.loader is not None
    loaded_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


hook_module = _load_hook_module()
evaluate = hook_module.evaluate
GATE_QUESTION_DENY_MESSAGE = hook_module.GATE_QUESTION_DENY_MESSAGE


def _ask_user_question_payload(
    question_text: str, all_option_labels: list[str]
) -> dict[str, object]:
    all_options = [{"label": each_label} for each_label in all_option_labels]
    return {
        "tool_name": ASK_USER_QUESTION_TOOL_NAME,
        "tool_input": {"questions": [{"question": question_text, "options": all_options}]},
    }


def test_compliant_gate_question_passes() -> None:
    payload = _ask_user_question_payload(
        GATE_QUESTION_TEXT, [COMPLIANT_FIRST_LABEL, SKIP_FIRST_LABEL]
    )
    assert evaluate(payload) is None


def test_skip_first_choice_is_blocked() -> None:
    payload = _ask_user_question_payload(
        GATE_QUESTION_TEXT, [SKIP_FIRST_LABEL, COMPLIANT_FIRST_LABEL]
    )
    assert evaluate(payload) == GATE_QUESTION_DENY_MESSAGE


def test_missing_recommended_mark_is_blocked() -> None:
    payload = _ask_user_question_payload(
        GATE_QUESTION_TEXT, [UNMARKED_REFACTOR_LABEL, SKIP_FIRST_LABEL]
    )
    assert evaluate(payload) == GATE_QUESTION_DENY_MESSAGE


def test_unrelated_question_passes_untouched() -> None:
    payload = _ask_user_question_payload(UNRELATED_QUESTION_TEXT, ["Ocean blue", "Forest green"])
    assert evaluate(payload) is None


def test_refactor_option_present_but_not_first_is_blocked() -> None:
    payload = _ask_user_question_payload(
        GATE_QUESTION_TEXT, [SKIP_FIRST_LABEL, COMPLIANT_FIRST_LABEL, "Stop"]
    )
    assert evaluate(payload) == GATE_QUESTION_DENY_MESSAGE
