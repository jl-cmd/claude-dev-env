"""Named constants for the host-aware `/code-review` invoker and review loop.

::

    ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER
        ok: ("low", "medium", "high", "xhigh", "max")
        flag: "ultra"  (rejected; needs an interactive terminal)
    ALL_FINDING_SEVERITIES
        ok: ("blocker", "high", "medium", "low", "nit")
    ALL_LOOP_TERMINALS
        ok: ("clean", "nits_fixed", "advisor_blocked")
Effort tokens, scalar flags, JSON keys, finding severity vocabulary,
reviewed-head counting, and loop terminal resolution live here.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence

ROOT_EFFECTIVE_USER_ID: int = 0
"""Effective user id the review binary treats as root."""

NON_ROOT_EFFECTIVE_USER_ID: int = 1000
"""Effective user id stood in for a platform that reports no user id."""


def _read_effective_user_id() -> int:
    """Read this process's effective user id, or a non-root stand-in.

    Windows exposes no ``os.geteuid``, so reading it there raises and the
    whole constants module fails to import — taking the review invoker with
    it. A caller on such a platform is never the root the review binary
    refuses, so it reads as an ordinary caller.
    """
    read_effective_user_id = getattr(os, "geteuid", None)
    if read_effective_user_id is None:
        return NON_ROOT_EFFECTIVE_USER_ID
    return int(read_effective_user_id())


IS_ROOT_CALLER: bool = _read_effective_user_id() == ROOT_EFFECTIVE_USER_ID
"""Whether this process runs as root, which limits the permission modes."""


ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER: tuple[str, ...] = (
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
)
"""Effort tokens ordered from the lowest supported effort to the highest."""

DEFAULT_CODE_REVIEW_EFFORT: str = "high"
"""Default effort when the caller omits the positional effort token."""

CODE_REVIEW_SLASH_COMMAND: str = "/code-review"
"""Built-in Claude Code slash command that runs the repository review."""

CODE_REVIEW_FIX_FLAG: str = "--fix"
"""Slash-command flag that applies automatic fixes for review findings."""

CODE_REVIEW_MODEL_ALIAS: str = "opus"
"""CLI `--model` short alias the review always pins to."""

PERMISSION_MODE_FLAG: str = "--permission-mode"
"""CLI flag that selects how the headless claude process handles tool permission prompts."""

PERMISSION_MODE_BYPASS: str = "bypassPermissions"
"""Permission-mode value that auto-approves tools for unattended chain runs."""

PERMISSION_MODE_ACCEPT_EDITS: str = "acceptEdits"
"""Permission mode asked for when the caller is root.

The review binary refuses ``bypassPermissions`` outright for a root caller.
"""

REVIEW_PERMISSION_MODE: str = (
    PERMISSION_MODE_ACCEPT_EDITS if IS_ROOT_CALLER else PERMISSION_MODE_BYPASS
)
"""Permission mode this caller asks the review binary for."""

MODE_IN_SESSION: str = "in_session"
"""Result mode when the host is Claude and the session already runs opus."""

MODE_CHAIN: str = "chain"
"""Result mode when the helper spawns a headless claude chain for the review."""

RESULT_KEY_MODE: str = "mode"
"""JSON result key naming the review mode (`in_session` or `chain`)."""

RESULT_KEY_SERVED_COMMAND: str = "served_command"
"""JSON result key naming the chain binary that served the call, or null."""

RESULT_KEY_RETURNCODE: str = "returncode"
"""JSON result key holding the process return code from the chain run."""

RESULT_KEY_DIRTY_TREE: str = "dirty_tree"
"""JSON result key holding whether the working tree is dirty after the review."""

CLI_SESSION_MODEL_FLAG: str = "--session-model"
"""CLI flag naming the caller's current session model short alias."""

GIT_BINARY: str = "git"
"""Executable name resolved on PATH for working-tree dirty checks."""

GIT_STATUS_SUBCOMMAND: str = "status"
"""Git subcommand used to detect an uncommitted dirty working tree."""

GIT_PORCELAIN_FLAG: str = "--porcelain"
"""Git status flag that prints machine-readable dirty-path lines."""

IN_SESSION_RETURNCODE: int = 0
"""Return code reported when the helper hands the review back to the in-session skill."""

HOST_PROFILE_ERROR_RETURNCODE: int = 1
"""Return code when host-profile detection raises ValueError at the CLI boundary."""

SUCCESSFUL_REVIEW_RETURNCODE: int = 0
"""Return code for a successful review invocation."""

CLI_EFFORT_METAVAR: str = "effort"
"""Argparse metavar for the positional effort token."""

