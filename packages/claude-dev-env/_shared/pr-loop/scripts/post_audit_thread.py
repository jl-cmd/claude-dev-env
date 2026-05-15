"""Post an audit review (APPROVE / REQUEST_CHANGES) to a draft PR.

Consumed by ``/bugteam``, ``/findbugs``, and ``/qbug`` at the end of every
audit invocation. Posts to ``/repos/{owner}/{repo}/pulls/{N}/reviews`` with
``commit_id=<SHA>``, a formatted body, and inline ``comments[]`` derived
from a findings JSON file. CLEAN state ``→`` APPROVE with empty
``comments[]``; DIRTY state ``→`` REQUEST_CHANGES with one inline comment
per finding so each becomes its own resolvable thread.

The body skeleton is read at runtime from ``audit-reply-template.md`` (the
canonical reference doc shipped in Phase 1) so the template stays the
single source of truth for the review-body shape.

Exit codes per spec:
- ``0`` on success (POSTs the new review's ``html_url`` to stdout)
- ``1`` on user error (bad CLI arguments, malformed findings JSON)
- ``2`` on retry exhaustion (four non-2xx responses — one initial attempt
  plus three retries) — hard blocker
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

sys.modules.pop("config", None)
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.post_audit_thread_constants import (
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
    CLI_FLAG_COMMIT,
    CLI_FLAG_FINDINGS_JSON,
    CLI_FLAG_OWNER,
    CLI_FLAG_PR_NUMBER,
    CLI_FLAG_REPO,
    CLI_FLAG_SKILL,
    CLI_FLAG_STATE,
    DETAILS_BLOCK_BULLET_TEMPLATE,
    DETAILS_BLOCK_FOOTER,
    DETAILS_BLOCK_HEADER,
    ERROR_RESPONSE_PREVIEW_CHARS,
    EXIT_CODE_RETRY_EXHAUSTED,
    EXIT_CODE_USER_ERROR,
    GITHUB_API_ACCEPT_HEADER,
    GITHUB_API_BASE_URL,
    GITHUB_API_USER_AGENT,
    GITHUB_API_VERSION_HEADER,
    GITHUB_REVIEW_EVENT_APPROVE,
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
        help="Repository name (e.g., claude-code-config).",
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


def _require_int_field(
    all_finding_fields: dict[str, object], field_name: str
) -> int:
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
    if not findings_json_path.is_file():
        raise UserInputError(
            f"findings-json path not found or not a file: {findings_json_path}"
        )
    findings_text = findings_json_path.read_text(encoding="utf-8")
    try:
        parsed_value: object = json.loads(findings_text)
    except json.JSONDecodeError as decode_error:
        raise UserInputError(
            f"findings-json file is not parseable as JSON: {decode_error}"
        ) from decode_error
    if not isinstance(parsed_value, list):
        raise UserInputError(
            f"findings JSON root must be a list; got {type(parsed_value).__name__}"
        )
    parsed_findings: list[AuditFinding] = []
    for each_entry in parsed_value:
        if not isinstance(each_entry, dict):
            raise UserInputError(
                "every findings JSON entry must be an object; got "
                f"{type(each_entry).__name__}"
            )
        all_entry_fields: dict[str, object] = each_entry
        for each_required_field in ALL_REQUIRED_FINDING_FIELDS:
            if each_required_field not in all_entry_fields:
                raise UserInputError(
                    f"finding entry missing required field: {each_required_field!r}"
                )
        severity_value = _require_string_field(all_entry_fields, JSON_FIELD_SEVERITY)
        if severity_value not in ALL_SUPPORTED_SEVERITY_TAGS:
            raise UserInputError(
                f"finding severity {severity_value!r} not in supported set "
                f"{list(ALL_SUPPORTED_SEVERITY_TAGS)!r}"
            )
        side_value = _require_string_field(all_entry_fields, JSON_FIELD_SIDE)
        if side_value not in ALL_SUPPORTED_INLINE_COMMENT_SIDES:
            raise UserInputError(
                f"finding side {side_value!r} not in supported set "
                f"{list(ALL_SUPPORTED_INLINE_COMMENT_SIDES)!r}"
            )
        path_value = _require_nonempty_string_field(all_entry_fields, JSON_FIELD_PATH)
        line_value = _require_int_field(all_entry_fields, JSON_FIELD_LINE)
        if line_value < 1:
            raise UserInputError(
                f"finding field {JSON_FIELD_LINE!r} must be >= 1 (GitHub "
                f"reviews API rejects line=0); got {line_value} for path "
                f"{path_value!r}"
            )
        parsed_findings.append(
            AuditFinding(
                path=path_value,
                line=line_value,
                side=side_value,
                severity=severity_value,
                description=_require_string_field(all_entry_fields, JSON_FIELD_DESCRIPTION),
                fix_summary=_require_string_field(all_entry_fields, JSON_FIELD_FIX_SUMMARY),
            )
        )
    return parsed_findings


def extract_audit_body_skeleton(template_markdown_text: str) -> str:
    """Pull the audit review body skeleton out of the Phase 1 template markdown.

    Locates the explicit HTML comment markers
    ``AUDIT_BODY_SKELETON_OPEN_MARKER`` and
    ``AUDIT_BODY_SKELETON_CLOSE_MARKER`` in the template, then captures
    the fenced block (delimited by the token in ``TEMPLATE_FENCE_TOKEN``)
    sitting between them. The captured text contains the placeholders the
    rest of this script substitutes. Anchoring on explicit markers — not on
    heading text or "the next fence after a heading" — keeps the contract
    stable across template edits that rename headings, insert new fences,
    or change fence syntax.

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
        raise RuntimeError(
            "audit body skeleton marker region has no opening fence"
        )
    skeleton_start = fence_open_index + len(TEMPLATE_FENCE_TOKEN)
    fence_close_index = region_text.find(TEMPLATE_FENCE_TOKEN, skeleton_start)
    if fence_close_index < 0:
        raise RuntimeError(
            "audit body skeleton marker region has no closing fence"
        )
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
        DETAILS_BLOCK_HEADER + "\n" + "\n".join(rendered_bullets) + DETAILS_BLOCK_FOOTER
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


