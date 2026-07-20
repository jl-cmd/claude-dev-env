"""Post an audit review (APPROVE / REQUEST_CHANGES / COMMENT) to a draft PR.

Consumed by ``/bugteam``, ``/findbugs``, and ``/qbug`` at the end of an audit
run. It POSTs to the reviews endpoint with a formatted body and inline
``comments[]`` derived from a findings JSON file.

::

    CLEAN            -> APPROVE, empty comments[]
    DIRTY            -> REQUEST_CHANGES, one inline comment per finding
    self-review 422  -> COMMENT downgrade, verdict body kept, disclosure added

The body skeleton is read at runtime from ``audit-reply-template.md`` so the
template stays the single source of truth for the review-body shape. Exit
codes: ``0`` success (prints the review ``html_url``), ``1`` user error,
``2`` retry exhaustion or an unrecoverable POST rejection.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import NoReturn

parent_directory = str(Path(__file__).resolve().parent)
if parent_directory not in sys.path:
    sys.path.insert(0, parent_directory)

from pr_loop_shared_constants.post_audit_thread_constants import (  # noqa: E402
    ALL_GH_API_COMMAND_PARTS,
    ALL_GH_API_USER_COMMAND_PARTS,
    ALL_GH_AUTH_STATUS_COMMAND_PARTS,
    ALL_GH_AUTH_TOKEN_COMMAND_PARTS,
    ALL_GH_TOKEN_ENV_VAR_NAMES,
    ALL_REQUIRED_FINDING_FIELDS,
    ALL_RETRY_BACKOFF_SECONDS,
    ALL_SUPPORTED_INLINE_COMMENT_SIDES,
    ALL_SUPPORTED_SEVERITY_TAGS,
    ALL_SUPPORTED_SKILLS,
    ALL_SUPPORTED_STATES,
    AUDIT_BODY_SKELETON_CLOSE_MARKER,
    AUDIT_BODY_SKELETON_OPEN_MARKER,
    BUGTEAM_REVIEWER_ACCOUNT_ENV_VAR_NAME,
    CLI_FLAG_COMMIT,
    CLI_FLAG_FINDINGS_JSON,
    CLI_FLAG_OWNER,
    CLI_FLAG_PR_NUMBER,
    CLI_FLAG_REPO,
    CLI_FLAG_SKILL,
    CLI_FLAG_STATE,
    DETAILS_BLOCK_BULLET_SEPARATOR,
    DETAILS_BLOCK_BULLET_TEMPLATE,
    DETAILS_BLOCK_FOOTER,
    DETAILS_BLOCK_HEADER,
    DISCLOSURE_BODY_SEPARATOR,
    ERROR_RESPONSE_PREVIEW_CHARS,
    EXIT_CODE_RETRY_EXHAUSTED,
    EXIT_CODE_USER_ERROR,
    GH_API_PR_PATH_TEMPLATE,
    GH_AUTH_STATUS_ACCOUNT_LINE_MARKER,
    GH_AUTH_STATUS_ACCOUNT_LINE_TOKEN_SEPARATOR,
    GH_AUTH_TOKEN_USER_FLAG,
    GH_ERROR_MESSAGE_FIELD,
    GH_PR_USER_FIELD,
    GH_USER_LOGIN_FIELD,
    GITHUB_API_ACCEPT_HEADER,
    GITHUB_API_BASE_URL,
    GITHUB_API_USER_AGENT,
    GITHUB_API_VERSION_HEADER,
    GITHUB_REVIEW_EVENT_APPROVE,
    GITHUB_REVIEW_EVENT_COMMENT,
    GITHUB_REVIEW_EVENT_REQUEST_CHANGES,
    HEADING_FOR_CLEAN,
    HEADING_FOR_DIRTY,
    HTTP_AUTHORIZATION_BEARER_PREFIX,
    HTTP_HEADER_ACCEPT,
    HTTP_HEADER_AUTHORIZATION,
    HTTP_HEADER_CONTENT_TYPE,
    HTTP_HEADER_GITHUB_API_VERSION,
    HTTP_HEADER_USER_AGENT,
    HTTP_METHOD_POST,
    HTTP_REQUEST_CONTENT_TYPE,
    HTTP_REQUEST_TIMEOUT_SECONDS,
    HTTP_STATUS_SUCCESS_RANGE_HIGH,
    HTTP_STATUS_SUCCESS_RANGE_LOW,
    HTTP_STATUS_UNPROCESSABLE_ENTITY,
    INLINE_COMMENT_BODY_TEMPLATE,
    INLINE_COMMENT_FIELD_BODY,
    INLINE_COMMENT_FIELD_LINE,
    INLINE_COMMENT_FIELD_PATH,
    INLINE_COMMENT_FIELD_SIDE,
    JSON_FIELD_DESCRIPTION,
    JSON_FIELD_FIX_SUMMARY,
    JSON_FIELD_LINE,
    JSON_FIELD_PATH,
    JSON_FIELD_SEVERITY,
    JSON_FIELD_SIDE,
    MAX_RETRY_ATTEMPTS,
    PLACEHOLDER_DETAILS_BLOCK,
    PLACEHOLDER_FINDINGS_COUNT,
    PLACEHOLDER_HEADING,
    PLACEHOLDER_P0_COUNT,
    PLACEHOLDER_P1_COUNT,
    PLACEHOLDER_P2_COUNT,
    PLACEHOLDER_SKILL,
    PLACEHOLDER_STATE_LABEL,
    PLACEHOLDER_SUMMARY_PARAGRAPH,
    REVIEW_REQUEST_FIELD_BODY,
    REVIEW_REQUEST_FIELD_COMMENTS,
    REVIEW_REQUEST_FIELD_COMMIT_ID,
    REVIEW_REQUEST_FIELD_EVENT,
    REVIEW_RESPONSE_FIELD_HTML_URL,
    REVIEWS_API_PATH_TEMPLATE,
    SELF_APPROVAL_DOWNGRADE_DISCLOSURE_CLEAN,
    SELF_APPROVAL_DOWNGRADE_DISCLOSURE_DIRTY,
    SELF_APPROVAL_DOWNGRADE_STDOUT_MARKER,
    SELF_APPROVAL_REJECTION_MESSAGE_SUBSTRING,
    SEVERITY_TAG_P0,
    SEVERITY_TAG_P1,
    SEVERITY_TAG_P2,
    SHORT_SHA_LENGTH,
    STATE_CLEAN,
    STATE_DIRTY,
    STATE_LABEL_FOR_CLEAN,
    STATE_LABEL_FOR_DIRTY,
    SUMMARY_PARAGRAPH_CLEAN_TEMPLATE,
    SUMMARY_PARAGRAPH_DIRTY_TEMPLATE,
    TEMPLATE_FENCE_TOKEN,
    template_path,
)


class UserInputError(ValueError):
    """Raised on malformed CLI input or findings JSON.

    Surfaces as exit code ``EXIT_CODE_USER_ERROR`` at the entry point.
    """


class RetryExhaustedError(RuntimeError):
    """Raised after four non-2xx responses from the reviews endpoint.

    Four attempts = one initial attempt plus three retries. Surfaces as
    exit code ``EXIT_CODE_RETRY_EXHAUSTED`` at the entry point.
    """


class _SelfApprovalDowngradeSignal(Exception):
    """Internal signal: GitHub rejected a self-authored review; retry as COMMENT.

    Raised inside the POST loop when a 422 carries the self-approval message,
    and caught once by :func:`post_audit_review` to re-post as a COMMENT.
    """


@dataclasses.dataclass(frozen=True)
class AuditFinding:
    """One row of the findings JSON file consumed by ``--findings-json``.

    Mirrors the schema in spec lines 158-169. Frozen so callers cannot
    mutate fields after parsing.
    """

    path: str
    line: int
    side: str
    severity: str
    description: str
    fix_summary: str


@dataclasses.dataclass(frozen=True)
class PostedReview:
    """Result of a successful POST to the reviews endpoint.

    ``html_url`` is the field emitted to stdout per spec line 177;
    ``raw_response_text`` and ``status_code`` are retained for tests and
    logging.
    """

    html_url: str
    raw_response_text: str
    status_code: int


@dataclasses.dataclass(frozen=True)
class ReviewerCredentials:
    """Token for the reviews POST plus whether to downgrade to a COMMENT review.

    ::

        alternate reviewer account found -> ReviewerCredentials(alt_token, False)
        self-PR, no alternate account    -> ReviewerCredentials(author_token, True)

    A ``did_downgrade`` of True tells the caller to post a COMMENT event and
    append the transport disclosure to the review body.
    """

    token: str
    did_downgrade: bool


@dataclasses.dataclass(frozen=True)
class AuditReviewOutcome:
    """A posted review paired with whether the self-approval downgrade fired.

    ::

        direct APPROVE / REQUEST_CHANGES -> AuditReviewOutcome(review, False)
        COMMENT downgrade                -> AuditReviewOutcome(review, True)

    ``main`` prints the marker stdout line only when ``did_downgrade`` is True.
    """

    posted_review: PostedReview
    did_downgrade: bool


class _UserInputArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that raises :class:`UserInputError` on parse errors.

    The stock ``argparse.ArgumentParser.error`` raises ``SystemExit(2)``,
    which collides with ``EXIT_CODE_RETRY_EXHAUSTED``. Routing parse
    failures through :class:`UserInputError` lets the entry point map
    them to ``EXIT_CODE_USER_ERROR`` (exit 1) instead.
    """

    def error(self, message: str) -> NoReturn:
        raise UserInputError(f"argument parsing failed: {message}")


