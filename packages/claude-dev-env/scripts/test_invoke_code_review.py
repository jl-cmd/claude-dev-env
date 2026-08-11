"""Specifications for code-review error reporting and review-loop outcomes."""

from __future__ import annotations

from pathlib import Path

import pytest

import invoke_code_review as invoker
from claude_chain_runner import ChainInvocationOutcome
from dev_env_scripts_constants.claude_chain_constants import TERMINAL_STATUS_SERVED
from dev_env_scripts_constants.code_review_constants import (
    ALL_FINDING_SEVERITIES,
    ALL_LOOP_TERMINALS,
    ALL_RETAINED_VERIFICATION_VERDICTS,
    DEFAULT_CODE_REVIEW_EFFORT,
    FINDING_FIELD_SEVERITY,
    FINDING_FIELD_VERDICT,
    PERMISSION_MODE_ACCEPT_EDITS,
    PERMISSION_MODE_BYPASS,
    RESULT_KEY_DRAFT_PRESERVED,
    RESULT_KEY_REVIEWED_HEAD_COUNT,
    RESULT_KEY_SURVIVING_FINDINGS,
    RESULT_KEY_TERMINAL,
    REVIEW_PERMISSION_MODE,
    SEVERITY_BLOCKER,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SEVERITY_NIT,
    TERMINAL_ADVISOR_BLOCKED,
    TERMINAL_CLEAN,
    TERMINAL_NITS_FIXED,
    VERDICT_CONFIRMED,
    VERDICT_PLAUSIBLE,
    VERDICT_REFUTED,
    all_findings_carry_severity_and_verdict,
    encode_review_loop_terminal_result,
    is_nits_only_findings,
    record_reviewed_head,
    resolve_review_loop_terminal,
)


def test_review_arguments_carry_the_permission_mode_this_caller_resolves() -> None:
    """The review command asks for a permission mode the binary accepts here.

    The binary refuses the bypass mode outright for a root caller.
    """
    all_arguments = invoker.build_code_review_arguments(DEFAULT_CODE_REVIEW_EFFORT)

    assert REVIEW_PERMISSION_MODE in all_arguments


def test_the_resolved_permission_mode_is_one_the_binary_knows() -> None:
    assert REVIEW_PERMISSION_MODE in (
        PERMISSION_MODE_ACCEPT_EDITS,
        PERMISSION_MODE_BYPASS,
    )


CHAIN_CONFIG_REMEDY_TEXT: str = (
    "Claude chain config not found at the path this specification names. "
    "Copy the example config there and list your account binaries."
)
HOST_PROFILE_FAILURE_TEXT: str = "session model alias carries no host profile"
MINT_TIMEOUT_SECONDS: int = 1
SERVED_COMMAND_NAME: str = "claude"
REVIEW_BINARY_REFUSAL_TEXT: str = (
    "--dangerously-skip-permissions cannot be used with root privileges"
)
REVIEW_FAILURE_RETURNCODE: int = 1
EMPTY_REVIEW_STDOUT: str = ""
ROOT_USER_ID: int = 0
UNPRIVILEGED_USER_ID: int = 1000


def _serve_a_refusing_binary(
    *_all_positional: object, **_all_keyword: object
) -> ChainInvocationOutcome:
    return ChainInvocationOutcome(
        served_command=SERVED_COMMAND_NAME,
        returncode=REVIEW_FAILURE_RETURNCODE,
        stdout=EMPTY_REVIEW_STDOUT,
        stderr=REVIEW_BINARY_REFUSAL_TEXT,
        attempts=(),
        terminal_status=TERMINAL_STATUS_SERVED,
    )


