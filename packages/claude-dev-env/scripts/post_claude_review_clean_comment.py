#!/usr/bin/env python3
"""Post a deterministic PR issue comment after a clean claude-review pass.

Soft-fail contract: every path prints one JSON object on stdout and exits
``0``. A flake in ``gh`` must not fail the review or block a clean stamp.

Idempotency: when a PR issue comment already carries the clean marker and the
same ``head_sha`` line, the helper skips the post.

Usage::

    python post_claude_review_clean_comment.py \\
        --cwd <PR-worktree> \\
        [--head-sha <sha>] \\
        [--mode chain|in_session] \\
        [--served-command <name>] \\
        [--effort <token>] \\
        [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from dev_env_scripts_constants.code_review_constants import (  # noqa: E402
    CODE_REVIEW_PROMPT_TEMPLATE,
    DEFAULT_CODE_REVIEW_EFFORT,
)
from dev_env_scripts_constants.post_claude_review_clean_comment_constants import (  # noqa: E402
    BODY_FILE_SUFFIX,
    CLEAN_COMMENT_BODY_JOIN,
    CLEAN_COMMENT_HEAD_LINE_TEMPLATE,
    CLEAN_COMMENT_MARKER_TITLE,
    CLEAN_COMMENT_MODE_LINE_TEMPLATE,
    CLEAN_COMMENT_NULL_SERVED_COMMAND,
    CLEAN_COMMENT_PROMPT_LINE_TEMPLATE,
    CLEAN_COMMENT_SERVED_COMMAND_LINE_TEMPLATE,
    CLEAN_COMMENT_UNKNOWN_MODE,
    CLI_CWD_FLAG,
    CLI_DRY_RUN_FLAG,
    CLI_EFFORT_FLAG,
    CLI_HEAD_SHA_FLAG,
    CLI_MODE_FLAG,
    CLI_SERVED_COMMAND_FLAG,
    EXIT_SUCCESS,
    GH_API_TOKEN,
    GH_BINARY_NAME,
    GH_BODY_FILE_FLAG,
    GH_COMMENT_BODY_JSON_KEY,
    GH_COMMENT_SUBCOMMAND,
    GH_JSON_FLAG,
    GH_PAGINATE_FLAG,
    GH_PR_NUMBER_JSON_KEY,
    GH_PR_TOKEN,
    GH_PR_VIEW_JSON_FIELDS,
    GH_REPO_NAME_WITH_OWNER_JSON_KEY,
    GH_REPO_TOKEN,
    GH_REPO_VIEW_JSON_FIELDS,
    GH_SLURP_FLAG,
    GH_VIEW_SUBCOMMAND,
    GIT_BINARY,
    GIT_HEAD_REF,
    GIT_REV_PARSE_SUBCOMMAND,
    ISSUE_COMMENTS_API_PATH_TEMPLATE,
    ISSUE_COMMENTS_PAGE_SIZE,
    MESSAGE_ALREADY_POSTED,
    MESSAGE_ARGUMENTS_REJECTED,
    MESSAGE_DRY_RUN,
    MESSAGE_HEAD_RESOLVE_FAILED,
    MESSAGE_LIST_COMMENTS_FAILED,
    MESSAGE_POST_FAILED,
    MESSAGE_POSTED,
    MESSAGE_UNEXPECTED_FAILURE,
    MESSAGE_PR_RESOLVE_FAILED,
    MESSAGE_REPO_RESOLVE_FAILED,
    NAME_WITH_OWNER_SEGMENT_COUNT,
    RESULT_KEY_BODY,
    RESULT_KEY_DRY_RUN,
    RESULT_KEY_HEAD_SHA,
    RESULT_KEY_MESSAGE,
    RESULT_KEY_POSTED,
    RESULT_KEY_PR_NUMBER,
    RESULT_KEY_SKIPPED,
    SUBPROCESS_LAUNCH_FAILURE_RETURNCODE,
    SUBPROCESS_TIMEOUT_SECONDS,
    UTF8_DECODE_ERROR_POLICY,
    UTF8_ENCODING,
)


@dataclass(frozen=True)
class PullRequestTarget:
    """Resolved PR identity for the current worktree."""

    pr_number: int
    owner: str
    repo: str


@dataclass(frozen=True)
class CleanCommentOutcome:
    """Structured result of a clean-comment attempt."""

    is_posted: bool
    is_skipped: bool
    is_dry_run: bool
    head_sha: str
    pr_number: int | None
    message: str
    body: str


def _run_command(
    all_arguments: Sequence[str],
    *,
    working_directory: Path,
) -> subprocess.CompletedProcess[str]:
    """Run one gh/git call, standing in a failed result for a launch problem.

    ::

        _run_command(["gh", "pr", "view"], working_directory=worktree)
            # ok:   CompletedProcess(returncode=0, stdout='{"number": 7}')
            # flag: gh absent -> CompletedProcess(returncode=127, stdout="")

    A missing binary, an unreadable cwd, and a stalled call all become a
    non-zero result rather than an exception, so every caller stays on the
    soft-fail path. Undecodable bytes are replaced instead of killing the
    reader thread and leaving ``stdout`` as None.

    Args:
        all_arguments: Full argv, binary first.
        working_directory: Directory the call runs in.

    Returns:
        The completed process, or a synthetic failed result.
    """
    try:
        return subprocess.run(
            list(all_arguments),
            cwd=str(working_directory),
            capture_output=True,
            text=True,
            encoding=UTF8_ENCODING,
            errors=UTF8_DECODE_ERROR_POLICY,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return subprocess.CompletedProcess(
            args=list(all_arguments),
            returncode=SUBPROCESS_LAUNCH_FAILURE_RETURNCODE,
            stdout="",
            stderr="",
        )


def _resolve_git_head(working_directory: Path) -> str | None:
    completion = _run_command(
        [GIT_BINARY, GIT_REV_PARSE_SUBCOMMAND, GIT_HEAD_REF],
        working_directory=working_directory,
    )
    if completion.returncode != 0:
        return None
    resolved_head = completion.stdout.strip()
    if not resolved_head:
        return None
    return resolved_head


def _parse_name_with_owner(name_with_owner: str) -> tuple[str, str] | None:
    all_parts = name_with_owner.split("/")
    if len(all_parts) != NAME_WITH_OWNER_SEGMENT_COUNT:
        return None
    owner_name, repo_name = all_parts
    if not owner_name or not repo_name:
        return None
    return owner_name, repo_name


def _load_json_object(raw_text: str) -> dict[str, object] | None:
    try:
        parsed_payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed_payload, dict):
        return None
    return parsed_payload


def _resolve_repository_slug(
    working_directory: Path,
) -> tuple[str, str] | None:
    completion = _run_command(
        [
            GH_BINARY_NAME,
            GH_REPO_TOKEN,
            GH_VIEW_SUBCOMMAND,
            GH_JSON_FLAG,
            GH_REPO_VIEW_JSON_FIELDS,
        ],
        working_directory=working_directory,
    )
    if completion.returncode != 0:
        return None
    parsed_payload = _load_json_object(completion.stdout)
    if parsed_payload is None:
        return None
    name_with_owner = parsed_payload.get(GH_REPO_NAME_WITH_OWNER_JSON_KEY)
    if not isinstance(name_with_owner, str):
        return None
    return _parse_name_with_owner(name_with_owner)


def _resolve_pull_request_target(
    working_directory: Path,
    *,
    owner_name: str,
    repo_name: str,
) -> PullRequestTarget | None:
    completion = _run_command(
        [
            GH_BINARY_NAME,
            GH_PR_TOKEN,
            GH_VIEW_SUBCOMMAND,
            GH_JSON_FLAG,
            GH_PR_VIEW_JSON_FIELDS,
        ],
        working_directory=working_directory,
    )
    if completion.returncode != 0:
        return None
    parsed_payload = _load_json_object(completion.stdout)
    if parsed_payload is None:
        return None
    maybe_number = parsed_payload.get(GH_PR_NUMBER_JSON_KEY)
    if not isinstance(maybe_number, int) or isinstance(maybe_number, bool):
        return None
    return PullRequestTarget(
        pr_number=maybe_number,
        owner=owner_name,
        repo=repo_name,
    )


def build_head_sha_line(head_sha: str) -> str:
    """Return the machine-readable head_sha body line.

    Args:
        head_sha: Full or abbreviated SHA the review stamped clean.

    Returns:
        Single body line embedding the SHA.
    """
    return CLEAN_COMMENT_HEAD_LINE_TEMPLATE.format(head_sha=head_sha)


def build_served_command_label(served_command: str | None) -> str:
    """Return the public label for a served binary, path segments stripped.

    ::

        build_served_command_label("claude")                  # ok: "claude"
        build_served_command_label("C:/u/alice/w/claude.exe") # ok: "claude.exe"
        build_served_command_label(None)                      # ok: "null"

    A chain entry's ``command`` may be an absolute path into a per-account
    home directory. The body lands on a public pull request, so only the
    final path segment is written.

    Args:
        served_command: Chain binary, in-session token, or None.

    Returns:
        The final path segment, or the null label when nothing was served.
    """
    if not served_command:
        return CLEAN_COMMENT_NULL_SERVED_COMMAND
    normalized_command = served_command.replace("\\", "/").rstrip("/")
    final_segment = normalized_command.rsplit("/", 1)[-1]
    if not final_segment:
        return CLEAN_COMMENT_NULL_SERVED_COMMAND
    return final_segment


def build_comment_body(
    *,
    head_sha: str,
    mode: str | None,
    served_command: str | None,
    effort: str | None = None,
) -> str:
    """Build the deterministic clean-pass issue-comment body.

    ::

        build_comment_body(head_sha="abc", mode="chain",
                           served_command="claude", effort="low")
        # ok: prompt line reads "/code-review low --fix"

    The prompt line records the effort the run actually used, so the comment
    never attests an effort the review did not run at.

    Args:
        head_sha: SHA the review stamped clean.
        mode: Review mode, or None when unknown.
        served_command: Chain binary or in-session token, or None.
        effort: Effort token the review ran at, or None for the default.

    Returns:
        Full markdown body for ``gh pr comment --body-file``.
    """
    resolved_mode = mode if mode else CLEAN_COMMENT_UNKNOWN_MODE
    resolved_effort = effort if effort else DEFAULT_CODE_REVIEW_EFFORT
    review_prompt = CODE_REVIEW_PROMPT_TEMPLATE.format(effort=resolved_effort)
    all_lines = [
        CLEAN_COMMENT_MARKER_TITLE,
        build_head_sha_line(head_sha),
        CLEAN_COMMENT_PROMPT_LINE_TEMPLATE.format(prompt=review_prompt),
        CLEAN_COMMENT_MODE_LINE_TEMPLATE.format(mode=resolved_mode),
        CLEAN_COMMENT_SERVED_COMMAND_LINE_TEMPLATE.format(
            served_command=build_served_command_label(served_command)
        ),
    ]
    return CLEAN_COMMENT_BODY_JOIN.join(all_lines) + CLEAN_COMMENT_BODY_JOIN


def _list_issue_comment_bodies(
    *,
    pull_request: PullRequestTarget,
    working_directory: Path,
) -> list[str] | None:
    """Read every comment body on a PR through the paginated issues API.

    ::

        gh api ... --paginate --slurp
            # ok: [[{"body": "a"}, {"body": "b"}], [{"body": "c"}]]
            #     one JSON array of pages; flatten after reading every page

    The query runs ``gh api --paginate --slurp`` so every page lands in one
    JSON array of pages, and the flattening happens here after the full
    pagination rather than per page.

    Args:
        pull_request: Resolved PR identity whose comments to read.
        working_directory: PR worktree used as cwd for the ``gh`` call.

    Returns:
        The comment bodies across all pages, or None when gh fails or the
        output is not the slurped page-array shape.
    """
    api_path = ISSUE_COMMENTS_API_PATH_TEMPLATE.format(
        owner=pull_request.owner,
        repo=pull_request.repo,
        pr_number=pull_request.pr_number,
        page_size=ISSUE_COMMENTS_PAGE_SIZE,
    )
    completion = _run_command(
        [GH_BINARY_NAME, GH_API_TOKEN, api_path, GH_PAGINATE_FLAG, GH_SLURP_FLAG],
        working_directory=working_directory,
    )
    if completion.returncode != 0:
        return None
    try:
        all_comment_pages = json.loads(completion.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(all_comment_pages, list):
        return None
    all_bodies: list[str] = []
    for each_page in all_comment_pages:
        if not isinstance(each_page, list):
            continue
        for each_entry in each_page:
            if not isinstance(each_entry, dict):
                continue
            maybe_body = each_entry.get(GH_COMMENT_BODY_JSON_KEY)
            if isinstance(maybe_body, str):
                all_bodies.append(maybe_body)
    return all_bodies


def has_existing_clean_comment(
    all_bodies: Sequence[str],
    *,
    head_sha: str,
) -> bool:
    """Return True when a comment already records this clean HEAD.

    Args:
        all_bodies: Existing issue-comment bodies on the PR.
        head_sha: SHA to match.

    Returns:
        True when marker title and head_sha line both appear in one body.
        The SHA line must match a whole line, so an abbreviated SHA never
        matches a longer SHA that merely starts with it.
    """
    head_line = build_head_sha_line(head_sha)
    for each_body in all_bodies:
        if CLEAN_COMMENT_MARKER_TITLE not in each_body:
            continue
        if any(
            each_line.strip() == head_line for each_line in each_body.splitlines()
        ):
            return True
    return False


def _remove_body_file(body_path: str) -> None:
    """Delete the temporary body file, never masking the post result.

    ::

        file present            -> removed
        file held by a scanner  -> left on disk, no exception raised

    On Windows an indexer or scanner can hold the freshly written file open,
    so an unguarded unlink would raise from a ``finally`` block and turn a
    posted comment into a reported failure.

    Args:
        body_path: Path to the temporary markdown body file.
    """
    try:
        Path(body_path).unlink(missing_ok=True)
    except OSError:
        return


def _post_issue_comment(
    *,
    pull_request: PullRequestTarget,
    comment_body: str,
    working_directory: Path,
) -> bool:
    body_file = tempfile.NamedTemporaryFile(  # noqa: SIM115
        mode="w",
        suffix=BODY_FILE_SUFFIX,
        delete=False,
        encoding=UTF8_ENCODING,
    )
    body_path = body_file.name
    try:
        with body_file:
            body_file.write(comment_body)
        completion = _run_command(
            [
                GH_BINARY_NAME,
                GH_PR_TOKEN,
                GH_COMMENT_SUBCOMMAND,
                str(pull_request.pr_number),
                GH_BODY_FILE_FLAG,
                body_path,
            ],
            working_directory=working_directory,
        )
    finally:
        _remove_body_file(body_path)
    return completion.returncode == 0


def _outcome_payload(outcome: CleanCommentOutcome) -> dict[str, object]:
    return {
        RESULT_KEY_POSTED: outcome.is_posted,
        RESULT_KEY_SKIPPED: outcome.is_skipped,
        RESULT_KEY_DRY_RUN: outcome.is_dry_run,
        RESULT_KEY_HEAD_SHA: outcome.head_sha,
        RESULT_KEY_PR_NUMBER: outcome.pr_number,
        RESULT_KEY_MESSAGE: outcome.message,
        RESULT_KEY_BODY: outcome.body,
    }


def _failed_outcome(
    *,
    head_sha: str,
    pr_number: int | None,
    message: str,
    body: str,
) -> CleanCommentOutcome:
    return CleanCommentOutcome(
        is_posted=False,
        is_skipped=False,
        is_dry_run=False,
        head_sha=head_sha,
        pr_number=pr_number,
        message=message,
        body=body,
    )


def _resolve_head_sha(
    *,
    working_directory: Path,
    head_sha: str | None,
) -> str | None:
    """Resolve the SHA to stamp, failing closed on an explicitly empty flag.

    ::

        head_sha=None  -> git rev-parse HEAD
        head_sha="abc" -> "abc"
        head_sha=""    -> None (caller must not stamp)

    An omitted ``--head-sha`` means "read the worktree". An empty value means
    the caller had no SHA to give, so resolving a live HEAD here would stamp a
    commit no review covered.

    Args:
        working_directory: Git working tree to read HEAD from.
        head_sha: Caller-stated SHA, empty string, or None when omitted.

    Returns:
        The SHA to stamp, or None when the caller passed an empty value or
        git HEAD could not be read.
    """
    if head_sha is None:
        return _resolve_git_head(working_directory)
    if not head_sha.strip():
        return None
    return head_sha


def _attempt_live_post(
    *,
    working_directory: Path,
    resolved_head: str,
    comment_body: str,
) -> CleanCommentOutcome:
    maybe_slug = _resolve_repository_slug(working_directory)
    if maybe_slug is None:
        return _failed_outcome(
            head_sha=resolved_head,
            pr_number=None,
            message=MESSAGE_REPO_RESOLVE_FAILED,
            body=comment_body,
        )
    owner_name, repo_name = maybe_slug
    pull_request = _resolve_pull_request_target(
        working_directory,
        owner_name=owner_name,
        repo_name=repo_name,
    )
    if pull_request is None:
        return _failed_outcome(
            head_sha=resolved_head,
            pr_number=None,
            message=MESSAGE_PR_RESOLVE_FAILED,
            body=comment_body,
        )
    return _post_or_skip_existing(
        pull_request=pull_request,
        working_directory=working_directory,
        resolved_head=resolved_head,
        comment_body=comment_body,
    )


def _post_or_skip_existing(
    *,
    pull_request: PullRequestTarget,
    working_directory: Path,
    resolved_head: str,
    comment_body: str,
) -> CleanCommentOutcome:
    all_bodies = _list_issue_comment_bodies(
        pull_request=pull_request,
        working_directory=working_directory,
    )
    if all_bodies is None:
        return _failed_outcome(
            head_sha=resolved_head,
            pr_number=pull_request.pr_number,
            message=MESSAGE_LIST_COMMENTS_FAILED,
            body=comment_body,
        )
    if has_existing_clean_comment(all_bodies, head_sha=resolved_head):
        return CleanCommentOutcome(
            is_posted=False,
            is_skipped=True,
            is_dry_run=False,
            head_sha=resolved_head,
            pr_number=pull_request.pr_number,
            message=MESSAGE_ALREADY_POSTED,
            body=comment_body,
        )
    is_posted = _post_issue_comment(
        pull_request=pull_request,
        comment_body=comment_body,
        working_directory=working_directory,
    )
    if not is_posted:
        return _failed_outcome(
            head_sha=resolved_head,
            pr_number=pull_request.pr_number,
            message=MESSAGE_POST_FAILED,
            body=comment_body,
        )
    return CleanCommentOutcome(
        is_posted=True,
        is_skipped=False,
        is_dry_run=False,
        head_sha=resolved_head,
        pr_number=pull_request.pr_number,
        message=MESSAGE_POSTED,
        body=comment_body,
    )


def post_clean_review_comment(
    *,
    working_directory: Path,
    head_sha: str | None,
    mode: str | None,
    served_command: str | None,
    is_dry_run: bool,
    effort: str | None = None,
) -> CleanCommentOutcome:
    """Resolve the PR and post (or skip) the clean-pass issue comment.

    Args:
        working_directory: PR worktree path.
        head_sha: Reviewed SHA, or None to read git HEAD.
        mode: Review mode, or None when unknown.
        served_command: Served binary/token, or None when unknown.
        is_dry_run: When True, print body without posting.
        effort: Effort token the review ran at, or None for the default.

    Returns:
        Structured soft-fail outcome (never raises for gh/git failures).
    """
    resolved_head = _resolve_head_sha(
        working_directory=working_directory,
        head_sha=head_sha,
    )
    if not resolved_head:
        return _failed_outcome(
            head_sha="",
            pr_number=None,
            message=MESSAGE_HEAD_RESOLVE_FAILED,
            body="",
        )
    comment_body = build_comment_body(
        head_sha=resolved_head,
        mode=mode,
        served_command=served_command,
        effort=effort,
    )
    if is_dry_run:
        return CleanCommentOutcome(
            is_posted=False,
            is_skipped=False,
            is_dry_run=True,
            head_sha=resolved_head,
            pr_number=None,
            message=MESSAGE_DRY_RUN,
            body=comment_body,
        )
    return _attempt_live_post(
        working_directory=working_directory,
        resolved_head=resolved_head,
        comment_body=comment_body,
    )


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Post a deterministic PR issue comment after a clean "
            "claude-review pass (soft-fail, idempotent per HEAD)."
        )
    )
    parser.add_argument(CLI_CWD_FLAG, required=True)
    parser.add_argument(CLI_HEAD_SHA_FLAG, default=None)
    parser.add_argument(CLI_MODE_FLAG, default=None)
    parser.add_argument(CLI_SERVED_COMMAND_FLAG, default=None)
    parser.add_argument(CLI_EFFORT_FLAG, default=None)
    parser.add_argument(CLI_DRY_RUN_FLAG, action="store_true")
    return parser


def main(all_argv: Sequence[str]) -> int:
    """CLI entry: print one JSON outcome and always exit success.

    Args:
        all_argv: Argument vector without program name.

    Returns:
        Always ``EXIT_SUCCESS`` so comment flakes never fail the review. A
        rejected argument vector and any unforeseen error are both caught here
        and reported as a failed outcome, so the one-JSON-object-then-exit-0
        contract holds structurally rather than resting on every helper
        choosing to return instead of raise.
    """
    parser = _build_argument_parser()
    try:
        parsed_arguments = parser.parse_args(list(all_argv))
    except SystemExit:
        print(
            json.dumps(
                _outcome_payload(
                    _failed_outcome(
                        head_sha="",
                        pr_number=None,
                        message=MESSAGE_ARGUMENTS_REJECTED,
                        body="",
                    )
                ),
                sort_keys=True,
            )
        )
        return EXIT_SUCCESS
    try:
        outcome = post_clean_review_comment(
            working_directory=Path(parsed_arguments.cwd),
            head_sha=parsed_arguments.head_sha,
            mode=parsed_arguments.mode,
            served_command=parsed_arguments.served_command,
            is_dry_run=bool(parsed_arguments.dry_run),
            effort=parsed_arguments.effort,
        )
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        KeyError,
        AttributeError,
        subprocess.SubprocessError,
    ):
        outcome = _failed_outcome(
            head_sha=parsed_arguments.head_sha or "",
            pr_number=None,
            message=MESSAGE_UNEXPECTED_FAILURE,
            body="",
        )
    print(json.dumps(_outcome_payload(outcome), sort_keys=True))
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