def parse_command_line_arguments(all_arguments: list[str]) -> argparse.Namespace:
    """Parse and validate the script's CLI surface.

    Args:
        all_arguments: ``sys.argv[1:]`` or an equivalent list of strings.

    Returns:
        Namespace with attributes ``skill``, ``owner``, ``repo``,
        ``pr_number``, ``commit``, ``state``, ``findings_json``.

    Raises:
        UserInputError: unrecognized argument, missing required argument,
            or value outside a declared ``choices`` set.
    """
    parser = _UserInputArgumentParser(
        description=(
            "Post an audit review to a draft PR. CLEAN state approves; "
            "DIRTY state requests changes with one inline comment per finding."
        ),
    )
    parser.add_argument(
        CLI_FLAG_SKILL,
        required=True,
        choices=list(ALL_SUPPORTED_SKILLS),
        help="Name of the calling audit skill.",
    )
    parser.add_argument(
        CLI_FLAG_OWNER,
        required=True,
        help="Repository owner (e.g., jl-cmd).",
    )
    parser.add_argument(
        CLI_FLAG_REPO,
        required=True,
        help="Repository name (e.g., claude-dev-env).",
    )
    parser.add_argument(
        CLI_FLAG_PR_NUMBER,
        required=True,
        type=int,
        dest="pr_number",
        help="Pull request number.",
    )
    parser.add_argument(
        CLI_FLAG_COMMIT,
        required=True,
        help="Commit SHA the review attaches to (commit_id field).",
    )
    parser.add_argument(
        CLI_FLAG_STATE,
        required=True,
        choices=list(ALL_SUPPORTED_STATES),
        help="CLEAN approves; DIRTY requests changes.",
    )
    parser.add_argument(
        CLI_FLAG_FINDINGS_JSON,
        required=True,
        type=Path,
        dest="findings_json",
        help="Path to the findings JSON file (empty list for CLEAN).",
    )
    return parser.parse_args(all_arguments)


def _require_string_field(
    all_finding_fields: dict[str, object], field_name: str
) -> str:
    field_value = all_finding_fields.get(field_name)
    if not isinstance(field_value, str):
        raise UserInputError(
            f"finding field {field_name!r} must be a string; "
            f"got {type(field_value).__name__}"
        )
    return field_value


def _require_nonempty_string_field(
    all_finding_fields: dict[str, object], field_name: str
) -> str:
    field_value = _require_string_field(all_finding_fields, field_name)
    if not field_value:
        raise UserInputError(
            f"finding field {field_name!r} must be a non-empty string; got ''"
        )
    return field_value


def _require_int_field(all_finding_fields: dict[str, object], field_name: str) -> int:
    field_value = all_finding_fields.get(field_name)
    if isinstance(field_value, bool) or not isinstance(field_value, int):
        raise UserInputError(
            f"finding field {field_name!r} must be an int; "
            f"got {type(field_value).__name__}"
        )
    return field_value


def parse_findings_json_file(findings_json_path: Path) -> list[AuditFinding]:
    """Parse and validate the findings JSON file.

    Args:
        findings_json_path: Path to a JSON file whose root is a list of
            finding objects matching the schema in the unresolved-thread
            spec.

    Returns:
        List of :class:`AuditFinding`. Empty list when the file contains
        an empty JSON array (used on CLEAN state).

    Raises:
        UserInputError: file missing, not parseable, JSON root not a list,
            entries not dicts, required fields missing or mistyped, path
            empty, or line value below ``1`` (the GitHub reviews API
            rejects ``line=0`` as unprocessable).
    """
    all_raw_entries = _read_findings_root(findings_json_path)
    return [_parse_one_finding(each_entry) for each_entry in all_raw_entries]