def test_failed_review_reports_what_the_served_binary_wrote(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A review that a served binary refused names the refusal.

    The binary can decline for reasons the caller must act on, such as a
    permission mode it will not accept. Dropping its words leaves a bare exit
    code without a usable recovery step.
    """
    monkeypatch.setattr(
        invoker, "_run_claude_with_empty_stdin", _serve_a_refusing_binary
    )

    outcome = invoker._run_chain_review(
        working_directory=tmp_path,
        timeout_seconds=MINT_TIMEOUT_SECONDS,
        effort=DEFAULT_CODE_REVIEW_EFFORT,
    )

    captured_streams = capsys.readouterr()
    assert outcome.returncode == REVIEW_FAILURE_RETURNCODE
    assert REVIEW_BINARY_REFUSAL_TEXT in captured_streams.err


HEAD_SHA_ONE: str = "aaa111"
HEAD_SHA_TWO: str = "bbb222"
HEAD_SHA_THREE: str = "ccc333"
HEAD_SHA_FOUR: str = "ddd444"
FINDING_FILE_PATH: str = "pkg/module.py"
FINDING_LINE_NUMBER: int = 12
FINDING_SUMMARY_TEXT: str = "example finding"


def _retained_finding(
    *,
    severity: str,
    verdict: str = VERDICT_CONFIRMED,
) -> dict[str, object]:
    return {
        "file": FINDING_FILE_PATH,
        "line": FINDING_LINE_NUMBER,
        "summary": FINDING_SUMMARY_TEXT,
        FINDING_FIELD_SEVERITY: severity,
        FINDING_FIELD_VERDICT: verdict,
    }


def test_severity_vocabulary_is_the_frozen_five_token_set() -> None:
    assert ALL_FINDING_SEVERITIES == (
        SEVERITY_BLOCKER,
        SEVERITY_HIGH,
        SEVERITY_MEDIUM,
        SEVERITY_LOW,
        SEVERITY_NIT,
    )
    assert ALL_FINDING_SEVERITIES == (
        "blocker",
        "high",
        "medium",
        "low",
        "nit",
    )


def test_loop_terminals_are_the_frozen_three_token_set() -> None:
    assert ALL_LOOP_TERMINALS == (
        TERMINAL_CLEAN,
        TERMINAL_NITS_FIXED,
        TERMINAL_ADVISOR_BLOCKED,
    )


def test_retained_finding_requires_severity_and_verification_verdict() -> None:
    complete_finding = _retained_finding(severity=SEVERITY_HIGH)
    missing_severity = {
        "file": FINDING_FILE_PATH,
        "line": FINDING_LINE_NUMBER,
        FINDING_FIELD_VERDICT: VERDICT_CONFIRMED,
    }
    missing_verdict = {
        "file": FINDING_FILE_PATH,
        "line": FINDING_LINE_NUMBER,
        FINDING_FIELD_SEVERITY: SEVERITY_HIGH,
    }
    refuted_finding = _retained_finding(
        severity=SEVERITY_LOW,
        verdict=VERDICT_REFUTED,
    )

    assert all_findings_carry_severity_and_verdict([complete_finding]) is True
    assert all_findings_carry_severity_and_verdict([missing_severity]) is False
    assert all_findings_carry_severity_and_verdict([missing_verdict]) is False
    assert all_findings_carry_severity_and_verdict([refuted_finding]) is False
    assert VERDICT_CONFIRMED in ALL_RETAINED_VERIFICATION_VERDICTS
    assert VERDICT_PLAUSIBLE in ALL_RETAINED_VERIFICATION_VERDICTS
    assert VERDICT_REFUTED not in ALL_RETAINED_VERIFICATION_VERDICTS


def test_review_of_new_head_increments_reviewed_head_count_once() -> None:
    after_first = record_reviewed_head((), HEAD_SHA_ONE)
    after_same_head = record_reviewed_head(after_first, HEAD_SHA_ONE)
    after_second = record_reviewed_head(after_same_head, HEAD_SHA_TWO)

    assert after_first == (HEAD_SHA_ONE,)
    assert after_same_head == (HEAD_SHA_ONE,)
    assert after_second == (HEAD_SHA_ONE, HEAD_SHA_TWO)
    assert len(after_second) == 2


def test_empty_findings_return_clean() -> None:
    terminal_status = resolve_review_loop_terminal(
        all_findings=(),
        reviewed_head_count=1,
        is_gates_passed=True,
        is_nits_applied=False,
    )

    assert terminal_status == TERMINAL_CLEAN


def test_empty_findings_continue_when_gates_have_not_passed() -> None:
    terminal_status = resolve_review_loop_terminal(
        all_findings=(),
        reviewed_head_count=1,
        is_gates_passed=False,
        is_nits_applied=False,
    )

    assert terminal_status is None


def test_nits_only_round_returns_nits_fixed_after_gates() -> None:
    all_nits = (
        _retained_finding(severity=SEVERITY_NIT),
        _retained_finding(severity=SEVERITY_NIT, verdict=VERDICT_PLAUSIBLE),
    )

    assert is_nits_only_findings(all_nits) is True
    terminal_status = resolve_review_loop_terminal(
        all_findings=all_nits,
        reviewed_head_count=1,
        is_gates_passed=True,
        is_nits_applied=True,
    )

    assert terminal_status == TERMINAL_NITS_FIXED


def test_nits_without_retained_verdict_do_not_return_nits_fixed() -> None:
    severity_only_nit = {
        "file": FINDING_FILE_PATH,
        "line": FINDING_LINE_NUMBER,
        "summary": FINDING_SUMMARY_TEXT,
        FINDING_FIELD_SEVERITY: SEVERITY_NIT,
    }

    assert is_nits_only_findings((severity_only_nit,)) is True
    assert all_findings_carry_severity_and_verdict((severity_only_nit,)) is False
    terminal_status = resolve_review_loop_terminal(
        all_findings=(severity_only_nit,),
        reviewed_head_count=1,
        is_gates_passed=True,
        is_nits_applied=True,
    )

    assert terminal_status is None


def test_open_non_nit_findings_continue_at_any_head_count() -> None:
    all_findings = (
        _retained_finding(severity=SEVERITY_HIGH),
        _retained_finding(severity=SEVERITY_NIT),
    )
    all_heads = record_reviewed_head((), HEAD_SHA_ONE)
    all_heads = record_reviewed_head(all_heads, HEAD_SHA_TWO)
    all_heads = record_reviewed_head(all_heads, HEAD_SHA_THREE)
    all_heads = record_reviewed_head(all_heads, HEAD_SHA_FOUR)

    assert len(all_heads) == 4
    terminal_status = resolve_review_loop_terminal(
        all_findings=all_findings,
        reviewed_head_count=len(all_heads),
        is_gates_passed=True,
        is_nits_applied=False,
    )

    assert terminal_status is None


def test_unclassified_findings_continue_when_advisor_is_reachable() -> None:
    unclassified_finding = {
        "file": FINDING_FILE_PATH,
        "line": FINDING_LINE_NUMBER,
        "summary": FINDING_SUMMARY_TEXT,
        FINDING_FIELD_VERDICT: VERDICT_CONFIRMED,
    }

    terminal_status = resolve_review_loop_terminal(
        all_findings=(unclassified_finding,),
        reviewed_head_count=5,
        is_gates_passed=True,
        is_nits_applied=False,
    )

    assert terminal_status is None


def test_nits_only_returns_nits_fixed_at_any_head_count() -> None:
    all_nits = (_retained_finding(severity=SEVERITY_NIT),)

    terminal_status = resolve_review_loop_terminal(
        all_findings=all_nits,
        reviewed_head_count=5,
        is_gates_passed=True,
        is_nits_applied=True,
    )

    assert terminal_status == TERMINAL_NITS_FIXED


def test_advisor_unreachable_with_unclassified_returns_advisor_blocked() -> None:
    unclassified_finding = {
        "file": FINDING_FILE_PATH,
        "line": FINDING_LINE_NUMBER,
        FINDING_FIELD_VERDICT: VERDICT_CONFIRMED,
    }

    terminal_status = resolve_review_loop_terminal(
        all_findings=(unclassified_finding,),
        reviewed_head_count=1,
        is_gates_passed=False,
        is_nits_applied=False,
        is_advisor_unreachable=True,
    )

    assert terminal_status == TERMINAL_ADVISOR_BLOCKED


def test_terminal_serialization_preserves_draft_and_findings() -> None:
    surviving_finding = _retained_finding(severity=SEVERITY_MEDIUM)
    encoded_payload = encode_review_loop_terminal_result(
        terminal=TERMINAL_ADVISOR_BLOCKED,
        all_surviving_findings=(surviving_finding,),
        reviewed_head_count=4,
        is_draft_preserved=True,
    )

    assert encoded_payload[RESULT_KEY_TERMINAL] == TERMINAL_ADVISOR_BLOCKED
    assert encoded_payload[RESULT_KEY_DRAFT_PRESERVED] is True
    assert encoded_payload[RESULT_KEY_REVIEWED_HEAD_COUNT] == 4
    assert encoded_payload[RESULT_KEY_SURVIVING_FINDINGS] == [surviving_finding]


def test_advisor_blocked_forces_draft_preserved_when_caller_passes_false() -> None:
    surviving_finding = _retained_finding(severity=SEVERITY_HIGH)
    advisor_blocked_payload = encode_review_loop_terminal_result(
        terminal=TERMINAL_ADVISOR_BLOCKED,
        all_surviving_findings=(surviving_finding,),
        reviewed_head_count=1,
        is_draft_preserved=False,
    )
    clean_payload = encode_review_loop_terminal_result(
        terminal=TERMINAL_CLEAN,
        all_surviving_findings=(),
        reviewed_head_count=1,
        is_draft_preserved=False,
    )

    assert advisor_blocked_payload[RESULT_KEY_DRAFT_PRESERVED] is True
    assert clean_payload[RESULT_KEY_DRAFT_PRESERVED] is False


def test_fourth_and_later_heads_are_recorded() -> None:
    all_heads = (HEAD_SHA_ONE, HEAD_SHA_TWO, HEAD_SHA_THREE)
    after_fourth = record_reviewed_head(all_heads, HEAD_SHA_FOUR)

    assert after_fourth == (
        HEAD_SHA_ONE,
        HEAD_SHA_TWO,
        HEAD_SHA_THREE,
        HEAD_SHA_FOUR,
    )
    assert len(after_fourth) == 4


def test_mixed_severities_are_not_nits_only() -> None:
    all_findings = (
        _retained_finding(severity=SEVERITY_NIT),
        _retained_finding(severity=SEVERITY_BLOCKER),
    )

    assert is_nits_only_findings(all_findings) is False
    assert is_nits_only_findings(()) is False