CLI_EFFORT_HELP: str = (
    "Review effort token: low, medium, high, xhigh, or max "
    "(ultra is rejected; default high)."
)
"""Help text for the positional effort argument."""

INVALID_EFFORT_RETURNCODE: int = 2
"""Return code when the caller passes an unknown or unsupported effort token."""

EFFORT_TOKEN_LIST_SEPARATOR: str = ", "
"""Separator used when listing allowed effort tokens in error messages."""

INVALID_EFFORT_MESSAGE: str = (
    "invalid effort {effort!r}: must be one of {allowed}; "
    "'ultra' is rejected because it requires an interactive terminal"
)
"""Stderr template when the caller supplies an unknown or ultra effort token."""

SEVERITY_BLOCKER: str = "blocker"
"""Finding severity for a release-blocking defect."""

SEVERITY_HIGH: str = "high"
"""Finding severity for a high-impact defect that is not a release blocker."""

SEVERITY_MEDIUM: str = "medium"
"""Finding severity for a moderate maintainer-action defect."""

SEVERITY_LOW: str = "low"
"""Finding severity for a low-impact non-nit defect."""

SEVERITY_NIT: str = "nit"
"""Finding severity for a mechanical clarity, format, or typo fix only."""

ALL_FINDING_SEVERITIES: tuple[str, ...] = (
    SEVERITY_BLOCKER,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    SEVERITY_LOW,
    SEVERITY_NIT,
)
"""Frozen severity vocabulary every retained finding must use."""

VERDICT_CONFIRMED: str = "CONFIRMED"
"""Verification verdict when the trigger and wrong outcome are named."""

VERDICT_PLAUSIBLE: str = "PLAUSIBLE"
"""Verification verdict when the mechanism is real and the trigger is uncertain."""

VERDICT_REFUTED: str = "REFUTED"
"""Verification verdict when the candidate is factually wrong or guarded."""

ALL_VERIFICATION_VERDICTS: tuple[str, ...] = (
    VERDICT_CONFIRMED,
    VERDICT_PLAUSIBLE,
    VERDICT_REFUTED,
)
"""Frozen verification-verdict vocabulary from the medium verify phase."""

ALL_RETAINED_VERIFICATION_VERDICTS: tuple[str, ...] = (
    VERDICT_CONFIRMED,
    VERDICT_PLAUSIBLE,
)
"""Verdicts that keep a candidate in the retained findings list."""

TERMINAL_CLEAN: str = "clean"
"""Loop terminal when a reviewed head retains zero findings."""

TERMINAL_NITS_FIXED: str = "nits_fixed"
"""Loop terminal when every retained finding is a fixed nit after gates."""

TERMINAL_ADVISOR_BLOCKED: str = "advisor_blocked"
"""Loop terminal when classification needs an advisor that cannot be reached."""

ALL_LOOP_TERMINALS: tuple[str, ...] = (
    TERMINAL_CLEAN,
    TERMINAL_NITS_FIXED,
    TERMINAL_ADVISOR_BLOCKED,
)
"""Frozen set of review-loop terminal statuses."""

FINDING_FIELD_SEVERITY: str = "severity"
"""Structured finding field that holds one of ``ALL_FINDING_SEVERITIES``."""

FINDING_FIELD_VERDICT: str = "verdict"
"""Structured finding field that holds a verification verdict."""

RESULT_KEY_TERMINAL: str = "terminal"
"""JSON result key naming the review-loop terminal status."""

RESULT_KEY_DRAFT_PRESERVED: str = "draft_preserved"
"""JSON result key holding whether the pull request stays draft."""

RESULT_KEY_REVIEWED_HEAD_COUNT: str = "reviewed_head_count"
"""JSON result key holding how many distinct heads the loop reviewed."""

RESULT_KEY_SURVIVING_FINDINGS: str = "surviving_findings"
"""JSON result key holding structured findings that remain at terminal."""


def is_known_finding_severity(severity: str) -> bool:
    """Return whether ``severity`` is one of the frozen five tokens.

    ::

        is_known_finding_severity("nit")      # ok: True
        is_known_finding_severity("P1")       # flag: False
        is_known_finding_severity("")         # flag: False

    Args:
        severity: Candidate severity token from a structured finding.

    Returns:
        True when ``severity`` is in ``ALL_FINDING_SEVERITIES``.
    """
    return severity in ALL_FINDING_SEVERITIES


def is_nit_finding_severity(severity: str) -> bool:
    """Return whether ``severity`` is exactly the nit token.

    ::

        is_nit_finding_severity("nit")   # ok: True
        is_nit_finding_severity("low")   # flag: False

    Args:
        severity: Candidate severity token from a structured finding.

    Returns:
        True when ``severity`` equals ``SEVERITY_NIT``.
    """
    return severity == SEVERITY_NIT