def _read_findings_root(findings_json_path: Path) -> list[object]:
    if not findings_json_path.is_file():
        raise UserInputError(
            f"findings-json path not found or not a file: {findings_json_path}"
        )
    findings_text = findings_json_path.read_text(encoding="utf-8")
    try:
        parsed_root: object = json.loads(findings_text)
    except json.JSONDecodeError as decode_error:
        raise UserInputError(
            f"findings-json file is not parseable as JSON: {decode_error}"
        ) from decode_error
    if not isinstance(parsed_root, list):
        raise UserInputError(
            f"findings JSON root must be a list; got {type(parsed_root).__name__}"
        )
    return parsed_root


def _require_all_finding_fields_present(all_entry_fields: dict[str, object]) -> None:
    for each_required_field in ALL_REQUIRED_FINDING_FIELDS:
        if each_required_field not in all_entry_fields:
            raise UserInputError(
                f"finding entry missing required field: {each_required_field!r}"
            )


def _require_supported_severity(all_entry_fields: dict[str, object]) -> str:
    finding_severity = _require_string_field(all_entry_fields, JSON_FIELD_SEVERITY)
    if finding_severity not in ALL_SUPPORTED_SEVERITY_TAGS:
        raise UserInputError(
            f"finding severity {finding_severity!r} not in supported set "
            f"{list(ALL_SUPPORTED_SEVERITY_TAGS)!r}"
        )
    return finding_severity


def _require_supported_side(all_entry_fields: dict[str, object]) -> str:
    finding_side = _require_string_field(all_entry_fields, JSON_FIELD_SIDE)
    if finding_side not in ALL_SUPPORTED_INLINE_COMMENT_SIDES:
        raise UserInputError(
            f"finding side {finding_side!r} not in supported set "
            f"{list(ALL_SUPPORTED_INLINE_COMMENT_SIDES)!r}"
        )
    return finding_side


def _require_positive_line(
    all_entry_fields: dict[str, object], finding_path: str
) -> int:
    finding_line = _require_int_field(all_entry_fields, JSON_FIELD_LINE)
    if finding_line < 1:
        raise UserInputError(
            f"finding field {JSON_FIELD_LINE!r} must be >= 1 (GitHub "
            f"reviews API rejects line=0); got {finding_line} for path "
            f"{finding_path!r}"
        )
    return finding_line


def _parse_one_finding(finding_entry: object) -> AuditFinding:
    if not isinstance(finding_entry, dict):
        raise UserInputError(
            "every findings JSON entry must be an object; got "
            f"{type(finding_entry).__name__}"
        )
    all_entry_fields: dict[str, object] = finding_entry
    _require_all_finding_fields_present(all_entry_fields)
    finding_path = _require_nonempty_string_field(all_entry_fields, JSON_FIELD_PATH)
    return AuditFinding(
        path=finding_path,
        line=_require_positive_line(all_entry_fields, finding_path),
        side=_require_supported_side(all_entry_fields),
        severity=_require_supported_severity(all_entry_fields),
        description=_require_string_field(all_entry_fields, JSON_FIELD_DESCRIPTION),
        fix_summary=_require_string_field(all_entry_fields, JSON_FIELD_FIX_SUMMARY),
    )


def extract_audit_body_skeleton(template_markdown_text: str) -> str:
    """Pull the audit review body skeleton out of the template markdown.

    ::

        <!-- open -->
        ~~~
        <skeleton body with placeholders>   <- captured, markers and fences dropped
        ~~~
        <!-- close -->

    It finds the two HTML comment markers, then captures the fenced block
    between them. Anchoring on explicit markers keeps the contract stable when
    a template edit renames a heading or inserts another fence.

    Args:
        template_markdown_text: Full text of ``audit-reply-template.md``.

    Returns:
        Text between the fence markers, with any leading or trailing
        newlines stripped.

    Raises:
        RuntimeError: open or close marker missing, markers out of order,
            or the marker-bounded region is not a paired fence block.
    """
    open_marker_index = template_markdown_text.find(AUDIT_BODY_SKELETON_OPEN_MARKER)
    if open_marker_index < 0:
        raise RuntimeError(
            f"audit body skeleton open marker not found in template: "
            f"{AUDIT_BODY_SKELETON_OPEN_MARKER!r}"
        )
    region_start = open_marker_index + len(AUDIT_BODY_SKELETON_OPEN_MARKER)
    close_marker_index = template_markdown_text.find(
        AUDIT_BODY_SKELETON_CLOSE_MARKER, region_start
    )
    if close_marker_index < 0:
        raise RuntimeError(
            f"audit body skeleton close marker not found after open marker: "
            f"{AUDIT_BODY_SKELETON_CLOSE_MARKER!r}"
        )
    region_text = template_markdown_text[region_start:close_marker_index]
    fence_open_index = region_text.find(TEMPLATE_FENCE_TOKEN)
    if fence_open_index < 0:
        raise RuntimeError("audit body skeleton marker region has no opening fence")
    skeleton_start = fence_open_index + len(TEMPLATE_FENCE_TOKEN)
    fence_close_index = region_text.find(TEMPLATE_FENCE_TOKEN, skeleton_start)
    if fence_close_index < 0:
        raise RuntimeError("audit body skeleton marker region has no closing fence")
    return region_text[skeleton_start:fence_close_index].strip("\n")


def load_audit_body_skeleton() -> str:
    """Read ``audit-reply-template.md`` and return the audit body skeleton.

    Returns:
        Skeleton text containing the placeholders the body formatter
        substitutes. Reads from disk every call so a docs change picks
        up without restarting the caller.

    Raises:
        RuntimeError: template file missing or malformed.
    """
    template_file_path = template_path()
    if not template_file_path.is_file():
        raise RuntimeError(f"audit-reply-template.md not found at {template_file_path}")
    template_text = template_file_path.read_text(encoding="utf-8")
    return extract_audit_body_skeleton(template_text)


def short_commit_sha(commit_sha: str) -> str:
    """Return the short form of a Git SHA per ``SHORT_SHA_LENGTH``.

    Args:
        commit_sha: Full or already-short Git SHA.

    Returns:
        First ``SHORT_SHA_LENGTH`` characters of the input.
    """
    return commit_sha[:SHORT_SHA_LENGTH]


def skill_display_name(skill_argument: str) -> str:
    """Return the title-cased display form of a skill name.

    Args:
        skill_argument: Lowercase skill identifier (``bugteam``,
            ``findbugs``, ``qbug``).

    Returns:
        Title-cased form for embedding in the review body
        (``Bugteam``, ``Findbugs``, ``Qbug``).
    """
    return skill_argument.title()


