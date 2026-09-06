"""Evaluate local verification state for the native Git notice."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

from git_hooks_constants.verification_notice_constants import (
    ALL_GIT_BASE_QUERY_PREFIX,
    GIT_COMMAND_SUCCESS_EXIT_CODE,
    HEX_DIGITS,
    NOTICE_FAILED_LINE,
    NOTICE_NO_PASS_LINE,
    NOTICE_PASSED_LINE,
    NOTICE_SETUP_PENDING_LINE,
    NOTICE_STALE_LINE,
    REPORT_AGGREGATE_FIELD,
    REPORT_BASE_FIELD,
    REPORT_EXIT_CODE_FIELD,
    REPORT_FAILED_FIELD,
    REPORT_HEAD_FIELD,
    REPORT_INCOMPLETE_FIELD,
    REPORT_INPUTS_UNCHANGED_FIELD,
    REPORT_MANIFEST_DIGEST_FIELD,
    REPORT_PASSED_FIELD,
    REPORT_PUBLISHABLE_FIELD,
    REPORT_STATUS_FIELD,
    REPORT_TOTAL_FIELD,
    REPORT_WORKTREE_CLEAN_FIELD,
    RESOLVED_SHA_LENGTH,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_PENDING,
    STATUS_STALE,
    STATUS_UNVERIFIED,
)
from local_verification.manifest import (
    ManifestRunFatal,
    compute_manifest_digest,
    load_manifest,
)


class _VerificationNoticeContext(Protocol):
    @property
    def current_head(self) -> str | None: ...

    @property
    def repository_root(self) -> Path: ...

    @property
    def manifest_path(self) -> Path | None: ...

    @property
    def manifest_is_available(self) -> bool: ...

    @property
    def report_is_present(self) -> bool: ...

    @property
    def all_report_fields(self) -> Mapping[str, object] | None: ...


def _evaluate_context(
    context: _VerificationNoticeContext,
    run_git_query: Callable[[Path, tuple[str, ...], bool], str | None],
) -> tuple[str, str | None]:
    context_state = _context_setup_state(context)
    if context_state is not None:
        return context_state, None
    if context.current_head is None or context.all_report_fields is None:
        return STATUS_UNVERIFIED, None
    reported_head = _read_text_field(context.all_report_fields, REPORT_HEAD_FIELD)
    if reported_head is None:
        return STATUS_UNVERIFIED, None
    if reported_head != context.current_head:
        return STATUS_STALE, None
    if _read_report_status(context.all_report_fields) == STATUS_FAILED:
        return STATUS_FAILED, None
    if _is_complete_pass(context, run_git_query):
        return STATUS_PASSED, context.current_head
    return STATUS_UNVERIFIED, None


def _context_setup_state(context: _VerificationNoticeContext) -> str | None:
    if context.all_report_fields is None:
        return STATUS_UNVERIFIED if context.report_is_present else STATUS_PENDING
    if context.all_report_fields is not None and context.manifest_path is None:
        return STATUS_UNVERIFIED
    if not context.manifest_is_available:
        return STATUS_PENDING
    return None


def _read_text_field(
    all_fields: Mapping[str, object],
    field_name: str,
) -> str | None:
    field_text = all_fields.get(field_name)
    if not isinstance(field_text, str):
        return None
    return field_text.strip() or None


def _read_report_status(all_report_fields: Mapping[str, object]) -> str | None:
    status_text = _read_text_field(all_report_fields, REPORT_STATUS_FIELD)
    if status_text:
        return status_text
    all_aggregate_fields = all_report_fields.get(REPORT_AGGREGATE_FIELD)
    if isinstance(all_aggregate_fields, Mapping):
        return _read_text_field(all_aggregate_fields, REPORT_STATUS_FIELD)
    return None


def _build_state_message(state: str, is_manifest_available: bool) -> str:
    if not is_manifest_available:
        return NOTICE_SETUP_PENDING_LINE
    message_by_state = {
        STATUS_STALE: NOTICE_STALE_LINE,
        STATUS_FAILED: NOTICE_FAILED_LINE,
        STATUS_PASSED: NOTICE_PASSED_LINE,
    }
    return message_by_state.get(state, NOTICE_NO_PASS_LINE)


def _is_complete_pass(
    context: _VerificationNoticeContext,
    run_git_query: Callable[[Path, tuple[str, ...], bool], str | None],
) -> bool:
    all_report_fields = context.all_report_fields
    if all_report_fields is None or context.manifest_path is None:
        return False
    base_revision = _read_text_field(all_report_fields, REPORT_BASE_FIELD)
    if not _report_has_complete_pass(all_report_fields, base_revision):
        return False
    if base_revision is None or not _base_matches_current(
        context.repository_root,
        base_revision,
        run_git_query,
    ):
        return False
    if not _worktree_is_clean(context.repository_root, run_git_query):
        return False
    if not _manifest_digest_matches(all_report_fields, context.manifest_path):
        return False
    all_aggregate_fields = all_report_fields.get(REPORT_AGGREGATE_FIELD)
    return isinstance(all_aggregate_fields, Mapping) and _aggregate_is_complete_pass(
        all_aggregate_fields
    )


def _report_has_complete_pass(
    all_report_fields: Mapping[str, object],
    base_revision: str | None,
) -> bool:
    return (
        _read_report_status(all_report_fields) == STATUS_PASSED
        and _report_is_publishable(all_report_fields)
        and base_revision is not None
        and _is_resolved_sha(base_revision)
    )


def _report_is_publishable(all_report_fields: Mapping[str, object]) -> bool:
    return all(
        all_report_fields.get(each_field) is True
        for each_field in (
            REPORT_PUBLISHABLE_FIELD,
            REPORT_WORKTREE_CLEAN_FIELD,
            REPORT_INPUTS_UNCHANGED_FIELD,
        )
    )


def _base_matches_current(
    repository_root: Path,
    base_revision: str,
    run_git_query: Callable[[Path, tuple[str, ...], bool], str | None],
) -> bool:
    current_base_revision = run_git_query(
        repository_root,
        (*ALL_GIT_BASE_QUERY_PREFIX, "origin/main^{commit}"),
        False,
    )
    return current_base_revision == base_revision


def _worktree_is_clean(
    repository_root: Path,
    run_git_query: Callable[[Path, tuple[str, ...], bool], str | None],
) -> bool:
    status_text = run_git_query(
        repository_root,
        ("status", "--porcelain=v1", "--untracked-files=all"),
        True,
    )
    return status_text == ""


def _is_resolved_sha(revision_text: str) -> bool:
    return len(revision_text) == RESOLVED_SHA_LENGTH and all(
        each_character.casefold() in HEX_DIGITS for each_character in revision_text
    )


def _manifest_digest_matches(
    all_report_fields: Mapping[str, object],
    manifest_path: Path | None,
) -> bool:
    manifest_digest = _read_text_field(all_report_fields, REPORT_MANIFEST_DIGEST_FIELD)
    if not manifest_digest or manifest_path is None:
        return False
    try:
        loaded_manifest = load_manifest(manifest_path)
        actual_digest = compute_manifest_digest(loaded_manifest)
    except (ManifestRunFatal, OSError, UnicodeError, ValueError):
        return False
    return actual_digest == manifest_digest.casefold()


def _aggregate_is_complete_pass(
    all_aggregate_fields: Mapping[str, object],
) -> bool:
    total_checks = all_aggregate_fields.get(REPORT_TOTAL_FIELD)
    passed_checks = all_aggregate_fields.get(REPORT_PASSED_FIELD)
    failed_checks = all_aggregate_fields.get(REPORT_FAILED_FIELD)
    incomplete_checks = all_aggregate_fields.get(REPORT_INCOMPLETE_FIELD)
    exit_code = all_aggregate_fields.get(REPORT_EXIT_CODE_FIELD)
    return (
        isinstance(total_checks, int)
        and total_checks > 0
        and passed_checks == total_checks
        and failed_checks == 0
        and incomplete_checks == 0
        and exit_code == GIT_COMMAND_SUCCESS_EXIT_CODE
    )
