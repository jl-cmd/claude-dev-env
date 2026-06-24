"""Tests for convergence_summary.build_summary_prompt."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import convergence_summary


SAMPLE_FINDINGS = [
    {
        "severity": "P0",
        "category": "bug",
        "file": "hooks/blocking/destructive_command_blocker.py",
        "line": 42,
        "title": "launcher-wrapped delete runs with no prompt",
        "detail": "timeout 5 bash -c 'rm -rf /etc' bypasses the confirmation gate.",
    },
    {
        "severity": "P2",
        "category": "code-standard",
        "file": "hooks/blocking/destructive_command_blocker.py",
        "line": 9,
        "title": "comment claims a refusal the code does not perform",
        "detail": "",
    },
]


def test_prompt_carries_pr_coordinates_and_round_count() -> None:
    """Should name the PR coordinates and the aggregated round count."""
    prompt = convergence_summary.build_summary_prompt(
        owner="jl-cmd",
        repo="claude-code-config",
        pr_number=581,
        round_count=39,
        findings=SAMPLE_FINDINGS,
        fix_summaries=["renamed and annotated", "guarded the launcher"],
        standards_note=None,
        copilot_note=None,
    )

    assert "owner=jl-cmd repo=claude-code-config PR #581" in prompt
    assert "https://github.com/jl-cmd/claude-code-config/pull/581" in prompt
    assert "convergence in 39 round(s)" in prompt
    assert "gh api repos/jl-cmd/claude-code-config/pulls/581" in prompt


def test_prompt_instructs_plain_json_object_not_structured_output() -> None:
    """Should instruct a plain JSON object answer and never name the StructuredOutput tool."""
    prompt = convergence_summary.build_summary_prompt(
        owner="jl-cmd",
        repo="claude-code-config",
        pr_number=581,
        round_count=39,
        findings=SAMPLE_FINDINGS,
        fix_summaries=[],
        standards_note=None,
        copilot_note=None,
    )

    assert "StructuredOutput" not in prompt
    assert "Return strictly a JSON object with keys" in prompt


def test_prompt_numbers_every_finding_with_severity_and_location() -> None:
    """Should list each aggregated finding numbered with severity, file, and line."""
    prompt = convergence_summary.build_summary_prompt(
        owner="jl-cmd",
        repo="claude-code-config",
        pr_number=581,
        round_count=39,
        findings=SAMPLE_FINDINGS,
        fix_summaries=[],
        standards_note=None,
        copilot_note=None,
    )

    assert (
        "1. [P0/bug] hooks/blocking/destructive_command_blocker.py:42 - "
        "launcher-wrapped delete runs with no prompt" in prompt
    )
    assert "2. [P2/code-standard]" in prompt
    assert "Per-round fix summaries:\nnone" in prompt


def test_prompt_carries_notes_when_present() -> None:
    """Should include the standards and copilot notes only when they are given."""
    with_notes = convergence_summary.build_summary_prompt(
        owner="o",
        repo="r",
        pr_number=1,
        round_count=2,
        findings=[],
        fix_summaries=[],
        standards_note="round 2 deferred a magic-value class",
        copilot_note="Copilot out of quota",
    )
    without_notes = convergence_summary.build_summary_prompt(
        owner="o",
        repo="r",
        pr_number=1,
        round_count=2,
        findings=[],
        fix_summaries=[],
        standards_note=None,
        copilot_note=None,
    )

    assert "Deferred code-standard note: round 2 deferred a magic-value class" in (
        with_notes
    )
    assert "Copilot gate note: Copilot out of quota" in with_notes
    assert "Deferred code-standard note:" not in without_notes
    assert "Copilot gate note:" not in without_notes


def test_prompt_imposes_no_issue_class_cap() -> None:
    """Should instruct one class per distinct kind with no fixed class ceiling."""
    prompt = convergence_summary.build_summary_prompt(
        owner="o",
        repo="r",
        pr_number=1,
        round_count=1,
        findings=[],
        fix_summaries=[],
        standards_note=None,
        copilot_note=None,
    )

    assert "Cap to about 5 classes" not in prompt
    assert "one class per distinct KIND of problem" in prompt


def test_empty_findings_state_clean_run() -> None:
    """Should render the clean-run sentence when no findings were caught."""
    prompt = convergence_summary.build_summary_prompt(
        owner="o",
        repo="r",
        pr_number=1,
        round_count=1,
        findings=[],
        fix_summaries=[],
        standards_note=None,
        copilot_note=None,
    )

    assert "none - every lens was clean on a stable HEAD" in prompt
