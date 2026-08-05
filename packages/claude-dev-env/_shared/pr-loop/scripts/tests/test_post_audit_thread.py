"""Live smoke tests for post_audit_thread.py.

Runs against the real GitHub repo ``JonEcho/tests``. The class opens a
single throwaway draft PR in ``setUpClass`` and reuses it across every
test in the class; ``tearDownClass`` closes the PR with
``--delete-branch``. The CLEAN and DIRTY tests post real reviews against
the shared PR. The retry tests stub the GitHub endpoint with a localhost
HTTP server so the four-attempt retry loop runs deterministically without
contacting api.github.com, but still reference the shared PR's number and
HEAD SHA so the request URL is exercised end-to-end. Authentication uses
``gh auth token`` — empty token fails loudly per spec.

Test files are exempt from the no-comment, magic-value, banned-identifier,
and constants-location enforcer rules.
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
import urllib.parse
import uuid
from pathlib import Path
from typing import Any

THIS_FILE_DIRECTORY = Path(__file__).resolve().parent
SCRIPT_DIRECTORY = THIS_FILE_DIRECTORY.parent

if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

from pr_loop_shared_constants.post_audit_thread_constants import (  # noqa: E402
    ALL_GH_AUTH_TOKEN_COMMAND_PARTS,
    ALL_RETRY_BACKOFF_SECONDS,
    BUGTEAM_REVIEWER_ACCOUNT_ENV_VAR_NAME,
    GH_TOKEN_ENV_VAR_NAME,
    GITHUB_TOKEN_ENV_VAR_NAME,
    CLI_FLAG_COMMIT,
    CLI_FLAG_FINDINGS_JSON,
    CLI_FLAG_OWNER,
    CLI_FLAG_PR_NUMBER,
    CLI_FLAG_REPO,
    CLI_FLAG_SKILL,
    CLI_FLAG_STATE,
    EXIT_CODE_RETRY_EXHAUSTED,
    INLINE_COMMENT_SIDE_RIGHT,
    JSON_FIELD_DESCRIPTION,
    JSON_FIELD_FIX_SUMMARY,
    JSON_FIELD_LINE,
    JSON_FIELD_PATH,
    JSON_FIELD_SEVERITY,
    JSON_FIELD_SIDE,
    MAX_RETRY_ATTEMPTS,
    SEVERITY_TAG_P0,
    SEVERITY_TAG_P1,
    SEVERITY_TAG_P2,
    SINGLE_REVIEW_API_PATH_TEMPLATE,
    SINGLE_REVIEW_COMMENTS_API_PATH_TEMPLATE,
    SKILL_BUGTEAM,
    STATE_CLEAN,
    STATE_DIRTY,
    GITHUB_REVIEW_EVENT_APPROVE,
    GITHUB_REVIEW_EVENT_COMMENT,
    GITHUB_REVIEW_EVENT_REQUEST_CHANGES,
    HTTP_STATUS_UNPROCESSABLE_ENTITY,
    REVIEW_REQUEST_FIELD_BODY,
    REVIEW_REQUEST_FIELD_COMMENTS,
    REVIEW_REQUEST_FIELD_EVENT,
    SELF_APPROVAL_DOWNGRADE_DISCLOSURE_CLEAN,
    SELF_APPROVAL_DOWNGRADE_DISCLOSURE_DIRTY,
    SELF_APPROVAL_DOWNGRADE_STDOUT_MARKER,
    AUDIT_BODY_SKELETON_CLOSE_MARKER,
    AUDIT_BODY_SKELETON_OPEN_MARKER,
    PLACEHOLDER_SKILL,
    SHORT_SHA_LENGTH,
    TEMPLATE_FENCE_TOKEN,
)
from post_audit_thread import (  # noqa: E402
    AuditFinding,
    AuditReviewOutcome,
    RetryExhaustedError,
    ReviewerCredentials,
    UserInputError,
    append_self_approval_disclosure,
    build_details_block,
    build_inline_comments_payload,
    build_review_request_payload,
    build_reviews_endpoint_url,
    execute_review_post_attempt,
    extract_audit_body_skeleton,
    extract_html_url_field,
    fetch_gh_token_for_account,
    fill_audit_body_skeleton,
    list_authenticated_gh_account_logins,
    load_audit_body_skeleton,
    parse_command_line_arguments,
    parse_findings_json_file,
    post_audit_review,
    post_review_with_retries,
    query_active_gh_user_login,
    query_pull_request_author_login,
    resolve_github_token,
    resolve_reviewer_credentials,
    review_event_for_state,
    severity_counts_by_tag,
    short_commit_sha,
    skill_display_name,
)

LIVE_TEST_OWNER = "JonEcho"
LIVE_TEST_REPO = "tests"
LIVE_TEST_BRANCH_PREFIX = "pr-loop-test"
LIVE_TEST_PR_TITLE = "TEST: post_audit_thread smoke test (auto-closed)"
LIVE_TEST_PR_BODY = (
    "Throwaway PR for post_audit_thread.py live smoke tests. "
    "Auto-created by `test_post_audit_thread.py`; closed in `tearDownClass`."
)
LIVE_TEST_BASE_BRANCH = "main"
LIVE_TEST_FIXTURE_FILENAME = "post-audit-thread-fixture.md"
LIVE_TEST_FIXTURE_CONTENT = (
    "# Throwaway test fixture\n\n"
    "Created by `test_post_audit_thread.py` to satisfy GitHub's "
    "non-empty PR-diff requirement. Deleted when the PR closes.\n"
)
LIVE_TEST_FIXTURE_LINE_FOR_FINDING_ONE = 1
LIVE_TEST_FIXTURE_LINE_FOR_FINDING_TWO = 2
LIVE_TEST_FIXTURE_LINE_FOR_FINDING_THREE = 3

SCRIPT_PATH = SCRIPT_DIRECTORY / "post_audit_thread.py"
REPO_FULL_NAME = f"{LIVE_TEST_OWNER}/{LIVE_TEST_REPO}"

LIVE_TEST_AUDIT_ACCOUNT_NAME = "jl-cmd"

GH_EVENT_APPROVED = "APPROVED"
GH_EVENT_CHANGES_REQUESTED = "CHANGES_REQUESTED"

UUID_SUFFIX_LENGTH = 8

REVIEW_URL_ID_DELIMITER = "#pullrequestreview-"


def _strip_read_only_and_retry(
    removal_function: Any, target_path: str, *_exc_info: Any
) -> None:
    try:
        os.chmod(target_path, stat.S_IWRITE)
        removal_function(target_path)
    except OSError:
        pass


def force_remove_directory(target_path: Path) -> None:
    if not target_path.exists():
        return
    handler_kwargs: dict[str, Any]
    if sys.version_info >= (3, 12):
        handler_kwargs = {"onexc": _strip_read_only_and_retry}
    else:
        handler_kwargs = {"onerror": _strip_read_only_and_retry}
    try:
        shutil.rmtree(str(target_path), **handler_kwargs)
    except OSError as removal_error:
        sys.stderr.write(
            f"force_remove_directory: could not remove {target_path}: {removal_error}\n"
        )


def resolve_gh_auth_token() -> str:
    completion = subprocess.run(
        list(ALL_GH_AUTH_TOKEN_COMMAND_PARTS),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completion.returncode != 0:
        raise AssertionError(
            f"`gh auth token` failed: rc={completion.returncode} "
            f"stderr={completion.stderr.strip()} — live tests require gh to "
            f"be authenticated against github.com"
        )
    token_text = completion.stdout.strip()
    if not token_text:
        raise AssertionError(
            "`gh auth token` returned empty output — not authenticated"
        )
    return token_text


def resolve_audit_account_token(account_name: str) -> str:
    completion = subprocess.run(
        list(ALL_GH_AUTH_TOKEN_COMMAND_PARTS) + ["--user", account_name],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completion.returncode != 0:
        raise AssertionError(
            f"`gh auth token --user {account_name}` failed — the audit-side "
            f"account must be authenticated separately from the PR author so "
            f"GitHub allows APPROVE / REQUEST_CHANGES on the throwaway PR. "
            f"rc={completion.returncode} stderr={completion.stderr.strip()}"
        )
    token_text = completion.stdout.strip()
    if not token_text:
        raise AssertionError(
            f"`gh auth token --user {account_name}` returned empty output"
        )
    return token_text


def gh_api_object_json(api_path: str) -> dict[str, Any]:
    completion = subprocess.run(
        ["gh", "api", api_path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    parsed_object: Any = json.loads(completion.stdout)
    if not isinstance(parsed_object, dict):
        raise AssertionError(
            f"unexpected gh api object shape: {type(parsed_object).__name__}"
        )
    return parsed_object


def review_id_from_html_url(html_url: str) -> int:
    suffix_parts = html_url.rsplit(REVIEW_URL_ID_DELIMITER, 1)
    if len(suffix_parts) != 2:
        raise AssertionError(
            f"html_url {html_url!r} missing {REVIEW_URL_ID_DELIMITER!r} suffix"
        )
    return int(suffix_parts[1])


def gh_api_paginated_json(api_path: str) -> list[dict[str, Any]]:
    completion = subprocess.run(
        ["gh", "api", api_path, "--paginate", "--slurp"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    parsed: Any = json.loads(completion.stdout)
    if not isinstance(parsed, list):
        raise AssertionError(
            f"unexpected gh api response shape: {type(parsed).__name__}"
        )
    flattened: list[dict[str, Any]] = []
    for each_page in parsed:
        if isinstance(each_page, list):
            for each_item in each_page:
                if isinstance(each_item, dict):
                    flattened.append(each_item)
        elif isinstance(each_page, dict):
            flattened.append(each_page)
    return flattened


def write_pr_body_temporary_file(body_text: str) -> Path:
    handle, body_path_str = tempfile.mkstemp(suffix=".md", prefix="post-audit-pr-body-")
    os.close(handle)
    body_path = Path(body_path_str)
    body_path.write_text(body_text, encoding="utf-8")
    return body_path


def create_throwaway_pr(
    clone_directory: Path,
    branch_name: str,
) -> tuple[int, str]:
    subprocess.run(
        [
            "gh",
            "repo",
            "clone",
            REPO_FULL_NAME,
            str(clone_directory),
            "--",
            "--branch",
            LIVE_TEST_BASE_BRANCH,
            "--single-branch",
            "--depth",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(clone_directory),
            "config",
            "--local",
            "core.hooksPath",
            str(clone_directory / ".git" / "hooks"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "-C", str(clone_directory), "checkout", "-b", branch_name],
        check=True,
        capture_output=True,
        text=True,
    )
    fixture_path = clone_directory / LIVE_TEST_FIXTURE_FILENAME
    fixture_path.write_text(LIVE_TEST_FIXTURE_CONTENT, encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(clone_directory), "add", LIVE_TEST_FIXTURE_FILENAME],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(clone_directory),
            "commit",
            "-m",
            "test: post_audit_thread.py live smoke fixture",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    head_sha_completion = subprocess.run(
        ["git", "-C", str(clone_directory), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    head_sha = head_sha_completion.stdout.strip()
    subprocess.run(
        ["git", "-C", str(clone_directory), "push", "-u", "origin", branch_name],
        check=True,
        capture_output=True,
        text=True,
    )
    body_path = write_pr_body_temporary_file(LIVE_TEST_PR_BODY)
    try:
        create_completion = subprocess.run(
            [
                "gh",
                "pr",
                "create",
                "--draft",
                "--head",
                branch_name,
                "--base",
                LIVE_TEST_BASE_BRANCH,
                "--title",
                LIVE_TEST_PR_TITLE,
                "--body-file",
                str(body_path),
                "--repo",
                REPO_FULL_NAME,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            cwd=str(clone_directory),
        )
    finally:
        try:
            body_path.unlink()
        except OSError:
            pass
    pr_url = create_completion.stdout.strip().splitlines()[-1]
    parsed_pr_url = urllib.parse.urlparse(pr_url)
    pr_number = int(parsed_pr_url.path.rsplit("/", 1)[-1])
    return pr_number, head_sha


def close_throwaway_pr(pr_number: int) -> None:
    subprocess.run(
        [
            "gh",
            "pr",
            "close",
            str(pr_number),
            "--delete-branch",
            "--repo",
            REPO_FULL_NAME,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def remove_local_clone(clone_directory: Path) -> None:
    force_remove_directory(clone_directory)


def best_effort_delete_remote_branch(branch_name: str) -> None:
    try:
        subprocess.run(
            [
                "gh",
                "api",
                "--method",
                "DELETE",
                f"repos/{LIVE_TEST_OWNER}/{LIVE_TEST_REPO}/git/refs/heads/{branch_name}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as deletion_error:
        sys.stderr.write(
            f"best_effort_delete_remote_branch: could not delete "
            f"{branch_name}: {deletion_error}\n"
        )


def write_findings_json(findings_payload: list[dict[str, Any]]) -> Path:
    handle, findings_path_str = tempfile.mkstemp(
        suffix=".json", prefix="post-audit-findings-"
    )
    os.close(handle)
    findings_path = Path(findings_path_str)
    findings_path.write_text(json.dumps(findings_payload), encoding="utf-8")
    return findings_path


def invoke_post_audit_thread_script(
    pr_number: int,
    head_sha: str,
    state_argument: str,
    findings_json_path: Path,
    audit_token: str,
) -> subprocess.CompletedProcess[str]:
    child_environment = dict(os.environ)
    child_environment[GH_TOKEN_ENV_VAR_NAME] = audit_token
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            CLI_FLAG_SKILL,
            SKILL_BUGTEAM,
            CLI_FLAG_OWNER,
            LIVE_TEST_OWNER,
            CLI_FLAG_REPO,
            LIVE_TEST_REPO,
            CLI_FLAG_PR_NUMBER,
            str(pr_number),
            CLI_FLAG_COMMIT,
            head_sha,
            CLI_FLAG_STATE,
            state_argument,
            CLI_FLAG_FINDINGS_JSON,
            str(findings_json_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        env=child_environment,
    )


STUB_SERVER_HOST = "127.0.0.1"
STUB_SERVER_PORT_DYNAMIC = 0
STUB_RESPONSE_HEADER_CONTENT_TYPE = "Content-Type"
STUB_RESPONSE_HEADER_CONTENT_LENGTH = "Content-Length"
STUB_RESPONSE_CONTENT_TYPE_VALUE = "application/json"
STUB_HTTP_STATUS_BAD_GATEWAY = 502
STUB_HTTP_STATUS_OK = 200
STUB_502_RESPONSE_BODY_BYTES = json.dumps(
    {"message": "stub server: simulated transient 502 for retry test"}
).encode("utf-8")
STUB_200_RESPONSE_BODY_BYTES = json.dumps(
    {"html_url": ("https://github.com/stub-host/stub-repo/pull/0#pullrequestreview-1")}
).encode("utf-8")
STUB_SERVER_SHUTDOWN_JOIN_TIMEOUT_SECONDS = 5.0

FAILURE_COUNT_FOR_RETRY_SUCCESS = 1
TOTAL_REQUEST_COUNT_FOR_RETRY_SUCCESS = 2
FAILURE_COUNT_FOR_RETRY_EXHAUSTION = MAX_RETRY_ATTEMPTS + 1
TOTAL_REQUEST_COUNT_FOR_RETRY_EXHAUSTION = MAX_RETRY_ATTEMPTS + 1

BACKOFF_TIMING_EPSILON_SECONDS = 0.1
TOTAL_BACKOFF_SECONDS = sum(ALL_RETRY_BACKOFF_SECONDS)

EXPECTED_RETRY_SUCCESS_ELAPSED_LOWER_BOUND_SECONDS = (
    ALL_RETRY_BACKOFF_SECONDS[0] - BACKOFF_TIMING_EPSILON_SECONDS
)
EXPECTED_RETRY_EXHAUSTION_ELAPSED_LOWER_BOUND_SECONDS = (
    TOTAL_BACKOFF_SECONDS - BACKOFF_TIMING_EPSILON_SECONDS
)

EXIT_CODE_SUCCESS = 0

LAUNCHER_SOURCE_CODE = textwrap.dedent(
    """
    import sys
    sys.path.insert(0, sys.argv[1])
    import post_audit_thread
    post_audit_thread.GITHUB_API_BASE_URL = sys.argv[2]
    sys.exit(post_audit_thread.main(sys.argv[3:]))
    """
).strip()


class _StubReviewsServer(http.server.HTTPServer):
    """HTTP server that records POST count and serves canned 502/200 responses."""

    request_count: int = 0
    failure_count: int = 0
    recorded_request_path: str = ""


class _StubReviewsHandler(http.server.BaseHTTPRequestHandler):
    """Returns 502 for the first ``failure_count`` POSTs, then 200 thereafter.

    State lives on the owning :class:`_StubReviewsServer` instance so the
    test can inspect the final request count and the path of the last
    received POST after the script exits.
    """

    def do_POST(self) -> None:
        owning_server = self.server
        owning_server.request_count += 1
        owning_server.recorded_request_path = self.path
        if owning_server.request_count <= owning_server.failure_count:
            response_status = STUB_HTTP_STATUS_BAD_GATEWAY
            response_body_bytes = STUB_502_RESPONSE_BODY_BYTES
        else:
            response_status = STUB_HTTP_STATUS_OK
            response_body_bytes = STUB_200_RESPONSE_BODY_BYTES
        self.send_response(response_status)
        self.send_header(
            STUB_RESPONSE_HEADER_CONTENT_TYPE, STUB_RESPONSE_CONTENT_TYPE_VALUE
        )
        self.send_header(
            STUB_RESPONSE_HEADER_CONTENT_LENGTH, str(len(response_body_bytes))
        )
        self.end_headers()
        self.wfile.write(response_body_bytes)

    def log_message(self, format: str, *args: Any) -> None:
        return


def spawn_stub_reviews_server(
    failure_count: int,
) -> tuple[_StubReviewsServer, threading.Thread]:
    """Start a localhost stub server returning leading 502s then 200s.

    Args:
        failure_count: Number of leading POSTs the stub responds to with
            502. Subsequent POSTs receive a synthetic 200 carrying a fake
            ``html_url``. Set above the script's total retry budget to
            force the retry-exhaustion path end-to-end.

    Returns:
        Tuple of the stub server (bound to a random port on
        ``127.0.0.1``) and its serving thread.
    """
    stub_server = _StubReviewsServer(
        (STUB_SERVER_HOST, STUB_SERVER_PORT_DYNAMIC), _StubReviewsHandler
    )
    stub_server.request_count = 0
    stub_server.failure_count = failure_count
    stub_server.recorded_request_path = ""
    stub_thread = threading.Thread(target=stub_server.serve_forever, daemon=True)
    stub_thread.start()
    return stub_server, stub_thread


def shutdown_stub_reviews_server(
    stub_server: _StubReviewsServer,
    stub_thread: threading.Thread,
) -> None:
    """Stop the stub server and join its serving thread.

    Args:
        stub_server: Server returned by :func:`spawn_stub_reviews_server`.
        stub_thread: Serving thread returned by
            :func:`spawn_stub_reviews_server`.
    """
    stub_server.shutdown()
    stub_server.server_close()
    stub_thread.join(timeout=STUB_SERVER_SHUTDOWN_JOIN_TIMEOUT_SECONDS)


def stub_reviews_server_base_url(stub_server: _StubReviewsServer) -> str:
    """Return ``http://host:port`` for a bound stub server.

    Args:
        stub_server: Server returned by :func:`spawn_stub_reviews_server`.

    Returns:
        Base URL suitable for assigning to
        ``post_audit_thread.GITHUB_API_BASE_URL`` inside the launcher
        subprocess so the script targets the stub instead of api.github.com.
    """
    host_address, bound_port = stub_server.server_address[:2]
    return f"http://{host_address}:{bound_port}"


def invoke_post_audit_thread_with_url_override(
    pr_number: int,
    head_sha: str,
    state_argument: str,
    findings_json_path: Path,
    audit_token: str,
    overridden_base_url: str,
) -> subprocess.CompletedProcess[str]:
    """Subprocess-invoke the script with ``GITHUB_API_BASE_URL`` redirected.

    The subprocess runs a short launcher (``LAUNCHER_SOURCE_CODE``) that
    imports ``post_audit_thread`` as a module, rebinds its
    ``GITHUB_API_BASE_URL`` attribute to ``overridden_base_url``, then
    delegates to ``main()``. Lets the retry tests point the script at the
    local stub server without modifying production source.

    Args:
        pr_number: Throwaway PR number created by ``setUpClass``.
        head_sha: HEAD SHA the script attaches the review to.
        state_argument: ``CLEAN`` or ``DIRTY``.
        findings_json_path: Path to the (empty-list) findings JSON.
        audit_token: Token assigned to ``GH_TOKEN`` in the child env.
        overridden_base_url: Base URL handed to the launcher (the local
            stub server URL).

    Returns:
        Completed subprocess result with ``returncode``, ``stdout``, and
        ``stderr`` for the test to inspect.
    """
    child_environment = dict(os.environ)
    child_environment[GH_TOKEN_ENV_VAR_NAME] = audit_token
    return subprocess.run(
        [
            sys.executable,
            "-c",
            LAUNCHER_SOURCE_CODE,
            str(SCRIPT_DIRECTORY),
            overridden_base_url,
            CLI_FLAG_SKILL,
            SKILL_BUGTEAM,
            CLI_FLAG_OWNER,
            LIVE_TEST_OWNER,
            CLI_FLAG_REPO,
            LIVE_TEST_REPO,
            CLI_FLAG_PR_NUMBER,
            str(pr_number),
            CLI_FLAG_COMMIT,
            head_sha,
            CLI_FLAG_STATE,
            state_argument,
            CLI_FLAG_FINDINGS_JSON,
            str(findings_json_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        env=child_environment,
    )


class LivePostAuditThreadTests(unittest.TestCase):
    """Live smoke tests for post_audit_thread.py against JonEcho/tests.

    Every test in this class reuses a single throwaway draft PR created
    in :meth:`setUpClass` and closed in :meth:`tearDownClass`. The CLEAN
    and DIRTY tests post real reviews against that PR; the retry tests
    redirect the script's HTTP layer to a localhost stub server so the
    retry loop runs deterministically without touching api.github.com,
    while still consuming the shared PR's number and HEAD SHA.
    """

    audit_account_token: str
    local_clone_directory: Path
    branch_name: str
    pr_number: int
    head_sha: str

    @classmethod
    def setUpClass(cls) -> None:
        resolve_gh_auth_token()
        cls.audit_account_token = resolve_audit_account_token(
            LIVE_TEST_AUDIT_ACCOUNT_NAME
        )
        unique_suffix = uuid.uuid4().hex[:UUID_SUFFIX_LENGTH]
        cls.branch_name = f"{LIVE_TEST_BRANCH_PREFIX}/{unique_suffix}"
        cls.local_clone_directory = Path(
            tempfile.mkdtemp(prefix=f"post-audit-thread-test-{unique_suffix}-")
        )
        cls.pr_number = 0
        cls.head_sha = ""
        try:
            cls.pr_number, cls.head_sha = create_throwaway_pr(
                cls.local_clone_directory,
                cls.branch_name,
            )
        except Exception:
            try:
                remove_local_clone(cls.local_clone_directory)
            finally:
                best_effort_delete_remote_branch(cls.branch_name)
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            if cls.pr_number > 0:
                close_throwaway_pr(cls.pr_number)
        finally:
            try:
                remove_local_clone(cls.local_clone_directory)
            finally:
                best_effort_delete_remote_branch(cls.branch_name)

    def _assert_review_state_for_url(
        self, html_url: str, expected_state: str
    ) -> dict[str, Any]:
        review_id = review_id_from_html_url(html_url)
        single_review_api_path = SINGLE_REVIEW_API_PATH_TEMPLATE.format(
            owner=LIVE_TEST_OWNER,
            repo=LIVE_TEST_REPO,
            pr_number=self.pr_number,
            review_id=review_id,
        )
        single_review = gh_api_object_json(single_review_api_path)
        self.assertEqual(
            single_review.get("state"),
            expected_state,
            f"unexpected review state for {html_url!r}: {single_review!r}",
        )
        return single_review

    def _fetch_comments_for_review(self, html_url: str) -> list[dict[str, Any]]:
        review_id = review_id_from_html_url(html_url)
        review_comments_api_path = SINGLE_REVIEW_COMMENTS_API_PATH_TEMPLATE.format(
            owner=LIVE_TEST_OWNER,
            repo=LIVE_TEST_REPO,
            pr_number=self.pr_number,
            review_id=review_id,
        )
        return gh_api_paginated_json(review_comments_api_path)

    def _run_script_capturing_html_url(
        self,
        state_argument: str,
        findings_payload: list[dict[str, Any]],
    ) -> str:
        findings_path = write_findings_json(findings_payload)
        try:
            completion = invoke_post_audit_thread_script(
                pr_number=self.pr_number,
                head_sha=self.head_sha,
                state_argument=state_argument,
                findings_json_path=findings_path,
                audit_token=self.audit_account_token,
            )
        finally:
            try:
                findings_path.unlink()
            except OSError:
                pass
        self.assertEqual(
            completion.returncode,
            0,
            f"script exited {completion.returncode}; stdout={completion.stdout!r} "
            f"stderr={completion.stderr!r}",
        )
        emitted_html_url = completion.stdout.strip().splitlines()[-1]
        self.assertTrue(
            emitted_html_url.startswith("https://github.com/"),
            f"expected an html_url on stdout, got {emitted_html_url!r}",
        )
        return emitted_html_url

    def test_clean_state_posts_approved_review_with_empty_comments(self) -> None:
        emitted_html_url = self._run_script_capturing_html_url(
            state_argument=STATE_CLEAN, findings_payload=[]
        )
        self._assert_review_state_for_url(emitted_html_url, GH_EVENT_APPROVED)
        review_comments = self._fetch_comments_for_review(emitted_html_url)
        self.assertEqual(
            len(review_comments),
            0,
            f"CLEAN state should produce zero inline comments on this review; "
            f"saw {len(review_comments)}: {review_comments!r}",
        )

    def test_dirty_state_with_three_findings_posts_changes_requested_with_three_inline_threads(
        self,
    ) -> None:
        findings_payload: list[dict[str, Any]] = [
            {
                JSON_FIELD_PATH: LIVE_TEST_FIXTURE_FILENAME,
                JSON_FIELD_LINE: LIVE_TEST_FIXTURE_LINE_FOR_FINDING_ONE,
                JSON_FIELD_SIDE: INLINE_COMMENT_SIDE_RIGHT,
                JSON_FIELD_SEVERITY: SEVERITY_TAG_P0,
                JSON_FIELD_DESCRIPTION: "Smoke finding one (heading line).",
                JSON_FIELD_FIX_SUMMARY: "Trim the leading marker (smoke fix one).",
            },
            {
                JSON_FIELD_PATH: LIVE_TEST_FIXTURE_FILENAME,
                JSON_FIELD_LINE: LIVE_TEST_FIXTURE_LINE_FOR_FINDING_TWO,
                JSON_FIELD_SIDE: INLINE_COMMENT_SIDE_RIGHT,
                JSON_FIELD_SEVERITY: SEVERITY_TAG_P1,
                JSON_FIELD_DESCRIPTION: "Smoke finding two (blank-line anchor).",
                JSON_FIELD_FIX_SUMMARY: "Collapse the blank separator (smoke fix two).",
            },
            {
                JSON_FIELD_PATH: LIVE_TEST_FIXTURE_FILENAME,
                JSON_FIELD_LINE: LIVE_TEST_FIXTURE_LINE_FOR_FINDING_THREE,
                JSON_FIELD_SIDE: INLINE_COMMENT_SIDE_RIGHT,
                JSON_FIELD_SEVERITY: SEVERITY_TAG_P2,
                JSON_FIELD_DESCRIPTION: "Smoke finding three (body-line anchor).",
                JSON_FIELD_FIX_SUMMARY: "Tighten the description (smoke fix three).",
            },
        ]
        emitted_html_url = self._run_script_capturing_html_url(
            state_argument=STATE_DIRTY, findings_payload=findings_payload
        )
        self._assert_review_state_for_url(emitted_html_url, GH_EVENT_CHANGES_REQUESTED)
        review_comments = self._fetch_comments_for_review(emitted_html_url)
        self.assertEqual(
            len(review_comments),
            len(findings_payload),
            f"DIRTY state should produce one inline comment per finding on "
            f"this review; expected {len(findings_payload)} got "
            f"{len(review_comments)}: {review_comments!r}",
        )

    def _expected_reviews_request_path(self) -> str:
        full_endpoint_url = build_reviews_endpoint_url(
            LIVE_TEST_OWNER, LIVE_TEST_REPO, self.pr_number
        )
        parsed_endpoint = urllib.parse.urlparse(full_endpoint_url)
        return parsed_endpoint.path

    def _run_retry_simulation_and_measure_elapsed(
        self,
        failure_count: int,
    ) -> tuple[subprocess.CompletedProcess[str], _StubReviewsServer, float]:
        findings_path = write_findings_json([])
        try:
            stub_server, stub_thread = spawn_stub_reviews_server(
                failure_count=failure_count
            )
            try:
                overridden_base_url = stub_reviews_server_base_url(stub_server)
                start_time = time.perf_counter()
                completion = invoke_post_audit_thread_with_url_override(
                    pr_number=self.pr_number,
                    head_sha=self.head_sha,
                    state_argument=STATE_CLEAN,
                    findings_json_path=findings_path,
                    audit_token=self.audit_account_token,
                    overridden_base_url=overridden_base_url,
                )
                elapsed_seconds = time.perf_counter() - start_time
            finally:
                shutdown_stub_reviews_server(stub_server, stub_thread)
        finally:
            try:
                findings_path.unlink()
            except OSError:
                pass
        return completion, stub_server, elapsed_seconds

    def test_retry_succeeds_after_one_transient_502_response(self) -> None:
        completion, stub_server, elapsed_seconds = (
            self._run_retry_simulation_and_measure_elapsed(
                failure_count=FAILURE_COUNT_FOR_RETRY_SUCCESS
            )
        )
        self.assertEqual(
            completion.returncode,
            EXIT_CODE_SUCCESS,
            f"retry-success: expected exit {EXIT_CODE_SUCCESS}; got "
            f"{completion.returncode}; stdout={completion.stdout!r} "
            f"stderr={completion.stderr!r}",
        )
        self.assertEqual(
            stub_server.request_count,
            TOTAL_REQUEST_COUNT_FOR_RETRY_SUCCESS,
            f"retry-success: stub should have received exactly "
            f"{TOTAL_REQUEST_COUNT_FOR_RETRY_SUCCESS} POSTs (one 502 + "
            f"one 200); got {stub_server.request_count}",
        )
        expected_request_path = self._expected_reviews_request_path()
        self.assertEqual(
            stub_server.recorded_request_path,
            expected_request_path,
            f"retry-success: stub received POST at "
            f"{stub_server.recorded_request_path!r}; expected "
            f"{expected_request_path!r} per build_reviews_endpoint_url",
        )
        self.assertGreaterEqual(
            elapsed_seconds,
            EXPECTED_RETRY_SUCCESS_ELAPSED_LOWER_BOUND_SECONDS,
            f"retry-success should observe at least the first 1s backoff; "
            f"elapsed={elapsed_seconds:.2f}s",
        )

    def test_retry_exhausts_and_exits_two_after_four_consecutive_502_responses(
        self,
    ) -> None:
        completion, stub_server, elapsed_seconds = (
            self._run_retry_simulation_and_measure_elapsed(
                failure_count=FAILURE_COUNT_FOR_RETRY_EXHAUSTION
            )
        )
        self.assertEqual(
            completion.returncode,
            EXIT_CODE_RETRY_EXHAUSTED,
            f"retry-exhaustion: expected exit "
            f"{EXIT_CODE_RETRY_EXHAUSTED}; got "
            f"{completion.returncode}; stdout={completion.stdout!r} "
            f"stderr={completion.stderr!r}",
        )
        self.assertEqual(
            stub_server.request_count,
            TOTAL_REQUEST_COUNT_FOR_RETRY_EXHAUSTION,
            f"retry-exhaustion: stub should have received exactly "
            f"{TOTAL_REQUEST_COUNT_FOR_RETRY_EXHAUSTION} POSTs (one "
            f"initial plus three retries); got "
            f"{stub_server.request_count}",
        )
        expected_request_path = self._expected_reviews_request_path()
        self.assertEqual(
            stub_server.recorded_request_path,
            expected_request_path,
            f"retry-exhaustion: stub received POST at "
            f"{stub_server.recorded_request_path!r}; expected "
            f"{expected_request_path!r} per build_reviews_endpoint_url",
        )
        self.assertGreaterEqual(
            elapsed_seconds,
            EXPECTED_RETRY_EXHAUSTION_ELAPSED_LOWER_BOUND_SECONDS,
            f"retry-exhaustion should observe ~21s of backoff "
            f"(1s + 4s + 16s); elapsed={elapsed_seconds:.2f}s",
        )

    def _isolate_auth_env_vars(self) -> dict[str, str | None]:
        all_managed_env_var_names = (
            GH_TOKEN_ENV_VAR_NAME,
            GITHUB_TOKEN_ENV_VAR_NAME,
            BUGTEAM_REVIEWER_ACCOUNT_ENV_VAR_NAME,
        )
        previous_env_state: dict[str, str | None] = {
            each_name: os.environ.get(each_name)
            for each_name in all_managed_env_var_names
        }
        for each_name in all_managed_env_var_names:
            os.environ.pop(each_name, None)
        return previous_env_state

    def _restore_auth_env_vars(self, previous_env_state: dict[str, str | None]) -> None:
        for each_name, prior_value in previous_env_state.items():
            if prior_value is None:
                os.environ.pop(each_name, None)
            else:
                os.environ[each_name] = prior_value

    def test_query_active_gh_user_login_matches_gh_api_user_login_field(self) -> None:
        active_login = query_active_gh_user_login()
        self.assertTrue(
            active_login,
            "query_active_gh_user_login() returned empty",
        )
        gh_api_user_response = gh_api_object_json("user")
        self.assertEqual(active_login, gh_api_user_response.get("login"))

    def test_query_pull_request_author_login_matches_throwaway_pr_author(self) -> None:
        author_login = query_pull_request_author_login(
            owner=LIVE_TEST_OWNER,
            repo=LIVE_TEST_REPO,
            pr_number=self.pr_number,
        )
        pr_detail_path = (
            f"repos/{LIVE_TEST_OWNER}/{LIVE_TEST_REPO}/pulls/{self.pr_number}"
        )
        pr_detail_object = gh_api_object_json(pr_detail_path)
        user_field_object = pr_detail_object.get("user")
        self.assertIsInstance(user_field_object, dict)
        if isinstance(user_field_object, dict):
            self.assertEqual(author_login, user_field_object.get("login"))

    def test_list_authenticated_gh_account_logins_includes_active_and_audit_accounts(
        self,
    ) -> None:
        all_logins = list_authenticated_gh_account_logins()
        active_login = query_active_gh_user_login()
        self.assertIn(active_login, all_logins)
        self.assertIn(LIVE_TEST_AUDIT_ACCOUNT_NAME, all_logins)

    def test_fetch_gh_token_for_account_returns_audit_account_cached_token(
        self,
    ) -> None:
        fetched_token = fetch_gh_token_for_account(LIVE_TEST_AUDIT_ACCOUNT_NAME)
        self.assertEqual(fetched_token, self.audit_account_token)

    def test_resolve_reviewer_credentials_returns_env_var_when_gh_token_is_set(
        self,
    ) -> None:
        sentinel_env_token = "sentinel-gh-token-from-env-var-precedence-test"
        previous_env_state = self._isolate_auth_env_vars()
        try:
            os.environ[GH_TOKEN_ENV_VAR_NAME] = sentinel_env_token
            returned_token = resolve_reviewer_credentials(
                owner=LIVE_TEST_OWNER,
                repo=LIVE_TEST_REPO,
                pr_number=self.pr_number,
            ).token
            self.assertEqual(returned_token, sentinel_env_token)
        finally:
            self._restore_auth_env_vars(previous_env_state)

    def test_resolve_reviewer_credentials_toggles_to_alternate_token_on_self_pr(
        self,
    ) -> None:
        previous_env_state = self._isolate_auth_env_vars()
        try:
            returned_token = resolve_reviewer_credentials(
                owner=LIVE_TEST_OWNER,
                repo=LIVE_TEST_REPO,
                pr_number=self.pr_number,
            ).token
            active_login = query_active_gh_user_login()
            pr_author_login = query_pull_request_author_login(
                owner=LIVE_TEST_OWNER,
                repo=LIVE_TEST_REPO,
                pr_number=self.pr_number,
            )
            self.assertEqual(
                active_login.lower(),
                pr_author_login.lower(),
                "throwaway PR author must equal active gh account so the "
                "self-PR toggle branch is exercised",
            )
            all_alternates = [
                each_login
                for each_login in list_authenticated_gh_account_logins()
                if each_login.lower() != pr_author_login.lower()
            ]
            self.assertTrue(
                all_alternates,
                "test setup requires at least one alternate authenticated account",
            )
            expected_first_alternate_token = fetch_gh_token_for_account(
                all_alternates[0]
            )
            self.assertEqual(returned_token, expected_first_alternate_token)
            active_account_token = resolve_gh_auth_token()
            self.assertNotEqual(
                returned_token,
                active_account_token,
                "self-PR toggle must not return the active (author) token",
            )
        finally:
            self._restore_auth_env_vars(previous_env_state)

    def test_resolve_reviewer_credentials_honors_bugteam_reviewer_account_pin(
        self,
    ) -> None:
        previous_env_state = self._isolate_auth_env_vars()
        try:
            pr_author_login = query_pull_request_author_login(
                owner=LIVE_TEST_OWNER,
                repo=LIVE_TEST_REPO,
                pr_number=self.pr_number,
            )
            all_alternates_excluding_pr_author = [
                each_login
                for each_login in list_authenticated_gh_account_logins()
                if each_login.lower() != pr_author_login.lower()
            ]
            self.assertTrue(
                all_alternates_excluding_pr_author,
                "test setup requires at least one authenticated account that "
                "is not the PR author so the pin has a valid target",
            )
            chosen_pin_login = all_alternates_excluding_pr_author[0]
            os.environ[BUGTEAM_REVIEWER_ACCOUNT_ENV_VAR_NAME] = chosen_pin_login
            returned_token = resolve_reviewer_credentials(
                owner=LIVE_TEST_OWNER,
                repo=LIVE_TEST_REPO,
                pr_number=self.pr_number,
            ).token
            expected_pinned_token = fetch_gh_token_for_account(chosen_pin_login)
            self.assertEqual(returned_token, expected_pinned_token)
        finally:
            self._restore_auth_env_vars(previous_env_state)

    def test_resolve_reviewer_credentials_error_excludes_pr_author_from_candidate_set(
        self,
    ) -> None:
        unauthenticated_account_name = "intentionally-not-authenticated-account-zzz"
        previous_env_state = self._isolate_auth_env_vars()
        try:
            os.environ[BUGTEAM_REVIEWER_ACCOUNT_ENV_VAR_NAME] = (
                unauthenticated_account_name
            )
            with self.assertRaises(UserInputError) as raised_context:
                resolve_reviewer_credentials(
                    owner=LIVE_TEST_OWNER,
                    repo=LIVE_TEST_REPO,
                    pr_number=self.pr_number,
                )
            error_message_text = str(raised_context.exception)
            self.assertIn(unauthenticated_account_name, error_message_text)
            pr_author_login = query_pull_request_author_login(
                owner=LIVE_TEST_OWNER,
                repo=LIVE_TEST_REPO,
                pr_number=self.pr_number,
            )
            all_alternates_at_call_time = [
                each_login
                for each_login in list_authenticated_gh_account_logins()
                if each_login.lower() != pr_author_login.lower()
            ]
            self.assertIn(
                repr(all_alternates_at_call_time),
                error_message_text,
                "error must show the alternate-reviewer set actually searched",
            )
            self.assertNotIn(
                f"authenticated set [{repr(pr_author_login)}",
                error_message_text,
                "error must not show a set whose head is the excluded PR author",
            )
        finally:
            self._restore_auth_env_vars(previous_env_state)


OFFLINE_DUMMY_TOKEN = "offline-dummy-token"
OFFLINE_OWNER = "offline-owner"
OFFLINE_REPO = "offline-repo"
OFFLINE_PR_NUMBER = 1
OFFLINE_COMMIT_SHA = "0123456789abcdef0123456789abcdef01234567"
STUB_OK_REVIEW_HTML_URL = (
    "https://github.com/offline-owner/offline-repo/pull/1#pullrequestreview-1"
)
SELF_APPROVAL_422_MESSAGE = "Can not approve your own pull request"
MALFORMED_COMMENT_422_TOP_MESSAGE = "Validation Failed"
MALFORMED_COMMENT_422_DETAIL = "line must be part of the diff"
POST_AUDIT_THREAD_MODULE_NAME = "post_audit_thread"
GITHUB_API_BASE_URL_ATTRIBUTE = "GITHUB_API_BASE_URL"


class _SequencedReviewsServer(http.server.HTTPServer):
    """Serves a fixed response sequence and records each POST's JSON payload."""

    all_canned_responses: list[tuple[int, bytes]]
    next_response_index: int
    all_recorded_payloads: list[dict[str, object]]