def severity_counts_by_tag(
    all_findings: list[AuditFinding],
) -> dict[str, int]:
    """Tally findings by severity tag.

    Args:
        all_findings: Parsed findings list (empty on CLEAN state).

    Returns:
        Mapping with every key in ``ALL_SUPPORTED_SEVERITY_TAGS`` present,
        even when its count is ``0``. Callers can index the result without
        a ``KeyError``.
    """
    counts_by_tag: dict[str, int] = {
        each_tag: 0 for each_tag in ALL_SUPPORTED_SEVERITY_TAGS
    }
    for each_finding in all_findings:
        counts_by_tag[each_finding.severity] += 1
    return counts_by_tag


def build_details_block(all_findings: list[AuditFinding]) -> str:
    """Render the collapsed ``<details>`` block listing every finding.

    Args:
        all_findings: Non-empty list of findings (DIRTY state only).

    Returns:
        Multi-line markdown string wrapped in ``<details>`` / ``</details>``,
        or an empty string when no findings were supplied (CLEAN state).
    """
    if not all_findings:
        return ""
    rendered_bullets = [
        DETAILS_BLOCK_BULLET_TEMPLATE.format(
            severity=each_finding.severity,
            path=each_finding.path,
            line=each_finding.line,
            description=each_finding.description,
        )
        for each_finding in all_findings
    ]
    return (
        DETAILS_BLOCK_HEADER
        + DETAILS_BLOCK_BULLET_SEPARATOR
        + DETAILS_BLOCK_BULLET_SEPARATOR.join(rendered_bullets)
        + DETAILS_BLOCK_FOOTER
    )


def fill_audit_body_skeleton(
    skeleton_text: str,
    skill_argument: str,
    state_argument: str,
    commit_sha: str,
    all_findings: list[AuditFinding],
) -> str:
    """Substitute placeholders in the audit body skeleton with concrete values.

    Args:
        skeleton_text: Skeleton produced by :func:`load_audit_body_skeleton`.
        skill_argument: One of ``ALL_SUPPORTED_SKILLS``.
        state_argument: One of ``ALL_SUPPORTED_STATES``.
        commit_sha: Full SHA of the commit the review attaches to.
        all_findings: Parsed findings list.

    Returns:
        Markdown body string ready to send as the ``body`` field of the
        reviews POST payload.
    """
    display_skill = skill_display_name(skill_argument)
    short_commit = short_commit_sha(commit_sha)
    counts_by_tag = severity_counts_by_tag(all_findings)
    is_clean = state_argument == STATE_CLEAN
    state_label = STATE_LABEL_FOR_CLEAN if is_clean else STATE_LABEL_FOR_DIRTY
    heading_text = HEADING_FOR_CLEAN if is_clean else HEADING_FOR_DIRTY
    summary_template = (
        SUMMARY_PARAGRAPH_CLEAN_TEMPLATE
        if is_clean
        else SUMMARY_PARAGRAPH_DIRTY_TEMPLATE
    )
    summary_paragraph_text = summary_template.format(
        skill_display=display_skill,
        short_commit=short_commit,
        findings_count=len(all_findings),
    )
    details_block_text = "" if is_clean else build_details_block(all_findings)
    placeholder_replacements: list[tuple[str, str]] = [
        (PLACEHOLDER_SKILL, display_skill),
        (PLACEHOLDER_STATE_LABEL, state_label),
        (PLACEHOLDER_HEADING, heading_text),
        (PLACEHOLDER_SUMMARY_PARAGRAPH, summary_paragraph_text),
        (PLACEHOLDER_FINDINGS_COUNT, str(len(all_findings))),
        (PLACEHOLDER_P0_COUNT, str(counts_by_tag[SEVERITY_TAG_P0])),
        (PLACEHOLDER_P1_COUNT, str(counts_by_tag[SEVERITY_TAG_P1])),
        (PLACEHOLDER_P2_COUNT, str(counts_by_tag[SEVERITY_TAG_P2])),
        (PLACEHOLDER_DETAILS_BLOCK, details_block_text),
    ]
    filled_text = skeleton_text
    for each_placeholder, each_replacement in placeholder_replacements:
        filled_text = filled_text.replace(each_placeholder, each_replacement)
    return filled_text


def build_inline_comments_payload(
    skill_argument: str,
    all_findings: list[AuditFinding],
) -> list[dict[str, object]]:
    """Render the findings list as a GitHub reviews ``comments[]`` payload.

    Args:
        skill_argument: One of ``ALL_SUPPORTED_SKILLS``; embedded in each
            comment's body text.
        all_findings: Findings to render (empty list on CLEAN state).

    Returns:
        List of dictionaries matching the GitHub API shape for inline
        review comments: ``path``, ``line``, ``side``, ``body``.
    """
    display_skill = skill_display_name(skill_argument)
    rendered_comments: list[dict[str, object]] = []
    for each_finding in all_findings:
        comment_body_text = INLINE_COMMENT_BODY_TEMPLATE.format(
            severity=each_finding.severity,
            skill_display=display_skill,
            description=each_finding.description,
            fix_summary=each_finding.fix_summary,
        )
        rendered_comments.append(
            {
                INLINE_COMMENT_FIELD_PATH: each_finding.path,
                INLINE_COMMENT_FIELD_LINE: each_finding.line,
                INLINE_COMMENT_FIELD_SIDE: each_finding.side,
                INLINE_COMMENT_FIELD_BODY: comment_body_text,
            }
        )
    return rendered_comments


def review_event_for_state(state_argument: str, did_downgrade: bool) -> str:
    """Return the GitHub API ``event`` string for an audit state.

    A downgrade posts COMMENT whatever the state. Otherwise CLEAN maps to
    APPROVE and DIRTY to REQUEST_CHANGES.

    Args:
        state_argument: One of ``ALL_SUPPORTED_STATES``.
        did_downgrade: True when the self-approval downgrade is in effect.

    Returns:
        ``COMMENT`` on a downgrade, else ``APPROVE`` for CLEAN and
        ``REQUEST_CHANGES`` for DIRTY.

    Raises:
        UserInputError: state outside the supported set.
    """
    if state_argument not in ALL_SUPPORTED_STATES:
        raise UserInputError(
            f"state {state_argument!r} not in supported set {list(ALL_SUPPORTED_STATES)!r}"
        )
    if did_downgrade:
        return GITHUB_REVIEW_EVENT_COMMENT
    if state_argument == STATE_CLEAN:
        return GITHUB_REVIEW_EVENT_APPROVE
    return GITHUB_REVIEW_EVENT_REQUEST_CHANGES


