"""Tests for docstring_rule_gate_count_blocker hook."""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from docstring_rule_gate_count_blocker import (
    find_gate_count_drift,
    is_target_rule_file,
)

from hooks_constants.docstring_rule_gate_count_blocker_constants import (
    GATE_COUNT_SYSTEM_MESSAGE,
    TARGET_RULE_BASENAME,
)

HOOK_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "docstring_rule_gate_count_blocker.py")

IN_STEP_RULE_TEXT = (
    "The gate validator `check_docstring_args_match_signature` covers the Args "
    "section parameter names. Four more gate validators each cover one "
    "deterministic slice of the free-form prose. `check_docstring_fallback_branch_coverage` "
    "covers a fallback. `check_class_docstring_names_public_methods` covers a "
    "class. `check_docstring_no_consumer_claim` covers a producer. "
    "`check_docstring_unguarded_malformed_payload_claim` covers a malformed "
    "payload. The audit lane covers everything outside the five gated slices.\n"
)

STALE_FREE_FORM_COUNT_RULE_TEXT = (
    "The gate validator `check_docstring_args_match_signature` covers the Args "
    "section parameter names. Three more gate validators each cover one "
    "deterministic slice of the free-form prose. `check_docstring_fallback_branch_coverage` "
    "covers a fallback. `check_class_docstring_names_public_methods` covers a "
    "class. `check_docstring_no_consumer_claim` covers a producer. "
    "`check_docstring_unguarded_malformed_payload_claim` covers a malformed "
    "payload. The audit lane covers everything outside the four gated slices.\n"
)

THREE_VALIDATORS_IN_STEP_RULE_TEXT = (
    "The gate validator `check_docstring_args_match_signature` covers the Args "
    "section parameter names. Three more gate validators each cover one "
    "deterministic slice of the free-form prose. `check_docstring_fallback_branch_coverage` "
    "covers a fallback. `check_class_docstring_names_public_methods` covers a "
    "class. `check_docstring_no_consumer_claim` covers a producer. The audit lane "
    "covers everything outside the four gated slices.\n"
)

FENCED_COUNT_CLAUSE_RULE_TEXT = (
    "This rule names no live count outside a fence.\n\n"
    "```\n"
    "Three more gate validators each cover a slice: "
    "`check_docstring_fallback_branch_coverage`, "
    "`check_class_docstring_names_public_methods`. The four gated slices.\n"
    "```\n"
)

NO_COUNT_CLAUSE_RULE_TEXT = (
    "This rule prose names `check_docstring_fallback_branch_coverage` and "
    "`check_class_docstring_names_public_methods` but states no spelled-out "
    "gate count or gated-slice total.\n"
)

OUT_OF_WINDOW_VALIDATOR_RULE_TEXT = (
    "The gate validator `check_docstring_args_match_signature` covers the Args "
    "section parameter names. Three more gate validators each cover one "
    "deterministic slice of the free-form prose. `check_docstring_fallback_branch_coverage` "
    "covers a fallback. `check_class_docstring_names_public_methods` covers a "
    "class. `check_docstring_no_consumer_claim` covers a producer. The audit lane "
    "covers everything outside the four gated slices. The worked example below "
    "also names `check_docstring_step_enumeration_dispatch_coverage`, which the "
    "enforcement section discusses but the count clause does not enumerate.\n"
)


class _RunHook:
    """Helper to drive the hook via subprocess, mirroring the sibling test style."""

    def __call__(self, tool_name: str, tool_input: dict) -> subprocess.CompletedProcess:
        payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        return subprocess.run(
            [sys.executable, HOOK_SCRIPT_PATH],
            input=payload,
            capture_output=True,
            text=True,
            check=False,
        )


_run_hook = _RunHook()


def _target_rule_path(tmp_path: Path) -> Path:
    """Return a path inside *tmp_path* named after the guarded rule basename."""
    return tmp_path / TARGET_RULE_BASENAME


def should_flag_target_rule_basename() -> None:
    assert is_target_rule_file("/somewhere/" + TARGET_RULE_BASENAME) is True


def should_ignore_unrelated_markdown_file() -> None:
    assert is_target_rule_file("/somewhere/other-rule.md") is False


def should_report_no_drift_when_counts_match_named_validators() -> None:
    assert find_gate_count_drift(IN_STEP_RULE_TEXT) == []


def should_report_no_drift_for_three_validators_in_step() -> None:
    assert find_gate_count_drift(THREE_VALIDATORS_IN_STEP_RULE_TEXT) == []


def should_flag_stale_free_form_count_after_a_validator_is_added() -> None:
    issues = find_gate_count_drift(STALE_FREE_FORM_COUNT_RULE_TEXT)
    assert len(issues) == 2
    assert any("Three more gate validators" in each_issue for each_issue in issues)
    assert any("four gated slices" in each_issue for each_issue in issues)


def should_ignore_count_clauses_inside_a_code_fence() -> None:
    assert find_gate_count_drift(FENCED_COUNT_CLAUSE_RULE_TEXT) == []


def should_report_no_drift_when_no_count_clause_is_present() -> None:
    assert find_gate_count_drift(NO_COUNT_CLAUSE_RULE_TEXT) == []


def should_exclude_validators_named_outside_the_enumeration_window() -> None:
    assert find_gate_count_drift(OUT_OF_WINDOW_VALIDATOR_RULE_TEXT) == []


def should_deny_a_write_with_a_stale_gate_count() -> None:
    completed = _run_hook(
        "Write",
        {
            "file_path": "/anywhere/" + TARGET_RULE_BASENAME,
            "content": STALE_FREE_FORM_COUNT_RULE_TEXT,
        },
    )
    parsed_output = json.loads(completed.stdout)
    hook_specific = parsed_output["hookSpecificOutput"]
    assert hook_specific["permissionDecision"] == "deny"
    assert parsed_output["systemMessage"] == GATE_COUNT_SYSTEM_MESSAGE


def should_allow_a_write_with_in_step_counts() -> None:
    completed = _run_hook(
        "Write",
        {"file_path": "/anywhere/" + TARGET_RULE_BASENAME, "content": IN_STEP_RULE_TEXT},
    )
    assert completed.stdout.strip() == ""


def should_allow_a_write_to_an_unrelated_markdown_file() -> None:
    completed = _run_hook(
        "Write",
        {"file_path": "/anywhere/other-rule.md", "content": STALE_FREE_FORM_COUNT_RULE_TEXT},
    )
    assert completed.stdout.strip() == ""


def should_deny_an_edit_that_makes_the_count_stale(tmp_path: Path) -> None:
    rule_path = _target_rule_path(tmp_path)
    rule_path.write_text(IN_STEP_RULE_TEXT, encoding="utf-8")
    completed = _run_hook(
        "Edit",
        {
            "file_path": str(rule_path),
            "old_string": "Four more gate validators",
            "new_string": "Three more gate validators",
        },
    )
    parsed_output = json.loads(completed.stdout)
    assert parsed_output["hookSpecificOutput"]["permissionDecision"] == "deny"


def should_allow_an_edit_that_keeps_the_count_in_step(tmp_path: Path) -> None:
    rule_path = _target_rule_path(tmp_path)
    rule_path.write_text(IN_STEP_RULE_TEXT, encoding="utf-8")
    completed = _run_hook(
        "Edit",
        {
            "file_path": str(rule_path),
            "old_string": "covers a malformed payload.",
            "new_string": "covers a malformed payload case.",
        },
    )
    assert completed.stdout.strip() == ""