class _SequencedReviewsHandler(http.server.BaseHTTPRequestHandler):
    """Records the POST body, then serves the next canned response in order."""

    def do_POST(self) -> None:
        owning_server = self.server
        if not isinstance(owning_server, _SequencedReviewsServer):
            raise AssertionError("handler bound to a non-sequenced server")
        content_length = int(self.headers.get(STUB_RESPONSE_HEADER_CONTENT_LENGTH, "0"))
        parsed_body: object = json.loads(
            self.rfile.read(content_length).decode("utf-8")
        )
        if isinstance(parsed_body, dict):
            owning_server.all_recorded_payloads.append(parsed_body)
        response_index = min(
            owning_server.next_response_index,
            len(owning_server.all_canned_responses) - 1,
        )
        owning_server.next_response_index += 1
        response_status, response_body_bytes = owning_server.all_canned_responses[
            response_index
        ]
        self.send_response(response_status)
        self.send_header(
            STUB_RESPONSE_HEADER_CONTENT_TYPE, STUB_RESPONSE_CONTENT_TYPE_VALUE
        )
        self.send_header(
            STUB_RESPONSE_HEADER_CONTENT_LENGTH, str(len(response_body_bytes))
        )
        self.end_headers()
        self.wfile.write(response_body_bytes)

    def log_message(self, format: str, *args: object) -> None:
        return