def is_retained_verification_verdict(verdict: str) -> bool:
    """Return whether ``verdict`` keeps a finding in the retained set.

    ::

        is_retained_verification_verdict("CONFIRMED")  # ok: True
        is_retained_verification_verdict("REFUTED")    # flag: False

    Args:
        verdict: Verification vote from the medium verify phase.

    Returns:
        True when ``verdict`` is CONFIRMED or PLAUSIBLE.
    """
    return verdict in ALL_RETAINED_VERIFICATION_VERDICTS


def finding_carries_severity_and_verdict(
    *,
    severity: object,
    verdict: object,
) -> bool:
    """Return whether one retained finding carries both required fields.

    ::

        finding_carries_severity_and_verdict(
            severity="high", verdict="CONFIRMED"
        )  # ok: True
        finding_carries_severity_and_verdict(
            severity="high", verdict=None
        )  # flag: False

    A retained finding needs a known severity and a retained verification
    verdict. Missing either field, or a REFUTED verdict, fails the contract.

    Args:
        severity: Severity token from a structured finding, or missing value.
        verdict: Verification verdict from a structured finding, or missing.

    Returns:
        True when severity and retained verdict are both present and valid.
    """
    if not isinstance(severity, str) or not isinstance(verdict, str):
        return False
    if not is_known_finding_severity(severity):
        return False
    return is_retained_verification_verdict(verdict)


def all_findings_carry_severity_and_verdict(
    all_findings: Sequence[Mapping[str, object]],
) -> bool:
    """Return whether every finding carries severity and a retained verdict.

    ::

        all_findings_carry_severity_and_verdict([])  # ok: True
        all_findings_carry_severity_and_verdict(
            [{"severity": "nit", "verdict": "CONFIRMED"}]
        )  # ok: True

    Args:
        all_findings: Structured findings retained after verification.

    Returns:
        True when every finding passes ``finding_carries_severity_and_verdict``.
    """
    for each_finding in all_findings:
        if not finding_carries_severity_and_verdict(
            severity=each_finding.get(FINDING_FIELD_SEVERITY),
            verdict=each_finding.get(FINDING_FIELD_VERDICT),
        ):
            return False
    return True


def has_unclassified_finding(all_findings: Sequence[Mapping[str, object]]) -> bool:
    """Return whether any finding lacks a known severity token.

    ::

        has_unclassified_finding([{"verdict": "CONFIRMED"}])  # ok: True
        has_unclassified_finding(
            [{"severity": "nit", "verdict": "CONFIRMED"}]
        )  # flag: False

    Args:
        all_findings: Structured findings under terminal evaluation.

    Returns:
        True when any finding omits severity or uses an unknown token.
    """
    for each_finding in all_findings:
        severity = each_finding.get(FINDING_FIELD_SEVERITY)
        if not isinstance(severity, str):
            return True
        if not is_known_finding_severity(severity):
            return True
    return False


def has_non_nit_finding(all_findings: Sequence[Mapping[str, object]]) -> bool:
    """Return whether any finding carries a known non-nit severity.

    ::

        has_non_nit_finding([{"severity": "high"}])  # ok: True
        has_non_nit_finding([{"severity": "nit"}])   # flag: False

    Args:
        all_findings: Structured findings under terminal evaluation.

    Returns:
        True when any finding's severity is known and not ``nit``.
    """
    for each_finding in all_findings:
        severity = each_finding.get(FINDING_FIELD_SEVERITY)
        if not isinstance(severity, str):
            continue
        if not is_known_finding_severity(severity):
            continue
        if not is_nit_finding_severity(severity):
            return True
    return False


def is_nits_only_findings(all_findings: Sequence[Mapping[str, object]]) -> bool:
    """Return whether every finding is a classified nit and at least one exists.

    ::

        is_nits_only_findings([{"severity": "nit"}])  # ok: True
        is_nits_only_findings([])                      # flag: False
        is_nits_only_findings(
            [{"severity": "nit"}, {"severity": "high"}]
        )  # flag: False

    An empty list is clean, not nits-only. Unclassified findings fail the
    nits-only check so they route to classification before a terminal.

    Args:
        all_findings: Structured findings under terminal evaluation.

    Returns:
        True when the list is non-empty, fully classified, and all nits.
    """
    if not all_findings:
        return False
    if has_unclassified_finding(all_findings):
        return False
    return not has_non_nit_finding(all_findings)


