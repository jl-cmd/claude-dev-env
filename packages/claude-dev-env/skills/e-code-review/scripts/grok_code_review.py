#!/usr/bin/env python3
"""Grok medium-review discovery and verification orchestration.

Dispatches exactly eight named finder angles at one target head, binds each
finder to an isolated identity (worktree path, leader socket, advisor session),
deduplicates candidates, verifies them, and retains CONFIRMED plus unresolved
PLAUSIBLE findings with severity. Head drift rejects the whole batch.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from config.grok_code_review_constants import (
    ALL_MEDIUM_FINDER_ANGLES,
    ALL_SEVERITIES,
    ALL_VERIFICATION_VERDICTS,
    MEDIUM_REVIEW_FINDER_COUNT,
    MEDIUM_REVIEW_SCHEMA_VERSION,
    VERDICT_CONFIRMED,
    VERDICT_PLAUSIBLE,
    VERDICT_REFUTED,
)


@dataclass(frozen=True)
class FinderCandidate:
    """One candidate finding from a discovery angle."""

    angle: str
    file_path: str
    line_number: int
    mechanism: str
    scenario: str
    worktree_path: str
    leader_socket: str
    advisor_session_id: str
    reviewed_head: str


@dataclass(frozen=True)
class VerifiedFinding:
    """A retained finding after verification."""

    file_path: str
    line_number: int
    mechanism: str
    scenario: str
    verdict: str
    severity: str
    reviewed_head: str


@dataclass
class MediumReviewBatch:
    """Result of one medium-review run at a single head."""

    schema_version: str = MEDIUM_REVIEW_SCHEMA_VERSION
    target_head: str = ""
    diff_base: str = ""
    all_finder_angles: tuple[str, ...] = ALL_MEDIUM_FINDER_ANGLES
    all_retained_findings: list[VerifiedFinding] = field(default_factory=list)
    is_rejected: bool = False
    rejection_reason: str | None = None


def require_exact_finder_set(all_angles: tuple[str, ...] | list[str]) -> None:
    """Require exactly the eight named finder angles.

    Args:
        all_angles: Angle names present in a run.

    Raises:
        ValueError: When the set is not exactly the eight angles.
    """
    angle_set = set(all_angles)
    expected = set(ALL_MEDIUM_FINDER_ANGLES)
    if angle_set != expected or len(all_angles) != MEDIUM_REVIEW_FINDER_COUNT:
        raise ValueError(
            f"finder angles must be exactly {MEDIUM_REVIEW_FINDER_COUNT}: "
            f"got {sorted(angle_set)}"
        )


def deduplicate_candidates(
    all_candidates: list[FinderCandidate],
) -> list[FinderCandidate]:
    """Keep the most concrete scenario per file/line/mechanism.

    Args:
        all_candidates: Raw finder outputs.

    Returns:
        Deduplicated candidates preserving the longest scenario text.
    """
    best_by_key: dict[tuple[str, int, str], FinderCandidate] = {}
    for each_candidate in all_candidates:
        key = (
            each_candidate.file_path,
            each_candidate.line_number,
            each_candidate.mechanism,
        )
        existing = best_by_key.get(key)
        if existing is None or len(each_candidate.scenario) > len(existing.scenario):
            best_by_key[key] = each_candidate
    return list(best_by_key.values())


def retain_verified_findings(
    *,
    all_candidates: list[FinderCandidate],
    verdict_by_key: dict[tuple[str, int, str], str],
    severity_by_key: dict[tuple[str, int, str], str],
) -> list[VerifiedFinding]:
    """Retain CONFIRMED and unresolved PLAUSIBLE findings with severity.

    Args:
        all_candidates: Deduplicated candidates.
        verdict_by_key: Verification verdict per file/line/mechanism.
        severity_by_key: Severity per file/line/mechanism.

    Returns:
        Retained findings.

    Raises:
        ValueError: When a retained finding lacks a legal severity or verdict.
    """
    all_retained: list[VerifiedFinding] = []
    for each_candidate in all_candidates:
        key = (
            each_candidate.file_path,
            each_candidate.line_number,
            each_candidate.mechanism,
        )
        verdict = verdict_by_key.get(key)
        if verdict not in ALL_VERIFICATION_VERDICTS:
            raise ValueError(f"missing or illegal verdict for {key}")
        if verdict == VERDICT_REFUTED:
            continue
        if verdict not in {VERDICT_CONFIRMED, VERDICT_PLAUSIBLE}:
            continue
        severity = severity_by_key.get(key)
        if severity not in ALL_SEVERITIES:
            raise ValueError(f"missing or illegal severity for {key}")
        all_retained.append(
            VerifiedFinding(
                file_path=each_candidate.file_path,
                line_number=each_candidate.line_number,
                mechanism=each_candidate.mechanism,
                scenario=each_candidate.scenario,
                verdict=verdict,
                severity=severity,
                reviewed_head=each_candidate.reviewed_head,
            )
        )
    return all_retained


def run_medium_review(
    *,
    target_head: str,
    diff_base: str,
    all_finder_candidates: list[FinderCandidate],
    verdict_by_key: dict[tuple[str, int, str], str],
    severity_by_key: dict[tuple[str, int, str], str],
    live_head: str,
    is_any_advisor_blocked: bool = False,
) -> MediumReviewBatch:
    """Run discovery and verification for one medium-review head.

    Args:
        target_head: Reviewed head OID.
        diff_base: Diff base OID.
        all_finder_candidates: Outputs from the eight finder angles.
        verdict_by_key: Verification results keyed by file/line/mechanism.
        severity_by_key: Severities for retained findings.
        live_head: Live head OID; must match target_head.
        is_any_advisor_blocked: True when any finder ended advisor_blocked.

    Raises:
        ValueError: When finder angles are incomplete or duplicated.

    Returns:
        The medium-review batch (possibly rejected).
    """
    batch = MediumReviewBatch(target_head=target_head, diff_base=diff_base)
    if is_any_advisor_blocked:
        batch.is_rejected = True
        batch.rejection_reason = "advisor_blocked"
        return batch
    if live_head != target_head:
        batch.is_rejected = True
        batch.rejection_reason = "head_drift"
        return batch
    for each_candidate in all_finder_candidates:
        if each_candidate.reviewed_head != target_head:
            batch.is_rejected = True
            batch.rejection_reason = "finder_head_mismatch"
            return batch
    all_angles = [each.angle for each in all_finder_candidates]
    all_sockets = {each.leader_socket for each in all_finder_candidates}
    all_sessions = {each.advisor_session_id for each in all_finder_candidates}
    all_worktrees = {each.worktree_path for each in all_finder_candidates}
    if (
        len(all_sockets) != len(all_finder_candidates)
        or len(all_sessions) != len(all_finder_candidates)
        or len(all_worktrees) != len(all_finder_candidates)
    ):
        batch.is_rejected = True
        batch.rejection_reason = "non_unique_finder_identity"
        return batch
    require_exact_finder_set(tuple(sorted(set(all_angles))))
    if len(set(all_angles)) != MEDIUM_REVIEW_FINDER_COUNT:
        raise ValueError("each finder angle must run exactly once")
    deduped = deduplicate_candidates(all_finder_candidates)
    batch.all_retained_findings = retain_verified_findings(
        all_candidates=deduped,
        verdict_by_key=verdict_by_key,
        severity_by_key=severity_by_key,
    )
    return batch