def _json_response_bytes(response_payload: dict[str, object]) -> bytes:
    return json.dumps(response_payload).encode("utf-8")


def _ok_review_response() -> tuple[int, bytes]:
    return STUB_HTTP_STATUS_OK, _json_response_bytes(
        {"html_url": STUB_OK_REVIEW_HTML_URL}
    )


def _self_approval_422_response() -> tuple[int, bytes]:
    return HTTP_STATUS_UNPROCESSABLE_ENTITY, _json_response_bytes(
        {"message": SELF_APPROVAL_422_MESSAGE}
    )


def _malformed_comment_422_response() -> tuple[int, bytes]:
    return HTTP_STATUS_UNPROCESSABLE_ENTITY, _json_response_bytes(
        {
            "message": MALFORMED_COMMENT_422_TOP_MESSAGE,
            "errors": [{"message": MALFORMED_COMMENT_422_DETAIL}],
        }
    )


def _bad_gateway_response() -> tuple[int, bytes]:
    return STUB_HTTP_STATUS_BAD_GATEWAY, _json_response_bytes(
        {"message": "stub simulated transient 502"}
    )


def _offline_findings_payload() -> list[dict[str, object]]:
    return [
        {
            JSON_FIELD_PATH: "offline-fixture.md",
            JSON_FIELD_LINE: 1,
            JSON_FIELD_SIDE: INLINE_COMMENT_SIDE_RIGHT,
            JSON_FIELD_SEVERITY: SEVERITY_TAG_P0,
            JSON_FIELD_DESCRIPTION: "Offline finding one.",
            JSON_FIELD_FIX_SUMMARY: "Offline fix one.",
        }
    ]


