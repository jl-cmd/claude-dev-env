"""Calibration for the hook prevention and near-neighbor harness.

A control that blocks, a known-bad hook that never blocks, a known-bad hook
that stops the valid neighbor, and a crashing hook each run through the same
route a registered hook takes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hook_cases import CaseResult, first_verdict, run_case
from hook_harness import (
    HookRegistration,
    Sandbox,
    build_payload,
    classify,
    is_matcher_hit,
    load_registrations,
    run_event_chain,
)

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
ALL_FIXTURE_REGISTRATIONS = load_registrations(FIXTURE_ROOT / "hooks" / "hooks.json")
ALL_CALIBRATION_CASES = json.loads(
    (FIXTURE_ROOT / "calibration_cases.json").read_text(encoding="utf-8")
)


def _registration(script_name: str) -> HookRegistration:
    return next(
        each_registration
        for each_registration in ALL_FIXTURE_REGISTRATIONS
        if each_registration.hook_id.endswith(script_name)
    )


def _run_all(script_name: str, tmp_path: Path) -> list[CaseResult]:
    return [
        run_case(
            _registration(script_name),
            each_case,
            FIXTURE_ROOT,
            tmp_path / str(each_index),
        )
        for each_index, each_case in enumerate(ALL_CALIBRATION_CASES)
    ]


@pytest.mark.parametrize("script_name", ["control_blocker.py", "exit_two_blocker.py"])
def test_should_pass_a_control_that_blocks_and_lets_the_neighbor_through(
    script_name: str, tmp_path: Path
) -> None:
    all_results = _run_all(script_name, tmp_path)
    verdict, all_reasons = first_verdict(all_results)
    assert [each_result.run.outcome for each_result in all_results] == [
        "block",
        "silent",
        "silent",
        "silent",
    ]
    assert (verdict, all_reasons) == ("works", [])


def test_should_flag_a_hook_that_never_blocks_its_claimed_input(tmp_path: Path) -> None:
    verdict, all_reasons = first_verdict(_run_all("never_blocks.py", tmp_path))
    assert verdict == "inactive/broken"
    assert all_reasons == ["prohibited: expected block, observed silent []"]


def test_should_flag_a_hook_that_blocks_the_valid_near_neighbor(tmp_path: Path) -> None:
    verdict, all_reasons = first_verdict(_run_all("overblocker.py", tmp_path))
    assert verdict == "inactive/broken"
    assert "near_neighbor: expected silent, observed block []" in all_reasons


def test_should_report_a_crashing_hook_as_a_harness_visible_failure(
    tmp_path: Path,
) -> None:
    all_results = _run_all("crashing.py", tmp_path)
    verdict, all_reasons = first_verdict(all_results)
    assert {each_result.run.outcome for each_result in all_results} == {
        "harness_failure"
    }
    assert all_results[0].run.exit_code == 1
    assert "calibration crash" in all_results[0].run.stderr
    assert verdict == "inactive/broken"
    assert all_reasons[0] == "prohibited: harness-visible failure exit=1"


def test_should_report_a_timeout_as_a_harness_visible_failure(tmp_path: Path) -> None:
    slow_registration = HookRegistration(
        event="PreToolUse", matcher="Bash", command="sleep 5", timeout_seconds=0.5
    )
    result = run_case(
        slow_registration, ALL_CALIBRATION_CASES[0], FIXTURE_ROOT, tmp_path
    )
    assert result.run.is_timed_out
    assert result.run.outcome == "harness_failure"


def test_should_flag_a_matcher_that_never_selects_the_claimed_input(
    tmp_path: Path,
) -> None:
    control = _registration("control_blocker.py")
    mismatched = HookRegistration("PreToolUse", "NoSuchTool", control.command, 20)
    verdict, all_reasons = first_verdict(
        [run_case(mismatched, ALL_CALIBRATION_CASES[0], FIXTURE_ROOT, tmp_path)]
    )
    assert verdict == "inactive/broken"
    assert all_reasons == [
        "prohibited: registered matcher never selects the claimed input"
    ]


def test_should_find_redundancy_only_when_another_hook_still_blocks(
    tmp_path: Path,
) -> None:
    sandbox = Sandbox(tmp_path)
    payload = build_payload("PreToolUse", sandbox, ALL_CALIBRATION_CASES[0]["payload"])
    all_blockers = [
        _registration("control_blocker.py"),
        _registration("exit_two_blocker.py"),
    ]
    control_id = all_blockers[0].hook_id
    assert (
        run_event_chain(all_blockers, payload, FIXTURE_ROOT, sandbox, control_id)
        == "block"
    )
    assert (
        run_event_chain(all_blockers[:1], payload, FIXTURE_ROOT, sandbox, control_id)
        == "silent"
    )


@pytest.mark.parametrize(
    ("matcher", "tool_name", "is_expected_hit"),
    [
        ("", "Bash", True),
        ("*", "Bash", True),
        ("Write|Edit", "Edit", True),
        ("Write, Edit", "Edit", True),
        ("Write|Edit", "MultiEdit", False),
        ("Edit.*", "NotebookEdit", True),
        ("^Edit$", "NotebookEdit", False),
    ],
)
def test_should_evaluate_matchers_as_the_hooks_reference_states(
    matcher: str, tool_name: str, is_expected_hit: bool, tmp_path: Path
) -> None:
    payload = build_payload("PreToolUse", Sandbox(tmp_path), {"tool_name": tool_name})
    registration = HookRegistration("PreToolUse", matcher, "unused", 1)
    assert is_matcher_hit(registration, payload) is is_expected_hit


@pytest.mark.parametrize(
    ("event", "exit_code", "stdout", "expected_outcome"),
    [
        ("PreToolUse", 2, "", "block"),
        ("PostToolUse", 2, "", "advise"),
        ("SessionEnd", 2, "", "harness_failure"),
        ("PreToolUse", 1, "", "harness_failure"),
        ("SessionStart", 0, "plain context", "advise"),
        ("PreToolUse", 0, "plain text", "silent"),
        ("SessionEnd", 0, '{"systemMessage": "x"}', "silent"),
        ("PostToolUse", 0, '{"decision": "block", "reason": "x"}', "block"),
        (
            "PreToolUse",
            0,
            '{"hookSpecificOutput": {"permissionDecision": "allow", "updatedInput": {}}}',
            "rewrite",
        ),
        (
            "PreToolUse",
            0,
            '{"hookSpecificOutput": {"permissionDecision": "ask"}}',
            "ask",
        ),
        (
            "SessionStart",
            0,
            '{"hookSpecificOutput": {"additionalContext": "abc"}}',
            "advise",
        ),
    ],
)
def test_should_classify_output_as_the_hooks_reference_states(
    event: str, exit_code: int, stdout: str, expected_outcome: str
) -> None:
    assert classify(event, exit_code, stdout, False)[0] == expected_outcome


def test_should_count_injected_context_characters() -> None:
    stdout = json.dumps({"hookSpecificOutput": {"additionalContext": "12345"}})
    assert classify("SessionStart", 0, stdout, False)[2] == 5