def build_review_request_payload(
    state_argument: str,
    commit_sha: str,
    review_body_text: str,
    all_inline_comments: list[dict[str, object]],
    did_downgrade: bool,
) -> dict[str, object]:
    """Assemble the JSON payload sent to the reviews endpoint.

    Args:
        state_argument: One of ``ALL_SUPPORTED_STATES``.
        commit_sha: SHA bound into ``commit_id``.
        review_body_text: Already-formatted review body.
        all_inline_comments: Output of :func:`build_inline_comments_payload`;
            empty list on CLEAN state.
        did_downgrade: True when the self-approval downgrade is in effect, which
            posts the review as a COMMENT event.

    Returns:
        Dictionary suitable for ``json.dumps`` and sending as the request
        body to ``POST /repos/{owner}/{repo}/pulls/{N}/reviews``.
    """
    return {
        REVIEW_REQUEST_FIELD_COMMIT_ID: commit_sha,
        REVIEW_REQUEST_FIELD_BODY: review_body_text,
        REVIEW_REQUEST_FIELD_EVENT: review_event_for_state(
            state_argument, did_downgrade
        ),
        REVIEW_REQUEST_FIELD_COMMENTS: all_inline_comments,
    }


def append_self_approval_disclosure(review_body_text: str, state_argument: str) -> str:
    """Append the transport disclosure to the review body on the downgrade path.

    The disclosure is appended, never prepended, so the clean-audit gate still
    reads the label off the body's first line.

    Args:
        review_body_text: The formatted review body.
        state_argument: One of ``ALL_SUPPORTED_STATES``; selects the CLEAN or
            DIRTY disclosure sentence.

    Returns:
        The body with a blank line and the state's disclosure sentence appended.
    """
    disclosure_sentence = (
        SELF_APPROVAL_DOWNGRADE_DISCLOSURE_CLEAN
        if state_argument == STATE_CLEAN
        else SELF_APPROVAL_DOWNGRADE_DISCLOSURE_DIRTY
    )
    return review_body_text + DISCLOSURE_BODY_SEPARATOR + disclosure_sentence


def _assemble_review_request_fields(
    skeleton_text: str,
    parsed_arguments: argparse.Namespace,
    all_findings: list[AuditFinding],
    did_downgrade: bool,
) -> dict[str, object]:
    review_body_text = fill_audit_body_skeleton(
        skeleton_text=skeleton_text,
        skill_argument=parsed_arguments.skill,
        state_argument=parsed_arguments.state,
        commit_sha=parsed_arguments.commit,
        all_findings=all_findings,
    )
    if did_downgrade:
        review_body_text = append_self_approval_disclosure(
            review_body_text, parsed_arguments.state
        )
    inline_comments_payload = (
        []
        if parsed_arguments.state == STATE_CLEAN
        else build_inline_comments_payload(parsed_arguments.skill, all_findings)
    )
    return build_review_request_payload(
        state_argument=parsed_arguments.state,
        commit_sha=parsed_arguments.commit,
        review_body_text=review_body_text,
        all_inline_comments=inline_comments_payload,
        did_downgrade=did_downgrade,
    )