def _offline_namespace(state_argument: str, findings_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        skill=SKILL_BUGTEAM,
        owner=OFFLINE_OWNER,
        repo=OFFLINE_REPO,
        pr_number=OFFLINE_PR_NUMBER,
        commit=OFFLINE_COMMIT_SHA,
        state=state_argument,
        findings_json=findings_path,
    )


def _restore_env_var(env_var_name: str, previous_value: str | None) -> None:
    if previous_value is None:
        os.environ.pop(env_var_name, None)
    else:
        os.environ[env_var_name] = previous_value


def _payload_field_text(payload: dict[str, object], field_name: str) -> str:
    field_value = payload[field_name]
    if not isinstance(field_value, str):
        raise AssertionError(
            f"expected str for {field_name!r}, got {type(field_value).__name__}"
        )
    return field_value


def _call_post_audit_review_capturing(
    parsed_arguments: argparse.Namespace,
) -> tuple[AuditReviewOutcome | None, BaseException | None]:
    try:
        return post_audit_review(parsed_arguments), None
    except (UserInputError, RetryExhaustedError) as raised_error:
        return None, raised_error


def spawn_sequenced_reviews_server(
    all_canned_responses: list[tuple[int, bytes]],
) -> tuple[_SequencedReviewsServer, threading.Thread]:
    stub_server = _SequencedReviewsServer(
        (STUB_SERVER_HOST, STUB_SERVER_PORT_DYNAMIC), _SequencedReviewsHandler
    )
    stub_server.all_canned_responses = list(all_canned_responses)
    stub_server.next_response_index = 0
    stub_server.all_recorded_payloads = []
    stub_thread = threading.Thread(target=stub_server.serve_forever, daemon=True)
    stub_thread.start()
    return stub_server, stub_thread