def review_event_for_state(state_argument: str) -> str:
    """Return the GitHub API ``event`` string for an audit state.

    Args:
        state_argument: One of ``ALL_SUPPORTED_STATES``.

    Returns:
        ``APPROVE`` for CLEAN, ``REQUEST_CHANGES`` for DIRTY.

    Raises:
        UserInputError: state outside the supported set.
    """
    if state_argument == STATE_CLEAN:
        return GITHUB_REVIEW_EVENT_APPROVE
    if state_argument == STATE_DIRTY:
        return GITHUB_REVIEW_EVENT_REQUEST_CHANGES
    raise UserInputError(
        f"state {state_argument!r} not in supported set {list(ALL_SUPPORTED_STATES)!r}"
    )


def build_review_request_payload(
    state_argument: str,
    commit_sha: str,
    review_body_text: str,
    all_inline_comments: list[dict[str, object]],
) -> dict[str, object]:
    """Assemble the JSON payload sent to the reviews endpoint.

    Args:
        state_argument: One of ``ALL_SUPPORTED_STATES``.
        commit_sha: SHA bound into ``commit_id``.
        review_body_text: Already-formatted review body.
        all_inline_comments: Output of :func:`build_inline_comments_payload`;
            empty list on CLEAN state.

    Returns:
        Dictionary suitable for ``json.dumps`` and sending as the request
        body to ``POST /repos/{owner}/{repo}/pulls/{N}/reviews``.
    """
    return {
        REVIEW_REQUEST_FIELD_COMMIT_ID: commit_sha,
        REVIEW_REQUEST_FIELD_BODY: review_body_text,
        REVIEW_REQUEST_FIELD_EVENT: review_event_for_state(state_argument),
        REVIEW_REQUEST_FIELD_COMMENTS: all_inline_comments,
    }


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
    for each_env_var_name in ALL_GH_TOKEN_ENV_VAR_NAMES:
        env_token_value = os.environ.get(each_env_var_name, "").strip()
        if env_token_value:
            return env_token_value
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
            "`gh` CLI not installed or not on PATH; cannot resolve a GitHub "
            "token"
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
    request_object = _build_authenticated_request(endpoint_url, token, all_request_fields)
    try:
        with urllib.request.urlopen(
            request_object, timeout=HTTP_REQUEST_TIMEOUT_SECONDS
        ) as response_object:
            response_body = response_object.read().decode("utf-8", errors="replace")
            return response_object.status, response_body
    except urllib.error.HTTPError as http_error:
        error_body_text = http_error.read().decode("utf-8", errors="replace")
        return http_error.code, error_body_text


