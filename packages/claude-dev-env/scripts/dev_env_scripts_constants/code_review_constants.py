"""Named constants for the host-aware `/code-review` invoker and review loop.

::

    ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER
        ok: ("low", "medium", "high", "xhigh", "max")
        flag: "ultra"  (rejected; needs an interactive terminal)
    ALL_FINDING_SEVERITIES
        ok: ("blocker", "high", "medium", "low", "nit")
    ALL_LOOP_TERMINALS
        ok: ("clean", "nits_fixed", "blocked_at_cap", "advisor_blocked")
    RECORD_STAMP_FLAG
        ok: "--record-stamp"

Effort tokens re-export the hooks enforcement constants (single source).
Scalar flags, JSON keys, mint-loop messages, finding severity vocabulary,
reviewed-head counting, and loop terminal resolution live here.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType

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


def _load_enforcement_constants_module() -> ModuleType:
    """Load the hooks enforcement constants by explicit file path.

    Binds a private module name so a foreign ``config`` package on
    ``sys.path`` cannot win the import and drift the effort token set.
    """
    package_root_directory = Path(__file__).resolve().parent.parent.parent
    constants_file_path = (
        package_root_directory
        / "hooks"
        / "blocking"
        / "config"
        / "code_review_enforcement_constants.py"
    )
    module_name = "_code_review_enforcement_constants_for_scripts"
    cached_module = sys.modules.get(module_name)
    if cached_module is not None:
        return cached_module
    module_spec = importlib.util.spec_from_file_location(
        module_name,
        constants_file_path,
    )
    if module_spec is None or module_spec.loader is None:
        raise ImportError(
            f"could not load code-review enforcement constants from {constants_file_path}"
        )
    constants_module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_name] = constants_module
    module_spec.loader.exec_module(constants_module)
    return constants_module


_ENFORCEMENT_CONSTANTS = _load_enforcement_constants_module()

ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER: tuple[str, ...] = (
    _ENFORCEMENT_CONSTANTS.ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER
)
"""Effort tokens ordered low to max; single source from enforcement constants."""

RECORD_STAMP_FLAG: str = _ENFORCEMENT_CONSTANTS.SANCTIONED_STAMP_MINTER_FLAG
"""CLI flag that forces chain mode and mints a clean stamp on a stable pass."""

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

The review binary refuses ``bypassPermissions`` outright for a root caller,
so asking for it there means no review runs and no stamp is ever minted.
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
"""Return code required before a clean stamp may advance past CODE_REVIEW."""

RESULT_KEY_STAMP_MINTED: str = "stamp_minted"
"""JSON result key holding whether a clean stamp was written this run."""

RESULT_KEY_PASS_COUNT: str = "pass_count"
"""JSON result key holding how many review passes the mint loop ran."""

RESULT_KEY_BOUND_HASH: str = "bound_hash"
"""JSON result key holding the surface hash bound into a minted stamp, or null."""

CLI_EFFORT_METAVAR: str = "effort"
"""Argparse metavar for the positional effort token."""

CLI_EFFORT_HELP: str = (
    "Review effort token: low, medium, high, xhigh, or max "
    "(ultra is rejected; default high)."
)
"""Help text for the positional effort argument."""

CLI_RECORD_STAMP_HELP: str = (
    "Force chain mode, loop a capped number of review passes, and mint a "
    "clean stamp only when a pass exits 0 with a stable surface hash."
)
"""Help text for the --record-stamp flag."""

INVALID_EFFORT_RETURNCODE: int = 2
"""Return code when the caller passes an unknown or unsupported effort token."""

STAMP_DID_NOT_CONVERGE_RETURNCODE: int = 1
"""Return code when the mint loop hits its pass cap without a stable clean pass."""

MAXIMUM_STAMP_MINT_PASSES: int = 3
"""Cap on review passes under --record-stamp before the invoker gives up."""

EFFORT_TOKEN_LIST_SEPARATOR: str = ", "
"""Separator used when listing allowed effort tokens in error messages."""

INVALID_EFFORT_MESSAGE: str = (
    "invalid effort {effort!r}: must be one of {allowed}; "
    "'ultra' is rejected because it requires an interactive terminal"
)
"""Stderr template when the caller supplies an unknown or ultra effort token."""

STAMP_DID_NOT_CONVERGE_MESSAGE: str = (
    "code-review stamp minting did not converge after {pass_count} passes "
    "(surface kept changing or review return codes stayed non-zero); no stamp written"
)
"""Stderr template when the mint loop hits the pass cap without minting."""

STAMP_STORE_IMPORT_FAILURE_MESSAGE: str = (
    "code-review stamp store could not be imported for --record-stamp: {error}"
)
"""Stderr template when --record-stamp cannot load the stamp store module."""

STAMP_STORE_MODULE_FILE_NAME: str = "code_review_stamp_store.py"
"""File name of the stamp store module under hooks/blocking."""

STAMP_STORE_MODULE_NAME: str = "code_review_stamp_store"
"""Import name of the stamp store module."""

STAMP_STORE_LIVE_SURFACE_HASH_NAME: str = "live_surface_hash"
"""Attribute name of the live surface-hash helper on the stamp store module."""

STAMP_STORE_RECORD_CLEAN_STAMP_NAME: str = "record_clean_stamp"
"""Attribute name of the stamp-mint helper on the stamp store module."""

STAMP_STORE_RESOLVE_REPO_ROOT_NAME: str = "resolve_repo_root"
"""Attribute name of the repo-root resolver on the stamp store module."""

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

TERMINAL_BLOCKED_AT_CAP: str = "blocked_at_cap"
"""Loop terminal when head three still holds an unclassified or non-nit finding."""

TERMINAL_ADVISOR_BLOCKED: str = "advisor_blocked"
"""Loop terminal when classification needs an advisor that cannot be reached."""

ALL_LOOP_TERMINALS: tuple[str, ...] = (
    TERMINAL_CLEAN,
    TERMINAL_NITS_FIXED,
    TERMINAL_BLOCKED_AT_CAP,
    TERMINAL_ADVISOR_BLOCKED,
)
"""Frozen set of review-loop terminal statuses."""

MAXIMUM_REVIEWED_HEADS: int = 3
"""Cap on distinct git heads the review loop may review before blocking."""

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
    nits-only check so they route to classification or the cap terminal.

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
    """Append ``head_sha`` once when it is new and under the three-head cap.

    ::

        record_reviewed_head((), "aaa")           # ok: ("aaa",)
        record_reviewed_head(("aaa",), "aaa")     # ok: ("aaa",)  re-review
        record_reviewed_head(("a", "b", "c"), "d")  # ok: unchanged at cap

    A re-review of the same head does not increment the count. A fourth
    distinct head is refused so the loop never reviews past the cap.

    Args:
        all_reviewed_head_shas: Ordered distinct heads already reviewed.
        head_sha: Git head under review for this pass.

    Returns:
        The prior tuple, or the prior tuple plus ``head_sha`` when new.
    """
    if head_sha in all_reviewed_head_shas:
        return all_reviewed_head_shas
    if len(all_reviewed_head_shas) >= MAXIMUM_REVIEWED_HEADS:
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
            all_findings=[{"severity": "high", "verdict": "CONFIRMED"}],
            reviewed_head_count=3, is_gates_passed=True, is_nits_applied=False,
        )  # ok: "blocked_at_cap"

    Empty findings return clean. Nits-only findings return nits_fixed after
    the nits are applied and gates pass, including on the third head. An
    unclassified or non-nit finding on the third head returns blocked_at_cap.
    An unreachable advisor needed for classification returns advisor_blocked.
    Open non-nit work before the cap returns None so the caller re-enters.

    Args:
        all_findings: Structured findings retained for this head.
        reviewed_head_count: Distinct heads reviewed so far, including this one.
        is_gates_passed: Whether required checks passed for this decision.
        is_nits_applied: Whether every nit on the target was fixed.
        is_advisor_unreachable: Whether classification needs a missing advisor.

    Returns:
        One of ``ALL_LOOP_TERMINALS``, or None when the loop continues.
    """
    if is_advisor_unreachable and has_unclassified_finding(all_findings):
        return TERMINAL_ADVISOR_BLOCKED
    if not all_findings:
        return TERMINAL_CLEAN
    if is_nits_only_findings(all_findings) and is_nits_applied and is_gates_passed:
        return TERMINAL_NITS_FIXED
    if reviewed_head_count < MAXIMUM_REVIEWED_HEADS:
        return None
    if has_unclassified_finding(all_findings):
        return TERMINAL_BLOCKED_AT_CAP
    if has_non_nit_finding(all_findings):
        return TERMINAL_BLOCKED_AT_CAP
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
            terminal="blocked_at_cap",
            all_surviving_findings=[{"severity": "high", "verdict": "CONFIRMED"}],
            reviewed_head_count=3,
            is_draft_preserved=True,
        )["draft_preserved"]  # ok: True

    ``blocked_at_cap`` keeps the pull request draft and carries every
    surviving structured finding. Other terminals use the same shape so
    callers read one schema.

    Args:
        terminal: One of ``ALL_LOOP_TERMINALS``.
        all_surviving_findings: Findings still open at the terminal.
        reviewed_head_count: Distinct heads reviewed before this terminal.
        is_draft_preserved: Whether the pull request stays in draft.

    Returns:
        A JSON-ready mapping with terminal, draft flag, head count, findings.
    """
    return {
        RESULT_KEY_TERMINAL: terminal,
        RESULT_KEY_DRAFT_PRESERVED: is_draft_preserved,
        RESULT_KEY_REVIEWED_HEAD_COUNT: reviewed_head_count,
        RESULT_KEY_SURVIVING_FINDINGS: list(all_surviving_findings),
    }