def _run_review_capturing(
    state_argument: str,
    findings_payload: list[dict[str, object]],
    all_canned_responses: list[tuple[int, bytes]],
) -> tuple[AuditReviewOutcome | None, BaseException | None, _SequencedReviewsServer]:
    findings_path = write_findings_json(findings_payload)
    stub_server, stub_thread = spawn_sequenced_reviews_server(all_canned_responses)
    post_audit_module = sys.modules[POST_AUDIT_THREAD_MODULE_NAME]
    previous_base_url: str = getattr(post_audit_module, GITHUB_API_BASE_URL_ATTRIBUTE)
    previous_token = os.environ.get(GH_TOKEN_ENV_VAR_NAME)
    stub_base_url = stub_reviews_server_base_url(stub_server)
    try:
        setattr(post_audit_module, GITHUB_API_BASE_URL_ATTRIBUTE, stub_base_url)
        os.environ[GH_TOKEN_ENV_VAR_NAME] = OFFLINE_DUMMY_TOKEN
        captured_outcome, captured_error = _call_post_audit_review_capturing(
            _offline_namespace(state_argument, findings_path)
        )
    finally:
        setattr(post_audit_module, GITHUB_API_BASE_URL_ATTRIBUTE, previous_base_url)
        _restore_env_var(GH_TOKEN_ENV_VAR_NAME, previous_token)
        shutdown_stub_reviews_server(stub_server, stub_thread)
        findings_path.unlink(missing_ok=True)
    return captured_outcome, captured_error, stub_server


