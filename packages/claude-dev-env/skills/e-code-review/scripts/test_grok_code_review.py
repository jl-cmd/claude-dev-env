"""Behavioral tests for Grok medium-review discovery and verification."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from config.grok_code_review_constants import (  # noqa: E402
    ALL_MEDIUM_FINDER_ANGLES,
    MEDIUM_REVIEW_FINDER_COUNT,
    VERDICT_CONFIRMED,
    VERDICT_PLAUSIBLE,
    VERDICT_REFUTED,
)
from grok_code_review import (  # noqa: E402
    FinderCandidate,
    deduplicate_candidates,
    require_exact_finder_set,
    retain_verified_findings,
    run_medium_review,
)


def _candidate(
    angle: str,
    *,
    file_path: str = "a.py",
    line_number: int = 1,
    mechanism: str = "m",
    scenario: str = "short",
    suffix: str = "",
    head: str = "head1",
) -> FinderCandidate:
    token = suffix or angle
    return FinderCandidate(
        angle=angle,
        file_path=file_path,
        line_number=line_number,
        mechanism=mechanism,
        scenario=scenario,
        worktree_path=f"/wt/{token}",
        leader_socket=f"sock-{token}",
        advisor_session_id=f"adv-{token}",
        reviewed_head=head,
    )


def test_require_exact_finder_set_accepts_all_angles() -> None:
    require_exact_finder_set(ALL_MEDIUM_FINDER_ANGLES)
    with pytest.raises(ValueError):
        require_exact_finder_set(ALL_MEDIUM_FINDER_ANGLES[:-1])


def test_deduplicate_keeps_most_concrete_scenario() -> None:
    short = _candidate("correctness", scenario="short")
    long = _candidate("security", scenario="much more concrete failure path")
    # same key different angles - force same file/line/mech
    short = FinderCandidate(
        angle="correctness",
        file_path="a.py",
        line_number=3,
        mechanism="null",
        scenario="x",
        worktree_path="/wt/a",
        leader_socket="s1",
        advisor_session_id="a1",
        reviewed_head="h",
    )
    long = FinderCandidate(
        angle="security",
        file_path="a.py",
        line_number=3,
        mechanism="null",
        scenario="concrete long scenario",
        worktree_path="/wt/b",
        leader_socket="s2",
        advisor_session_id="a2",
        reviewed_head="h",
    )
    kept = deduplicate_candidates([short, long])
    assert len(kept) == 1
    assert kept[0].scenario == "concrete long scenario"


def test_run_medium_review_happy_path() -> None:
    head = "abc123"
    all_finders = [
        _candidate(each_angle, head=head, suffix=each_angle)
        for each_angle in ALL_MEDIUM_FINDER_ANGLES
    ]
    # make unique keys per angle
    all_finders = [
        FinderCandidate(
            angle=each_angle,
            file_path=f"{each_angle}.py",
            line_number=1,
            mechanism="m",
            scenario=f"scenario {each_angle}",
            worktree_path=f"/wt/{each_angle}",
            leader_socket=f"sock-{each_angle}",
            advisor_session_id=f"adv-{each_angle}",
            reviewed_head=head,
        )
        for each_angle in ALL_MEDIUM_FINDER_ANGLES
    ]
    verdicts = {
        (f"{each}.py", 1, "m"): VERDICT_CONFIRMED
        for each in ALL_MEDIUM_FINDER_ANGLES
    }
    severities = {
        (f"{each}.py", 1, "m"): "medium" for each in ALL_MEDIUM_FINDER_ANGLES
    }
    # refute one
    first = ALL_MEDIUM_FINDER_ANGLES[0]
    verdicts[(f"{first}.py", 1, "m")] = VERDICT_REFUTED
    batch = run_medium_review(
        target_head=head,
        diff_base="base",
        all_finder_candidates=all_finders,
        verdict_by_key=verdicts,
        severity_by_key=severities,
        live_head=head,
    )
    assert batch.is_rejected is False
    assert len(batch.all_finder_angles) == MEDIUM_REVIEW_FINDER_COUNT
    assert all(each.reviewed_head == head for each in batch.all_retained_findings)
    assert all(each.verdict in {VERDICT_CONFIRMED, VERDICT_PLAUSIBLE} for each in batch.all_retained_findings)
    assert len(batch.all_retained_findings) == MEDIUM_REVIEW_FINDER_COUNT - 1


def test_head_drift_rejects_batch() -> None:
    head = "h1"
    all_finders = [
        FinderCandidate(
            angle=each_angle,
            file_path=f"{each_angle}.py",
            line_number=1,
            mechanism="m",
            scenario="s",
            worktree_path=f"/wt/{each_angle}",
            leader_socket=f"sock-{each_angle}",
            advisor_session_id=f"adv-{each_angle}",
            reviewed_head=head,
        )
        for each_angle in ALL_MEDIUM_FINDER_ANGLES
    ]
    batch = run_medium_review(
        target_head=head,
        diff_base="b",
        all_finder_candidates=all_finders,
        verdict_by_key={},
        severity_by_key={},
        live_head="other",
    )
    assert batch.is_rejected is True
    assert batch.rejection_reason == "head_drift"


def test_advisor_blocked_rejects_batch() -> None:
    head = "h1"
    all_finders = [
        FinderCandidate(
            angle=each_angle,
            file_path=f"{each_angle}.py",
            line_number=1,
            mechanism="m",
            scenario="s",
            worktree_path=f"/wt/{each_angle}",
            leader_socket=f"sock-{each_angle}",
            advisor_session_id=f"adv-{each_angle}",
            reviewed_head=head,
        )
        for each_angle in ALL_MEDIUM_FINDER_ANGLES
    ]
    batch = run_medium_review(
        target_head=head,
        diff_base="b",
        all_finder_candidates=all_finders,
        verdict_by_key={},
        severity_by_key={},
        live_head=head,
        is_any_advisor_blocked=True,
    )
    assert batch.is_rejected is True
    assert batch.rejection_reason == "advisor_blocked"


def test_retain_verified_findings_keeps_confirmed() -> None:
    candidate = FinderCandidate(
        angle="correctness",
        file_path="a.py",
        line_number=2,
        mechanism="null",
        scenario="boom",
        worktree_path="/wt/x",
        leader_socket="s",
        advisor_session_id="a",
        reviewed_head="h",
    )
    kept = retain_verified_findings(
        all_candidates=[candidate],
        verdict_by_key={("a.py", 2, "null"): VERDICT_CONFIRMED},
        severity_by_key={("a.py", 2, "null"): "high"},
    )
    assert len(kept) == 1
    assert kept[0].verdict == VERDICT_CONFIRMED