def post_review_with_retries(
    endpoint_url: str,
    token: str,
    all_request_fields: dict[str, object],
) -> PostedReview:
    """POST the review with retries on non-success outcomes.

    Backoffs between attempts come from ``ALL_RETRY_BACKOFF_SECONDS``.
    After every retry has failed, raise :class:`RetryExhaustedError` so
    the entry point can exit with the retry-exhausted code.

    Args:
        endpoint_url: Full URL produced by :func:`build_reviews_endpoint_url`.
        token: GitHub token string.
        all_request_fields: Payload produced by :func:`build_review_request_payload`.

    Returns:
        :class:`PostedReview` carrying the response's ``html_url``, raw
        body, and status code.

    Raises:
        RetryExhaustedError: every attempt across the four-attempt loop
            (one initial attempt plus three retries) returned a non-2xx
            response, raised a transport-level
            :class:`urllib.error.URLError`, or produced a 2xx response
            whose body could not be parsed for ``html_url``.
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


def post_audit_review(parsed_arguments: argparse.Namespace) -> PostedReview:
    """Top-level pipeline: load findings, build body, POST, return result.

    Args:
        parsed_arguments: Output of :func:`parse_command_line_arguments`.

    Returns:
        :class:`PostedReview` containing the new review's ``html_url``.

    Raises:
        UserInputError: bad CLI argument, malformed findings JSON, state
            inconsistent with findings list (CLEAN+non-empty or
            DIRTY+empty), missing ``gh`` CLI, ``gh auth token`` failure,
            or ``audit-reply-template.md`` misconfigured (translated from
            :class:`RuntimeError` at the boundary).
        RetryExhaustedError: every retry failed against the reviews API.
    """
    all_findings = parse_findings_json_file(parsed_arguments.findings_json)
    is_clean_state = parsed_arguments.state == STATE_CLEAN
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
    try:
        skeleton_text = load_audit_body_skeleton()
    except RuntimeError as template_error:
        raise UserInputError(
            f"audit-reply-template.md misconfigured: {template_error}"
        ) from template_error
    review_body_text = fill_audit_body_skeleton(
        skeleton_text=skeleton_text,
        skill_argument=parsed_arguments.skill,
        state_argument=parsed_arguments.state,
        commit_sha=parsed_arguments.commit,
        all_findings=all_findings,
    )
    inline_comments_payload = (
        []
        if parsed_arguments.state == STATE_CLEAN
        else build_inline_comments_payload(parsed_arguments.skill, all_findings)
    )
    all_request_fields = build_review_request_payload(
        state_argument=parsed_arguments.state,
        commit_sha=parsed_arguments.commit,
        review_body_text=review_body_text,
        all_inline_comments=inline_comments_payload,
    )
    endpoint_url = build_reviews_endpoint_url(
        owner=parsed_arguments.owner,
        repo=parsed_arguments.repo,
        pr_number=parsed_arguments.pr_number,
    )
    token_text = resolve_github_token()
    return post_review_with_retries(endpoint_url, token_text, all_request_fields)


def main(all_arguments: list[str]) -> int:
    """Entry-point. Returns the process exit code.

    Args:
        all_arguments: ``sys.argv[1:]`` or equivalent.

    Returns:
        ``0`` on success (emits the new review's ``html_url`` to stdout),
        ``EXIT_CODE_USER_ERROR`` on user input failure,
        ``EXIT_CODE_RETRY_EXHAUSTED`` on retry exhaustion.
    """
    try:
        parsed_arguments = parse_command_line_arguments(all_arguments)
        posted_review = post_audit_review(parsed_arguments)
    except UserInputError as user_error:
        print(f"post_audit_thread: {user_error}", file=sys.stderr)
        return EXIT_CODE_USER_ERROR
    except RetryExhaustedError as retry_error:
        print(f"post_audit_thread: {retry_error}", file=sys.stderr)
        return EXIT_CODE_RETRY_EXHAUSTED
    print(posted_review.html_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