class OfflinePostAuditThreadDowngradeTests(unittest.TestCase):
    """Offline coverage of the self-approval COMMENT downgrade via a localhost stub.

    Each test drives the real ``post_audit_thread`` pipeline against a sequenced
    localhost stub, with ``GH_TOKEN`` set so token resolution short-circuits and
    the 422 self-approval path runs through the real ``urlopen``.
    """

    def test_review_event_for_state_maps_state_and_downgrade(self) -> None:
        self.assertEqual(
            review_event_for_state(STATE_CLEAN, False), GITHUB_REVIEW_EVENT_APPROVE
        )
        self.assertEqual(
            review_event_for_state(STATE_DIRTY, False),
            GITHUB_REVIEW_EVENT_REQUEST_CHANGES,
        )
        self.assertEqual(
            review_event_for_state(STATE_CLEAN, True), GITHUB_REVIEW_EVENT_COMMENT
        )
        self.assertEqual(
            review_event_for_state(STATE_DIRTY, True), GITHUB_REVIEW_EVENT_COMMENT
        )

    def test_build_review_request_payload_downgrade_sets_comment_event(self) -> None:
        request_payload = build_review_request_payload(
            state_argument=STATE_CLEAN,
            commit_sha=OFFLINE_COMMIT_SHA,
            review_body_text="review body",
            all_inline_comments=[],
            did_downgrade=True,
        )
        self.assertEqual(
            request_payload[REVIEW_REQUEST_FIELD_EVENT], GITHUB_REVIEW_EVENT_COMMENT
        )
        self.assertEqual(request_payload[REVIEW_REQUEST_FIELD_BODY], "review body")

    def test_append_disclosure_keeps_first_line_and_adds_clean_sentence(self) -> None:
        original_body = "**Bugteam audit completed** —— Clean — no findings\n\nbody"
        appended_body = append_self_approval_disclosure(original_body, STATE_CLEAN)
        self.assertEqual(appended_body.splitlines()[0], original_body.splitlines()[0])
        self.assertTrue(
            appended_body.endswith(SELF_APPROVAL_DOWNGRADE_DISCLOSURE_CLEAN)
        )

    def test_env_token_resolves_credentials_without_downgrade(self) -> None:
        previous_token = os.environ.get(GH_TOKEN_ENV_VAR_NAME)
        try:
            os.environ[GH_TOKEN_ENV_VAR_NAME] = OFFLINE_DUMMY_TOKEN
            credentials = resolve_reviewer_credentials(
                owner=OFFLINE_OWNER, repo=OFFLINE_REPO, pr_number=OFFLINE_PR_NUMBER
            )
        finally:
            _restore_env_var(GH_TOKEN_ENV_VAR_NAME, previous_token)
        self.assertIsInstance(credentials, ReviewerCredentials)
        self.assertEqual(credentials.token, OFFLINE_DUMMY_TOKEN)
        self.assertFalse(credentials.did_downgrade)

    def test_clean_self_pr_422_downgrades_to_comment_event(self) -> None:
        outcome, error, stub_server = _run_review_capturing(
            STATE_CLEAN, [], [_self_approval_422_response(), _ok_review_response()]
        )
        self.assertIsNone(error)
        assert isinstance(outcome, AuditReviewOutcome)
        self.assertIsInstance(outcome, AuditReviewOutcome)
        self.assertTrue(outcome.did_downgrade)
        self.assertEqual(len(stub_server.all_recorded_payloads), 2)
        first_payload = stub_server.all_recorded_payloads[0]
        downgrade_payload = stub_server.all_recorded_payloads[1]
        self.assertEqual(
            first_payload[REVIEW_REQUEST_FIELD_EVENT], GITHUB_REVIEW_EVENT_APPROVE
        )
        self.assertEqual(
            downgrade_payload[REVIEW_REQUEST_FIELD_EVENT], GITHUB_REVIEW_EVENT_COMMENT
        )

    def test_clean_downgrade_appends_disclosure_below_the_first_line(self) -> None:
        outcome, error, stub_server = _run_review_capturing(
            STATE_CLEAN, [], [_self_approval_422_response(), _ok_review_response()]
        )
        self.assertIsNone(error)
        first_body = _payload_field_text(
            stub_server.all_recorded_payloads[0], REVIEW_REQUEST_FIELD_BODY
        )
        downgrade_body = _payload_field_text(
            stub_server.all_recorded_payloads[1], REVIEW_REQUEST_FIELD_BODY
        )
        self.assertEqual(downgrade_body.splitlines()[0], first_body.splitlines()[0])
        self.assertTrue(
            downgrade_body.endswith(SELF_APPROVAL_DOWNGRADE_DISCLOSURE_CLEAN)
        )

    def test_dirty_self_pr_422_downgrades_to_comment_with_findings(self) -> None:
        outcome, error, stub_server = _run_review_capturing(
            STATE_DIRTY,
            _offline_findings_payload(),
            [_self_approval_422_response(), _ok_review_response()],
        )
        self.assertIsNone(error)
        assert isinstance(outcome, AuditReviewOutcome)
        self.assertTrue(outcome.did_downgrade)
        downgrade_payload = stub_server.all_recorded_payloads[1]
        self.assertEqual(
            downgrade_payload[REVIEW_REQUEST_FIELD_EVENT], GITHUB_REVIEW_EVENT_COMMENT
        )
        downgrade_body = _payload_field_text(
            downgrade_payload, REVIEW_REQUEST_FIELD_BODY
        )
        self.assertIn(SELF_APPROVAL_DOWNGRADE_DISCLOSURE_DIRTY, downgrade_body)
        all_inline_comments = downgrade_payload[REVIEW_REQUEST_FIELD_COMMENTS]
        self.assertIsInstance(all_inline_comments, list)
        assert isinstance(all_inline_comments, list)
        self.assertEqual(len(all_inline_comments), 1)

    def test_non_downgrade_clean_posts_approve_without_disclosure(self) -> None:
        outcome, error, stub_server = _run_review_capturing(
            STATE_CLEAN, [], [_ok_review_response()]
        )
        self.assertIsNone(error)
        assert isinstance(outcome, AuditReviewOutcome)
        self.assertFalse(outcome.did_downgrade)
        self.assertEqual(len(stub_server.all_recorded_payloads), 1)
        only_payload = stub_server.all_recorded_payloads[0]
        self.assertEqual(
            only_payload[REVIEW_REQUEST_FIELD_EVENT], GITHUB_REVIEW_EVENT_APPROVE
        )
        approve_body = _payload_field_text(only_payload, REVIEW_REQUEST_FIELD_BODY)
        self.assertNotIn(SELF_APPROVAL_DOWNGRADE_DISCLOSURE_CLEAN, approve_body)

    def test_self_approval_422_downgrades_once_without_laddering(self) -> None:
        outcome, error, stub_server = _run_review_capturing(
            STATE_CLEAN, [], [_self_approval_422_response(), _ok_review_response()]
        )
        self.assertIsNone(error)
        assert isinstance(outcome, AuditReviewOutcome)
        self.assertTrue(outcome.did_downgrade)
        self.assertEqual(len(stub_server.all_recorded_payloads), 2)

    def test_malformed_comment_422_raises_without_downgrade_or_retry(self) -> None:
        outcome, error, stub_server = _run_review_capturing(
            STATE_CLEAN,
            [],
            [_malformed_comment_422_response(), _ok_review_response()],
        )
        self.assertIsNone(outcome)
        self.assertIsInstance(error, RetryExhaustedError)
        self.assertEqual(len(stub_server.all_recorded_payloads), 1)
        self.assertIn(MALFORMED_COMMENT_422_DETAIL, str(error))

    def test_five_hundred_response_still_ladders_before_success(self) -> None:
        outcome, error, stub_server = _run_review_capturing(
            STATE_CLEAN, [], [_bad_gateway_response(), _ok_review_response()]
        )
        self.assertIsNone(error)
        assert isinstance(outcome, AuditReviewOutcome)
        self.assertFalse(outcome.did_downgrade)
        self.assertEqual(len(stub_server.all_recorded_payloads), 2)

    def test_post_review_with_retries_returns_posted_review_on_success(self) -> None:
        stub_server, stub_thread = spawn_sequenced_reviews_server(
            [_ok_review_response()]
        )
        post_audit_module = sys.modules[POST_AUDIT_THREAD_MODULE_NAME]
        previous_base_url: str = getattr(
            post_audit_module, GITHUB_API_BASE_URL_ATTRIBUTE
        )
        stub_base_url = stub_reviews_server_base_url(stub_server)
        try:
            setattr(post_audit_module, GITHUB_API_BASE_URL_ATTRIBUTE, stub_base_url)
            endpoint_url = build_reviews_endpoint_url(
                OFFLINE_OWNER, OFFLINE_REPO, OFFLINE_PR_NUMBER
            )
            posted_review = post_review_with_retries(
                endpoint_url,
                OFFLINE_DUMMY_TOKEN,
                {},
                should_downgrade_on_self_approval=False,
            )
        finally:
            setattr(post_audit_module, GITHUB_API_BASE_URL_ATTRIBUTE, previous_base_url)
            shutdown_stub_reviews_server(stub_server, stub_thread)
        self.assertEqual(posted_review.html_url, STUB_OK_REVIEW_HTML_URL)

    def _invoke_main_against_stub(
        self,
        state_argument: str,
        all_canned_responses: list[tuple[int, bytes]],
    ) -> subprocess.CompletedProcess[str]:
        findings_path = write_findings_json([])
        stub_server, stub_thread = spawn_sequenced_reviews_server(all_canned_responses)
        try:
            completion = invoke_post_audit_thread_with_url_override(
                pr_number=OFFLINE_PR_NUMBER,
                head_sha=OFFLINE_COMMIT_SHA,
                state_argument=state_argument,
                findings_json_path=findings_path,
                audit_token=OFFLINE_DUMMY_TOKEN,
                overridden_base_url=stub_reviews_server_base_url(stub_server),
            )
        finally:
            shutdown_stub_reviews_server(stub_server, stub_thread)
            findings_path.unlink(missing_ok=True)
        return completion

    def test_main_stdout_is_one_line_without_downgrade(self) -> None:
        completion = self._invoke_main_against_stub(
            STATE_CLEAN, [_ok_review_response()]
        )
        self.assertEqual(completion.returncode, EXIT_CODE_SUCCESS)
        self.assertEqual(len(completion.stdout.strip().splitlines()), 1)

    def test_main_stdout_adds_marker_line_on_downgrade(self) -> None:
        completion = self._invoke_main_against_stub(
            STATE_CLEAN, [_self_approval_422_response(), _ok_review_response()]
        )
        self.assertEqual(completion.returncode, EXIT_CODE_SUCCESS)
        all_stdout_lines = completion.stdout.strip().splitlines()
        self.assertEqual(len(all_stdout_lines), 2)
        self.assertEqual(all_stdout_lines[1], SELF_APPROVAL_DOWNGRADE_STDOUT_MARKER)