def record_reviewed_head(
    all_reviewed_head_shas: tuple[str, ...],
    head_sha: str,
) -> tuple[str, ...]:
    """Append ``head_sha`` once when it is a new distinct head.

    ::

        record_reviewed_head((), "aaa")           # ok: ("aaa",)
        record_reviewed_head(("aaa",), "aaa")     # ok: ("aaa",)  re-review
        record_reviewed_head(("a", "b", "c"), "d")  # ok: ("a", "b", "c", "d")

    A re-review of the same head does not increment the count. There is no
    head count limit — every new head is recorded.

    Args:
        all_reviewed_head_shas: Ordered distinct heads already reviewed.
        head_sha: Git head under review for this pass.

    Returns:
        The prior tuple, or the prior tuple plus ``head_sha`` when new.
    """
    if head_sha in all_reviewed_head_shas:
        return all_reviewed_head_shas
    return all_reviewed_head_shas + (head_sha,)


def resolve_review_loop_terminal(
    *,
    all_findings: Sequence[Mapping[str, object]],
    reviewed_head_count: int,
    is_gates_passed: bool,
    is_nits_applied: bool,
    is_advisor_unreachable: bool = False,
) -> str | None:
    """Resolve the review-loop terminal, or None when the loop continues.

    ::

        resolve_review_loop_terminal(
            all_findings=(), reviewed_head_count=1,
            is_gates_passed=True, is_nits_applied=False,
        )  # ok: "clean"
        resolve_review_loop_terminal(
            all_findings=(), reviewed_head_count=1,
            is_gates_passed=False, is_nits_applied=False,
        )  # flag: None  (gates still open)
        resolve_review_loop_terminal(
            all_findings=[{"severity": "high", "verdict": "CONFIRMED"}],
            reviewed_head_count=5, is_gates_passed=True, is_nits_applied=False,
        )  # flag: None  (open non-nit work continues)

    Empty findings return clean only when gates pass. Nits-only findings
    return nits_fixed after each finding carries severity and a retained
    verdict, the nits are applied, and gates pass. An unreachable advisor
    needed for classification returns advisor_blocked. Open non-nit work
    returns None so the caller re-enters. There is no head-count stop.

    Args:
        all_findings: Structured findings retained for this head.
        reviewed_head_count: Distinct heads reviewed so far, including this one.
        is_gates_passed: Whether required checks passed for this decision.
        is_nits_applied: Whether every nit on the target was fixed.
        is_advisor_unreachable: Whether classification needs a missing advisor.

    Returns:
        One of ``ALL_LOOP_TERMINALS``, or None when the loop continues.
    """
    _ = reviewed_head_count
    if is_advisor_unreachable and has_unclassified_finding(all_findings):
        return TERMINAL_ADVISOR_BLOCKED
    if not all_findings:
        if is_gates_passed:
            return TERMINAL_CLEAN
        return None
    if (
        is_nits_only_findings(all_findings)
        and all_findings_carry_severity_and_verdict(all_findings)
        and is_nits_applied
        and is_gates_passed
    ):
        return TERMINAL_NITS_FIXED
    return None


def encode_review_loop_terminal_result(
    *,
    terminal: str,
    all_surviving_findings: Sequence[Mapping[str, object]],
    reviewed_head_count: int,
    is_draft_preserved: bool,
) -> dict[str, object]:
    """Serialize a review-loop terminal for hand-off and reporting.

    ::

        encode_review_loop_terminal_result(
            terminal="advisor_blocked",
            all_surviving_findings=[{"severity": "high", "verdict": "CONFIRMED"}],
            reviewed_head_count=2,
            is_draft_preserved=False,
        )["draft_preserved"]  # ok: True  (blocked terminals force draft)

    ``advisor_blocked`` keeps the pull request draft even when the caller
    passes a false draft flag. Other terminals use the caller's flag.
    Every terminal uses the same JSON shape.

    Args:
        terminal: One of ``ALL_LOOP_TERMINALS``.
        all_surviving_findings: Findings still open at the terminal.
        reviewed_head_count: Distinct heads reviewed before this terminal.
        is_draft_preserved: Whether the pull request stays in draft.

    Returns:
        A JSON-ready mapping with terminal, draft flag, head count, findings.
    """
    is_blocked_terminal = terminal == TERMINAL_ADVISOR_BLOCKED
    should_preserve_draft = is_blocked_terminal or is_draft_preserved
    return {
        RESULT_KEY_TERMINAL: terminal,
        RESULT_KEY_DRAFT_PRESERVED: should_preserve_draft,
        RESULT_KEY_REVIEWED_HEAD_COUNT: reviewed_head_count,
        RESULT_KEY_SURVIVING_FINDINGS: list(all_surviving_findings),
    }