def resolve_github_token() -> str:
    """Return the GitHub token to authenticate the reviews POST with.

    Precedence (first non-empty wins):
        - ``GH_TOKEN`` env var
        - ``GITHUB_TOKEN`` env var
        - ``gh auth token`` (current active ``gh`` account)

    Returns:
        Token string, stripped of trailing whitespace.

    Raises:
        UserInputError: every source above failed or returned empty.
    """
    env_token = _first_env_token()
    if env_token:
        return env_token
    try:
        completion = subprocess.run(
            list(ALL_GH_AUTH_TOKEN_COMMAND_PARTS),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError as missing_gh_error:
        raise UserInputError(
            "`gh` CLI not installed or not on PATH; cannot resolve a GitHub token"
        ) from missing_gh_error
    if completion.returncode != 0:
        raise UserInputError(
            f"`gh auth token` failed (exit {completion.returncode}): "
            f"{completion.stderr.strip()}"
        )
    token_text = completion.stdout.strip()
    if not token_text:
        raise UserInputError("`gh auth token` returned empty output")
    return token_text


def query_active_gh_user_login() -> str:
    """Return the login of the gh account that owns the current ``gh auth token``.

    Calls ``gh api /user`` and reads ``.login`` off the response. The result
    is the gh CLI's currently active account — the one whose token a default
    ``gh auth token`` call would emit.

    Returns:
        Login string of the active github.com account.

    Raises:
        UserInputError: ``gh`` not on PATH, the ``gh api /user`` call fails,
            or the response is missing a string ``login`` field.
    """
    try:
        completion = subprocess.run(
            list(ALL_GH_API_USER_COMMAND_PARTS),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError as missing_gh_error:
        raise UserInputError(
            "`gh` CLI not installed or not on PATH; cannot query the active "
            "github.com account login"
        ) from missing_gh_error
    if completion.returncode != 0:
        raise UserInputError(
            f"`gh api /user` failed (exit {completion.returncode}): "
            f"{completion.stderr.strip()}"
        )
    try:
        parsed_value: object = json.loads(completion.stdout)
    except json.JSONDecodeError as decode_error:
        raise UserInputError(
            f"`gh api /user` response not parseable as JSON: {decode_error}"
        ) from decode_error
    if not isinstance(parsed_value, dict):
        raise UserInputError(
            f"`gh api /user` response root must be an object; "
            f"got {type(parsed_value).__name__}"
        )
    typed_response: dict[str, object] = parsed_value
    login_value = typed_response.get(GH_USER_LOGIN_FIELD)
    if not isinstance(login_value, str) or not login_value:
        raise UserInputError(
            f"`gh api /user` response missing string {GH_USER_LOGIN_FIELD!r}"
        )
    return login_value


def query_pull_request_author_login(owner: str, repo: str, pr_number: int) -> str:
    """Return the login of the user who authored a pull request.

    Calls ``gh api /repos/{owner}/{repo}/pulls/{N}`` and reads ``.user.login``
    off the response.

    Args:
        owner: Repository owner slug.
        repo: Repository name slug.
        pr_number: Pull request number.

    Returns:
        Login string of the PR author.

    Raises:
        UserInputError: ``gh api`` call fails, response malformed, or the
            nested ``user.login`` field is missing.
    """
    pull_request_api_path = GH_API_PR_PATH_TEMPLATE.format(
        owner=owner,
        repo=repo,
        pr_number=pr_number,
    )
    try:
        completion = subprocess.run(
            list(ALL_GH_API_COMMAND_PARTS) + [pull_request_api_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError as missing_gh_error:
        raise UserInputError(
            "`gh` CLI not installed or not on PATH; cannot query the PR author login"
        ) from missing_gh_error
    if completion.returncode != 0:
        raise UserInputError(
            f"`gh api {pull_request_api_path}` failed (exit "
            f"{completion.returncode}): {completion.stderr.strip()}"
        )
    try:
        parsed_value: object = json.loads(completion.stdout)
    except json.JSONDecodeError as decode_error:
        raise UserInputError(
            f"`gh api {pull_request_api_path}` response not parseable as "
            f"JSON: {decode_error}"
        ) from decode_error
    if not isinstance(parsed_value, dict):
        raise UserInputError(
            f"`gh api {pull_request_api_path}` response root must be an "
            f"object; got {type(parsed_value).__name__}"
        )
    typed_response: dict[str, object] = parsed_value
    user_field = typed_response.get(GH_PR_USER_FIELD)
    if not isinstance(user_field, dict):
        raise UserInputError(f"PR response missing object {GH_PR_USER_FIELD!r}")
    typed_user: dict[str, object] = user_field
    login_value = typed_user.get(GH_USER_LOGIN_FIELD)
    if not isinstance(login_value, str) or not login_value:
        raise UserInputError(f"PR author missing string {GH_USER_LOGIN_FIELD!r} field")
    return login_value


def list_authenticated_gh_account_logins() -> list[str]:
    """Return every github.com account login currently authenticated via gh.

    Parses ``gh auth status`` output line-by-line. The CLI writes its
    human-readable status to stderr by default; the function reads both
    stdout and stderr to be resilient to the gh version in use.

    Returns:
        List of login strings in the order ``gh auth status`` reports them.
        Empty list when no accounts are logged in.

    Raises:
        UserInputError: ``gh`` not on PATH.
    """
    try:
        completion = subprocess.run(
            list(ALL_GH_AUTH_STATUS_COMMAND_PARTS),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError as missing_gh_error:
        raise UserInputError(
            "`gh` CLI not installed or not on PATH; cannot list "
            "authenticated github.com accounts"
        ) from missing_gh_error
    output_text = (completion.stdout or "") + (completion.stderr or "")
    parsed_logins: list[str] = []
    for each_line in output_text.splitlines():
        marker_index = each_line.find(GH_AUTH_STATUS_ACCOUNT_LINE_MARKER)
        if marker_index < 0:
            continue
        remainder = each_line[
            marker_index + len(GH_AUTH_STATUS_ACCOUNT_LINE_MARKER) :
        ].strip()
        space_index = remainder.find(GH_AUTH_STATUS_ACCOUNT_LINE_TOKEN_SEPARATOR)
        login_candidate = remainder[:space_index] if space_index >= 0 else remainder
        if login_candidate and login_candidate not in parsed_logins:
            parsed_logins.append(login_candidate)
    return parsed_logins


def fetch_gh_token_for_account(account_login: str) -> str:
    """Return the cached gh token for a specific authenticated account.

    Calls ``gh auth token --user <login>``. Does not mutate which account
    is "active" in the gh CLI; only retrieves a stored token.

    Args:
        account_login: github.com login whose token should be returned.

    Returns:
        Cached gh token string, stripped of trailing whitespace.

    Raises:
        UserInputError: ``gh`` not on PATH, the call fails, or it returns
            empty output.
    """
    try:
        completion = subprocess.run(
            list(ALL_GH_AUTH_TOKEN_COMMAND_PARTS)
            + [GH_AUTH_TOKEN_USER_FLAG, account_login],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError as missing_gh_error:
        raise UserInputError(
            f"`gh` CLI not installed or not on PATH; cannot fetch token "
            f"for account {account_login!r}"
        ) from missing_gh_error
    if completion.returncode != 0:
        raise UserInputError(
            f"`gh auth token --user {account_login}` failed (exit "
            f"{completion.returncode}): {completion.stderr.strip()}"
        )
    token_text = completion.stdout.strip()
    if not token_text:
        raise UserInputError(
            f"`gh auth token --user {account_login}` returned empty output"
        )
    return token_text


def resolve_reviewer_credentials(
    owner: str, repo: str, pr_number: int
) -> ReviewerCredentials:
    """Return the reviews-POST token and whether to downgrade to a COMMENT review.

    An env token or an alternate reviewer account posts a direct review. A
    self-PR with no alternate account downgrades to a COMMENT review on the
    author's own token, so a single-account author still converges.

    Args:
        owner: Repository owner slug.
        repo: Repository name slug.
        pr_number: Pull request number whose author decides the swap or downgrade.

    Returns:
        A :class:`ReviewerCredentials` with the token and the downgrade flag.

    Raises:
        UserInputError: a pinned ``BUGTEAM_REVIEWER_ACCOUNT`` is not an
            authenticated alternate, or an underlying gh query fails.
    """
    env_token = _first_env_token()
    if env_token:
        return ReviewerCredentials(token=env_token, did_downgrade=False)
    pr_author_login = query_pull_request_author_login(owner, repo, pr_number)
    if query_active_gh_user_login().lower() != pr_author_login.lower():
        return ReviewerCredentials(token=resolve_github_token(), did_downgrade=False)
    return _self_pr_credentials(pr_author_login)


def _first_env_token() -> str:
    for each_env_var_name in ALL_GH_TOKEN_ENV_VAR_NAMES:
        env_token = os.environ.get(each_env_var_name, "").strip()
        if env_token:
            return env_token
    return ""


def _alternate_reviewer_logins(pr_author_login: str) -> list[str]:
    all_authenticated_logins = list_authenticated_gh_account_logins()
    return [
        each_login
        for each_login in all_authenticated_logins
        if each_login.lower() != pr_author_login.lower()
    ]


def _self_pr_credentials(pr_author_login: str) -> ReviewerCredentials:
    all_alternate_logins = _alternate_reviewer_logins(pr_author_login)
    if not all_alternate_logins:
        return ReviewerCredentials(token=resolve_github_token(), did_downgrade=True)
    pinned_reviewer_account = os.environ.get(
        BUGTEAM_REVIEWER_ACCOUNT_ENV_VAR_NAME, ""
    ).strip()
    if pinned_reviewer_account:
        return _credentials_for_pinned_account(
            pinned_reviewer_account, all_alternate_logins, pr_author_login
        )
    return ReviewerCredentials(
        token=fetch_gh_token_for_account(all_alternate_logins[0]), did_downgrade=False
    )


def _credentials_for_pinned_account(
    pinned_reviewer_account: str,
    all_alternate_logins: list[str],
    pr_author_login: str,
) -> ReviewerCredentials:
    matching_pinned_account = next(
        (
            each_login
            for each_login in all_alternate_logins
            if each_login.lower() == pinned_reviewer_account.lower()
        ),
        None,
    )
    if matching_pinned_account is None:
        raise UserInputError(
            f"Self-PR detected and "
            f"{BUGTEAM_REVIEWER_ACCOUNT_ENV_VAR_NAME}="
            f"{pinned_reviewer_account!r} is set, but that account is "
            f"not in the alternate-reviewer set "
            f"{all_alternate_logins!r} (PR author "
            f"{pr_author_login!r} is excluded). Run `gh auth login` "
            f"for {pinned_reviewer_account!r} or unset the env var to "
            f"fall back to the first alternate account."
        )
    return ReviewerCredentials(
        token=fetch_gh_token_for_account(matching_pinned_account), did_downgrade=False
    )


def build_reviews_endpoint_url(owner: str, repo: str, pr_number: int) -> str:
    """Compose the full reviews-endpoint URL for a PR.

    Args:
        owner: Repository owner.
        repo: Repository name.
        pr_number: Pull request number.

    Returns:
        Full URL string ready to pass to :class:`urllib.request.Request`.
    """
    api_path = REVIEWS_API_PATH_TEMPLATE.format(
        owner=owner,
        repo=repo,
        pr_number=pr_number,
    )
    return f"{GITHUB_API_BASE_URL}{api_path}"


def _build_authenticated_request(
    endpoint_url: str,
    token: str,
    all_request_fields: dict[str, object],
) -> urllib.request.Request:
    encoded_body = json.dumps(all_request_fields).encode("utf-8")
    request_object = urllib.request.Request(
        url=endpoint_url,
        data=encoded_body,
        method=HTTP_METHOD_POST,
    )
    request_object.add_header(
        HTTP_HEADER_AUTHORIZATION, f"{HTTP_AUTHORIZATION_BEARER_PREFIX}{token}"
    )
    request_object.add_header(HTTP_HEADER_ACCEPT, GITHUB_API_ACCEPT_HEADER)
    request_object.add_header(HTTP_HEADER_CONTENT_TYPE, HTTP_REQUEST_CONTENT_TYPE)
    request_object.add_header(HTTP_HEADER_GITHUB_API_VERSION, GITHUB_API_VERSION_HEADER)
    request_object.add_header(HTTP_HEADER_USER_AGENT, GITHUB_API_USER_AGENT)
    return request_object


def execute_review_post_attempt(
    endpoint_url: str,
    token: str,
    all_request_fields: dict[str, object],
) -> tuple[int, str]:
    """Make one HTTP POST to the reviews endpoint and return its outcome.

    Args:
        endpoint_url: Full URL produced by :func:`build_reviews_endpoint_url`.
        token: GitHub token string.
        all_request_fields: Payload produced by :func:`build_review_request_payload`.

    Returns:
        Tuple ``(status_code, response_body_text)``. ``status_code`` is the
        HTTP status; ``response_body_text`` is the decoded response body.
        Client- and server-error responses are returned through this path
        (not raised) so the retry loop can decide whether to back off.

    Raises:
        urllib.error.URLError: transport-level failure (no DNS, no TCP).
    """
    request_object = _build_authenticated_request(
        endpoint_url, token, all_request_fields
    )
    try:
        with urllib.request.urlopen(
            request_object, timeout=HTTP_REQUEST_TIMEOUT_SECONDS
        ) as response_object:
            response_body = response_object.read().decode("utf-8", errors="replace")
            return response_object.status, response_body
    except urllib.error.HTTPError as http_error:
        error_body_text = http_error.read().decode("utf-8", errors="replace")
        return http_error.code, error_body_text


def _extract_top_level_message(error_body_text: str) -> str | None:
    try:
        parsed_error: object = json.loads(error_body_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed_error, dict):
        return None
    typed_error: dict[str, object] = parsed_error
    top_level_message = typed_error.get(GH_ERROR_MESSAGE_FIELD)
    if not isinstance(top_level_message, str):
        return None
    return top_level_message


def _raise_for_unprocessable_review(
    error_body_text: str, should_downgrade_on_self_approval: bool
) -> NoReturn:
    top_level_message = _extract_top_level_message(error_body_text)
    is_self_approval_rejection = (
        top_level_message is not None
        and SELF_APPROVAL_REJECTION_MESSAGE_SUBSTRING.casefold()
        in top_level_message.casefold()
    )
    if is_self_approval_rejection and should_downgrade_on_self_approval:
        raise _SelfApprovalDowngradeSignal(top_level_message)
    raise RetryExhaustedError(
        f"reviews POST rejected as unprocessable "
        f"({HTTP_STATUS_UNPROCESSABLE_ENTITY}); GitHub response body: "
        f"{error_body_text}"
    )


def post_review_with_retries(
    endpoint_url: str,
    token: str,
    all_request_fields: dict[str, object],
    should_downgrade_on_self_approval: bool,
) -> PostedReview:
    """POST the review with retries on non-success outcomes.

    Backoffs between attempts come from ``ALL_RETRY_BACKOFF_SECONDS``. A 422 is
    taken out of the ladder: a self-approval 422 signals a COMMENT downgrade,
    and any other 422 raises at once with GitHub's message.

    Args:
        endpoint_url: Full URL produced by :func:`build_reviews_endpoint_url`.
        token: GitHub token string.
        all_request_fields: Payload produced by :func:`build_review_request_payload`.
        should_downgrade_on_self_approval: True on the first POST, so a self-approval
            422 signals a downgrade rather than raising.

    Returns:
        :class:`PostedReview` carrying the response's ``html_url``, raw
        body, and status code.

    Raises:
        RetryExhaustedError: every attempt across the four-attempt loop
            returned a non-2xx response, raised a transport-level
            :class:`urllib.error.URLError`, produced a 2xx response whose body
            could not be parsed for ``html_url``, or a non-downgrade 422.
        _SelfApprovalDowngradeSignal: a self-approval 422 while
            ``should_downgrade_on_self_approval`` is True.
    """
    last_status_code: int = 0
    last_response_text: str = ""
    total_attempts = MAX_RETRY_ATTEMPTS + 1
    for each_attempt_index in range(total_attempts):
        try:
            status_code, response_text = execute_review_post_attempt(
                endpoint_url, token, all_request_fields
            )
        except urllib.error.URLError as transport_error:
            status_code = 0
            response_text = f"transport-level URLError: {transport_error.reason!r}"
        last_status_code = status_code
        last_response_text = response_text
        if status_code == HTTP_STATUS_UNPROCESSABLE_ENTITY:
            _raise_for_unprocessable_review(
                response_text, should_downgrade_on_self_approval
            )
        is_success = (
            HTTP_STATUS_SUCCESS_RANGE_LOW
            <= status_code
            < HTTP_STATUS_SUCCESS_RANGE_HIGH
        )
        if is_success:
            try:
                html_url_value = extract_html_url_field(response_text)
            except RuntimeError as malformed_body_error:
                raise RetryExhaustedError(
                    f"reviews POST returned {status_code} but the response body "
                    f"was unusable: {malformed_body_error}; "
                    f"body={response_text[:ERROR_RESPONSE_PREVIEW_CHARS]!r}"
                ) from malformed_body_error
            return PostedReview(
                html_url=html_url_value,
                raw_response_text=response_text,
                status_code=status_code,
            )
        is_last_attempt = each_attempt_index == MAX_RETRY_ATTEMPTS
        if is_last_attempt:
            break
        time.sleep(ALL_RETRY_BACKOFF_SECONDS[each_attempt_index])
    raise RetryExhaustedError(
        f"reviews POST failed after {total_attempts} attempts; "
        f"last status={last_status_code}; "
        f"last body={last_response_text[:ERROR_RESPONSE_PREVIEW_CHARS]!r}"
    )


def extract_html_url_field(response_text: str) -> str:
    """Pull the ``html_url`` field out of a successful reviews POST response.

    Args:
        response_text: Decoded response body.

    Returns:
        Value of the ``html_url`` field.

    Raises:
        RuntimeError: response is not JSON, root is not an object, or
            ``html_url`` is missing or not a string.
    """
    try:
        parsed_value: object = json.loads(response_text)
    except json.JSONDecodeError as decode_error:
        raise RuntimeError(
            f"review response is not parseable as JSON: {decode_error}"
        ) from decode_error
    if not isinstance(parsed_value, dict):
        raise RuntimeError(
            f"review response root is not an object; got {type(parsed_value).__name__}"
        )
    typed_response: dict[str, object] = parsed_value
    html_url_value = typed_response.get(REVIEW_RESPONSE_FIELD_HTML_URL)
    if not isinstance(html_url_value, str):
        raise RuntimeError(
            f"review response missing string {REVIEW_RESPONSE_FIELD_HTML_URL!r}"
        )
    return html_url_value


def _validate_state_matches_findings(
    state_argument: str, all_findings: list[AuditFinding]
) -> None:
    is_clean_state = state_argument == STATE_CLEAN
    if is_clean_state and all_findings:
        raise UserInputError(
            f"state {STATE_CLEAN} requires an empty findings list; got "
            f"{len(all_findings)} finding(s)"
        )
    if not is_clean_state and not all_findings:
        raise UserInputError(
            f"state {STATE_DIRTY} requires at least one finding; got an "
            f"empty findings list"
        )


def _load_skeleton_or_raise_user_error() -> str:
    try:
        return load_audit_body_skeleton()
    except RuntimeError as template_error:
        raise UserInputError(
            f"audit-reply-template.md misconfigured: {template_error}"
        ) from template_error


def _post_review_resolving_self_approval(
    endpoint_url: str,
    credentials: ReviewerCredentials,
    skeleton_text: str,
    parsed_arguments: argparse.Namespace,
    all_findings: list[AuditFinding],
) -> AuditReviewOutcome:
    did_downgrade = credentials.did_downgrade
    request_fields = _assemble_review_request_fields(
        skeleton_text, parsed_arguments, all_findings, did_downgrade
    )
    try:
        posted_review = post_review_with_retries(
            endpoint_url,
            credentials.token,
            request_fields,
            should_downgrade_on_self_approval=not did_downgrade,
        )
    except _SelfApprovalDowngradeSignal:
        request_fields = _assemble_review_request_fields(
            skeleton_text, parsed_arguments, all_findings, did_downgrade=True
        )
        posted_review = post_review_with_retries(
            endpoint_url,
            credentials.token,
            request_fields,
            should_downgrade_on_self_approval=False,
        )
        did_downgrade = True
    return AuditReviewOutcome(posted_review=posted_review, did_downgrade=did_downgrade)


def post_audit_review(parsed_arguments: argparse.Namespace) -> AuditReviewOutcome:
    """Top-level pipeline: load findings, build body, POST, return the outcome.

    Args:
        parsed_arguments: Output of :func:`parse_command_line_arguments`.

    Returns:
        :class:`AuditReviewOutcome` carrying the posted review and whether the
        self-approval COMMENT downgrade fired.

    Raises:
        UserInputError: bad CLI argument, malformed findings JSON, a state
            inconsistent with the findings list, a missing ``gh`` CLI, a gh
            query failure, or ``audit-reply-template.md`` misconfigured.
        RetryExhaustedError: every retry failed, or a non-downgrade 422.
    """
    all_findings = parse_findings_json_file(parsed_arguments.findings_json)
    _validate_state_matches_findings(parsed_arguments.state, all_findings)
    skeleton_text = _load_skeleton_or_raise_user_error()
    credentials = resolve_reviewer_credentials(
        owner=parsed_arguments.owner,
        repo=parsed_arguments.repo,
        pr_number=parsed_arguments.pr_number,
    )
    endpoint_url = build_reviews_endpoint_url(
        owner=parsed_arguments.owner,
        repo=parsed_arguments.repo,
        pr_number=parsed_arguments.pr_number,
    )
    return _post_review_resolving_self_approval(
        endpoint_url, credentials, skeleton_text, parsed_arguments, all_findings
    )


def main(all_arguments: list[str]) -> int:
    """Entry-point. Returns the process exit code.

    Args:
        all_arguments: ``sys.argv[1:]`` or equivalent.

    Returns:
        ``0`` on success (prints the review ``html_url``, plus a second marker
        line on a self-approval downgrade),
        ``EXIT_CODE_USER_ERROR`` on user input failure,
        ``EXIT_CODE_RETRY_EXHAUSTED`` on retry exhaustion.
    """
    try:
        parsed_arguments = parse_command_line_arguments(all_arguments)
        review_outcome = post_audit_review(parsed_arguments)
    except UserInputError as user_error:
        print(f"post_audit_thread: {user_error}", file=sys.stderr)
        return EXIT_CODE_USER_ERROR
    except RetryExhaustedError as retry_error:
        print(f"post_audit_thread: {retry_error}", file=sys.stderr)
        return EXIT_CODE_RETRY_EXHAUSTED
    stdout_text = review_outcome.posted_review.html_url
    if review_outcome.did_downgrade:
        stdout_text = f"{stdout_text}\n{SELF_APPROVAL_DOWNGRADE_STDOUT_MARKER}"
    print(stdout_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