def _two_severity_findings() -> list[AuditFinding]:
    return [
        AuditFinding(
            path="alpha.md",
            line=1,
            side=INLINE_COMMENT_SIDE_RIGHT,
            severity=SEVERITY_TAG_P0,
            description="Finding alpha.",
            fix_summary="Fix alpha.",
        ),
        AuditFinding(
            path="beta.md",
            line=2,
            side=INLINE_COMMENT_SIDE_RIGHT,
            severity=SEVERITY_TAG_P1,
            description="Finding beta.",
            fix_summary="Fix beta.",
        ),
    ]


class PublicFunctionCoverageTests(unittest.TestCase):
    """Behavioral coverage for the remaining public helpers of post_audit_thread."""

    def test_parse_command_line_arguments_binds_every_flag(self) -> None:
        parsed_arguments = parse_command_line_arguments(
            [
                CLI_FLAG_SKILL,
                SKILL_BUGTEAM,
                CLI_FLAG_OWNER,
                OFFLINE_OWNER,
                CLI_FLAG_REPO,
                OFFLINE_REPO,
                CLI_FLAG_PR_NUMBER,
                str(OFFLINE_PR_NUMBER),
                CLI_FLAG_COMMIT,
                OFFLINE_COMMIT_SHA,
                CLI_FLAG_STATE,
                STATE_CLEAN,
                CLI_FLAG_FINDINGS_JSON,
                "findings.json",
            ]
        )
        self.assertEqual(parsed_arguments.skill, SKILL_BUGTEAM)
        self.assertEqual(parsed_arguments.pr_number, OFFLINE_PR_NUMBER)
        self.assertEqual(parsed_arguments.state, STATE_CLEAN)

    def test_parse_findings_json_file_reads_findings_and_empty_array(self) -> None:
        findings_path = write_findings_json(_offline_findings_payload())
        empty_path = write_findings_json([])
        try:
            all_findings = parse_findings_json_file(findings_path)
            no_findings = parse_findings_json_file(empty_path)
        finally:
            findings_path.unlink(missing_ok=True)
            empty_path.unlink(missing_ok=True)
        self.assertEqual(len(all_findings), 1)
        self.assertIsInstance(all_findings[0], AuditFinding)
        self.assertEqual(all_findings[0].path, "offline-fixture.md")
        self.assertEqual(no_findings, [])

    def test_extract_audit_body_skeleton_returns_text_between_markers(self) -> None:
        skeleton_text = "body <Skill> line"
        template_markdown = (
            f"intro\n{AUDIT_BODY_SKELETON_OPEN_MARKER}\n"
            f"{TEMPLATE_FENCE_TOKEN}\n{skeleton_text}\n{TEMPLATE_FENCE_TOKEN}\n"
            f"{AUDIT_BODY_SKELETON_CLOSE_MARKER}\nrest"
        )
        self.assertEqual(extract_audit_body_skeleton(template_markdown), skeleton_text)

    def test_load_audit_body_skeleton_reads_the_shipped_template(self) -> None:
        loaded_skeleton = load_audit_body_skeleton()
        self.assertIn(PLACEHOLDER_SKILL, loaded_skeleton)
        self.assertTrue(loaded_skeleton.strip())

    def test_short_commit_sha_truncates_to_the_short_length(self) -> None:
        shortened = short_commit_sha(OFFLINE_COMMIT_SHA)
        self.assertEqual(len(shortened), SHORT_SHA_LENGTH)
        self.assertTrue(OFFLINE_COMMIT_SHA.startswith(shortened))

    def test_skill_display_name_title_cases_the_skill(self) -> None:
        self.assertEqual(skill_display_name(SKILL_BUGTEAM), "Bugteam")

    def test_severity_counts_by_tag_tallies_each_supported_tag(self) -> None:
        counts_by_tag = severity_counts_by_tag(_two_severity_findings())
        self.assertEqual(counts_by_tag[SEVERITY_TAG_P0], 1)
        self.assertEqual(counts_by_tag[SEVERITY_TAG_P1], 1)
        self.assertEqual(counts_by_tag[SEVERITY_TAG_P2], 0)

    def test_build_details_block_renders_bullets_and_empties_on_no_findings(
        self,
    ) -> None:
        details_markdown = build_details_block(_two_severity_findings())
        self.assertIn("alpha.md", details_markdown)
        self.assertIn("<details>", details_markdown)
        self.assertEqual(build_details_block([]), "")

    def test_fill_audit_body_skeleton_substitutes_the_skill_placeholder(self) -> None:
        filled_body = fill_audit_body_skeleton(
            skeleton_text=f"skill: {PLACEHOLDER_SKILL}",
            skill_argument=SKILL_BUGTEAM,
            state_argument=STATE_CLEAN,
            commit_sha=OFFLINE_COMMIT_SHA,
            all_findings=[],
        )
        self.assertIn("Bugteam", filled_body)
        self.assertNotIn(PLACEHOLDER_SKILL, filled_body)

    def test_build_inline_comments_payload_maps_each_finding(self) -> None:
        all_comments = build_inline_comments_payload(
            SKILL_BUGTEAM, _two_severity_findings()
        )
        self.assertEqual(len(all_comments), 2)
        self.assertEqual(all_comments[0]["path"], "alpha.md")
        self.assertEqual(all_comments[0]["line"], 1)
        self.assertEqual(all_comments[0]["side"], INLINE_COMMENT_SIDE_RIGHT)

    def test_resolve_github_token_returns_the_env_token(self) -> None:
        previous_token = os.environ.get(GH_TOKEN_ENV_VAR_NAME)
        try:
            os.environ[GH_TOKEN_ENV_VAR_NAME] = OFFLINE_DUMMY_TOKEN
            resolved_token = resolve_github_token()
        finally:
            _restore_env_var(GH_TOKEN_ENV_VAR_NAME, previous_token)
        self.assertEqual(resolved_token, OFFLINE_DUMMY_TOKEN)

    def test_execute_review_post_attempt_returns_status_and_body(self) -> None:
        stub_server, stub_thread = spawn_sequenced_reviews_server(
            [_ok_review_response()]
        )
        post_audit_module = sys.modules[POST_AUDIT_THREAD_MODULE_NAME]
        previous_base_url: str = getattr(
            post_audit_module, GITHUB_API_BASE_URL_ATTRIBUTE
        )
        stub_base_url = stub_reviews_server_base_url(stub_server)
        try:
            setattr(post_audit_module, GITHUB_API_BASE_URL_ATTRIBUTE, stub_base_url)
            endpoint_url = build_reviews_endpoint_url(
                OFFLINE_OWNER, OFFLINE_REPO, OFFLINE_PR_NUMBER
            )
            status_code, response_text = execute_review_post_attempt(
                endpoint_url, OFFLINE_DUMMY_TOKEN, {}
            )
        finally:
            setattr(post_audit_module, GITHUB_API_BASE_URL_ATTRIBUTE, previous_base_url)
            shutdown_stub_reviews_server(stub_server, stub_thread)
        self.assertEqual(status_code, STUB_HTTP_STATUS_OK)
        self.assertIn(STUB_OK_REVIEW_HTML_URL, response_text)

    def test_extract_html_url_field_reads_the_html_url(self) -> None:
        response_text = json.dumps({"html_url": STUB_OK_REVIEW_HTML_URL})
        self.assertEqual(extract_html_url_field(response_text), STUB_OK_REVIEW_HTML_URL)


if __name__ == "__main__":
    unittest.main()
