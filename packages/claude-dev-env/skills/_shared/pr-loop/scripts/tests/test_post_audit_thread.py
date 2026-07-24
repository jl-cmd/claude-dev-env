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
    ALL_SUPPORTED_SEVERITY_TAGS,
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
    EXIT_CODE_RETRY_EXHAUSTED,
    GH_TOKEN_ENV_VAR_NAME,
    GITHUB_REVIEW_EVENT_APPROVE,
    GITHUB_REVIEW_EVENT_REQUEST_CHANGES,
    GITHUB_TOKEN_ENV_VAR_NAME,
    INLINE_COMMENT_FIELD_BODY,
    INLINE_COMMENT_FIELD_LINE,
    INLINE_COMMENT_FIELD_PATH,
    INLINE_COMMENT_FIELD_SIDE,
    INLINE_COMMENT_SIDE_RIGHT,
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
    SEVERITY_TAG_P0,
    SEVERITY_TAG_P1,
    SEVERITY_TAG_P2,
    SHORT_SHA_LENGTH,
    SINGLE_REVIEW_API_PATH_TEMPLATE,
    SINGLE_REVIEW_COMMENTS_API_PATH_TEMPLATE,
    SKILL_BUGTEAM,
    STATE_CLEAN,
    STATE_DIRTY,
    TEMPLATE_FENCE_TOKEN,
)
import post_audit_thread  # noqa: E402
from post_audit_thread import (  # noqa: E402
    AuditFinding,
    UserInputError,
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
    resolve_reviewer_token,
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
    {
        "html_url": (
            "https://github.com/stub-host/stub-repo/pull/0#pullrequestreview-1"
        )
    }
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
        self._assert_review_state_for_url(
            emitted_html_url, GH_EVENT_CHANGES_REQUESTED
        )
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

    def _restore_auth_env_vars(
        self, previous_env_state: dict[str, str | None]
    ) -> None:
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
        pr_detail_path = f"repos/{LIVE_TEST_OWNER}/{LIVE_TEST_REPO}/pulls/{self.pr_number}"
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

    def test_fetch_gh_token_for_account_returns_audit_account_cached_token(self) -> None:
        fetched_token = fetch_gh_token_for_account(LIVE_TEST_AUDIT_ACCOUNT_NAME)
        self.assertEqual(fetched_token, self.audit_account_token)

    def test_resolve_reviewer_token_returns_env_var_when_gh_token_is_set(self) -> None:
        sentinel_env_token = "sentinel-gh-token-from-env-var-precedence-test"
        previous_env_state = self._isolate_auth_env_vars()
        try:
            os.environ[GH_TOKEN_ENV_VAR_NAME] = sentinel_env_token
            returned_token = resolve_reviewer_token(
                owner=LIVE_TEST_OWNER,
                repo=LIVE_TEST_REPO,
                pr_number=self.pr_number,
            )
            self.assertEqual(returned_token, sentinel_env_token)
        finally:
            self._restore_auth_env_vars(previous_env_state)

    def test_resolve_reviewer_token_toggles_to_alternate_token_on_self_pr(self) -> None:
        previous_env_state = self._isolate_auth_env_vars()
        try:
            returned_token = resolve_reviewer_token(
                owner=LIVE_TEST_OWNER,
                repo=LIVE_TEST_REPO,
                pr_number=self.pr_number,
            )
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

    def test_resolve_reviewer_token_honors_bugteam_reviewer_account_pin(self) -> None:
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
            returned_token = resolve_reviewer_token(
                owner=LIVE_TEST_OWNER,
                repo=LIVE_TEST_REPO,
                pr_number=self.pr_number,
            )
            expected_pinned_token = fetch_gh_token_for_account(chosen_pin_login)
            self.assertEqual(returned_token, expected_pinned_token)
        finally:
            self._restore_auth_env_vars(previous_env_state)

    def test_resolve_reviewer_token_error_excludes_pr_author_from_candidate_set(
        self,
    ) -> None:
        unauthenticated_account_name = "intentionally-not-authenticated-account-zzz"
        previous_env_state = self._isolate_auth_env_vars()
        try:
            os.environ[BUGTEAM_REVIEWER_ACCOUNT_ENV_VAR_NAME] = (
                unauthenticated_account_name
            )
            with self.assertRaises(UserInputError) as raised_context:
                resolve_reviewer_token(
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


class PostAuditThreadUnitTests(unittest.TestCase):
    """Offline unit tests for post_audit_thread.py functions.

    Each test calls a real production function with deterministic inputs.
    The HTTP-touching functions run against the in-process localhost stub
    server; the token resolver runs through an environment-variable
    short-circuit. None of these tests contact api.github.com.
    """

    def _write_findings_file(self, findings_payload: list[dict[str, Any]]) -> Path:
        findings_path = write_findings_json(findings_payload)
        self.addCleanup(findings_path.unlink, missing_ok=True)
        return findings_path

    def _sample_finding(self, severity: str, line_number: int) -> AuditFinding:
        return AuditFinding(
            path="src/example.py",
            line=line_number,
            side=INLINE_COMMENT_SIDE_RIGHT,
            severity=severity,
            description=f"Example {severity} finding.",
            fix_summary=f"Fix the {severity} issue.",
        )

    def test_parse_command_line_arguments_populates_every_field(self) -> None:
        parsed_arguments = parse_command_line_arguments(
            [
                CLI_FLAG_SKILL, SKILL_BUGTEAM,
                CLI_FLAG_OWNER, "acme",
                CLI_FLAG_REPO, "widgets",
                CLI_FLAG_PR_NUMBER, "42",
                CLI_FLAG_COMMIT, "abcdef1234567890",
                CLI_FLAG_STATE, STATE_CLEAN,
                CLI_FLAG_FINDINGS_JSON, "/tmp/findings.json",
            ]
        )
        self.assertEqual(parsed_arguments.skill, SKILL_BUGTEAM)
        self.assertEqual(parsed_arguments.owner, "acme")
        self.assertEqual(parsed_arguments.repo, "widgets")
        self.assertEqual(parsed_arguments.pr_number, 42)
        self.assertEqual(parsed_arguments.commit, "abcdef1234567890")
        self.assertEqual(parsed_arguments.state, STATE_CLEAN)
        self.assertEqual(parsed_arguments.findings_json, Path("/tmp/findings.json"))

    def test_parse_command_line_arguments_rejects_unknown_state(self) -> None:
        with self.assertRaises(UserInputError):
            parse_command_line_arguments(
                [
                    CLI_FLAG_SKILL, SKILL_BUGTEAM,
                    CLI_FLAG_OWNER, "acme",
                    CLI_FLAG_REPO, "widgets",
                    CLI_FLAG_PR_NUMBER, "42",
                    CLI_FLAG_COMMIT, "abcdef1",
                    CLI_FLAG_STATE, "SIDEWAYS",
                    CLI_FLAG_FINDINGS_JSON, "/tmp/findings.json",
                ]
            )

    def test_parse_findings_json_file_returns_typed_findings(self) -> None:
        findings_path = self._write_findings_file(
            [
                {
                    JSON_FIELD_PATH: "src/a.py",
                    JSON_FIELD_LINE: 12,
                    JSON_FIELD_SIDE: INLINE_COMMENT_SIDE_RIGHT,
                    JSON_FIELD_SEVERITY: SEVERITY_TAG_P0,
                    JSON_FIELD_DESCRIPTION: "Null dereference.",
                    JSON_FIELD_FIX_SUMMARY: "Add a guard.",
                }
            ]
        )
        parsed_findings = parse_findings_json_file(findings_path)
        self.assertEqual(len(parsed_findings), 1)
        self.assertEqual(parsed_findings[0].path, "src/a.py")
        self.assertEqual(parsed_findings[0].line, 12)
        self.assertEqual(parsed_findings[0].severity, SEVERITY_TAG_P0)
        self.assertEqual(parsed_findings[0].fix_summary, "Add a guard.")

    def test_parse_findings_json_file_empty_array_returns_empty_list(self) -> None:
        findings_path = self._write_findings_file([])
        self.assertEqual(parse_findings_json_file(findings_path), [])

    def test_parse_findings_json_file_rejects_line_below_one(self) -> None:
        findings_path = self._write_findings_file(
            [
                {
                    JSON_FIELD_PATH: "src/a.py",
                    JSON_FIELD_LINE: 0,
                    JSON_FIELD_SIDE: INLINE_COMMENT_SIDE_RIGHT,
                    JSON_FIELD_SEVERITY: SEVERITY_TAG_P0,
                    JSON_FIELD_DESCRIPTION: "Bad line number.",
                    JSON_FIELD_FIX_SUMMARY: "Use a one-based line.",
                }
            ]
        )
        with self.assertRaises(UserInputError):
            parse_findings_json_file(findings_path)

    def test_extract_audit_body_skeleton_returns_text_between_markers(self) -> None:
        skeleton_body = "**<Skill> audit completed** —— <state_label>"
        template_markdown = (
            "intro line\n"
            + AUDIT_BODY_SKELETON_OPEN_MARKER + "\n"
            + TEMPLATE_FENCE_TOKEN + "\n"
            + skeleton_body + "\n"
            + TEMPLATE_FENCE_TOKEN + "\n"
            + AUDIT_BODY_SKELETON_CLOSE_MARKER + "\n"
            "outro line\n"
        )
        self.assertEqual(
            extract_audit_body_skeleton(template_markdown), skeleton_body
        )

    def test_load_audit_body_skeleton_reads_shipped_template(self) -> None:
        skeleton_text = load_audit_body_skeleton()
        self.assertIn(PLACEHOLDER_SKILL, skeleton_text)
        self.assertIn(PLACEHOLDER_HEADING, skeleton_text)

    def test_short_commit_sha_truncates_to_configured_length(self) -> None:
        full_sha = "abcdef1234567890"
        self.assertEqual(short_commit_sha(full_sha), full_sha[:SHORT_SHA_LENGTH])
        self.assertEqual(len(short_commit_sha(full_sha)), SHORT_SHA_LENGTH)

    def test_skill_display_name_title_cases_identifier(self) -> None:
        self.assertEqual(skill_display_name(SKILL_BUGTEAM), "Bugteam")
        self.assertEqual(skill_display_name("findbugs"), "Findbugs")

    def test_severity_counts_by_tag_tallies_and_zero_fills(self) -> None:
        all_findings = [
            self._sample_finding(SEVERITY_TAG_P0, 1),
            self._sample_finding(SEVERITY_TAG_P0, 2),
            self._sample_finding(SEVERITY_TAG_P1, 3),
        ]
        counts_by_tag = severity_counts_by_tag(all_findings)
        self.assertEqual(counts_by_tag[SEVERITY_TAG_P0], 2)
        self.assertEqual(counts_by_tag[SEVERITY_TAG_P1], 1)
        self.assertEqual(counts_by_tag[SEVERITY_TAG_P2], 0)
        self.assertEqual(set(counts_by_tag), set(ALL_SUPPORTED_SEVERITY_TAGS))

    def test_build_details_block_empty_findings_returns_empty_string(self) -> None:
        self.assertEqual(build_details_block([]), "")

    def test_build_details_block_renders_one_bullet_per_finding(self) -> None:
        all_findings = [
            self._sample_finding(SEVERITY_TAG_P0, 10),
            self._sample_finding(SEVERITY_TAG_P1, 20),
        ]
        details_block = build_details_block(all_findings)
        self.assertIn("<details>", details_block)
        self.assertIn("</details>", details_block)
        self.assertIn("src/example.py:10", details_block)
        self.assertIn("src/example.py:20", details_block)
        self.assertEqual(details_block.count("- **["), len(all_findings))

    def test_fill_audit_body_skeleton_substitutes_placeholders(self) -> None:
        skeleton_text = (
            f"{PLACEHOLDER_SKILL} {PLACEHOLDER_STATE_LABEL} {PLACEHOLDER_HEADING} "
            f"{PLACEHOLDER_SUMMARY_PARAGRAPH} findings={PLACEHOLDER_FINDINGS_COUNT} "
            f"{PLACEHOLDER_P0_COUNT}/{PLACEHOLDER_P1_COUNT}/{PLACEHOLDER_P2_COUNT} "
            f"{PLACEHOLDER_DETAILS_BLOCK}"
        )
        filled_body = fill_audit_body_skeleton(
            skeleton_text=skeleton_text,
            skill_argument=SKILL_BUGTEAM,
            state_argument=STATE_DIRTY,
            commit_sha="abcdef1234567890",
            all_findings=[self._sample_finding(SEVERITY_TAG_P0, 5)],
        )
        self.assertIn("Bugteam", filled_body)
        self.assertNotIn(PLACEHOLDER_SKILL, filled_body)
        self.assertNotIn(PLACEHOLDER_FINDINGS_COUNT, filled_body)
        self.assertIn("findings=1", filled_body)

    def test_build_inline_comments_payload_shapes_each_comment(self) -> None:
        all_findings = [self._sample_finding(SEVERITY_TAG_P0, 7)]
        inline_comments = build_inline_comments_payload(SKILL_BUGTEAM, all_findings)
        self.assertEqual(len(inline_comments), 1)
        self.assertEqual(inline_comments[0][INLINE_COMMENT_FIELD_PATH], "src/example.py")
        self.assertEqual(inline_comments[0][INLINE_COMMENT_FIELD_LINE], 7)
        self.assertEqual(
            inline_comments[0][INLINE_COMMENT_FIELD_SIDE], INLINE_COMMENT_SIDE_RIGHT
        )
        self.assertIn("Bugteam", str(inline_comments[0][INLINE_COMMENT_FIELD_BODY]))

    def test_review_event_for_state_maps_clean_and_dirty(self) -> None:
        self.assertEqual(
            review_event_for_state(STATE_CLEAN), GITHUB_REVIEW_EVENT_APPROVE
        )
        self.assertEqual(
            review_event_for_state(STATE_DIRTY), GITHUB_REVIEW_EVENT_REQUEST_CHANGES
        )

    def test_review_event_for_state_rejects_unknown_state(self) -> None:
        with self.assertRaises(UserInputError):
            review_event_for_state("SIDEWAYS")

    def test_build_review_request_payload_assembles_fields(self) -> None:
        inline_comments = build_inline_comments_payload(
            SKILL_BUGTEAM, [self._sample_finding(SEVERITY_TAG_P0, 3)]
        )
        request_payload = build_review_request_payload(
            state_argument=STATE_DIRTY,
            commit_sha="deadbeefcafe",
            review_body_text="review body text",
            all_inline_comments=inline_comments,
        )
        self.assertEqual(request_payload[REVIEW_REQUEST_FIELD_COMMIT_ID], "deadbeefcafe")
        self.assertEqual(request_payload[REVIEW_REQUEST_FIELD_BODY], "review body text")
        self.assertEqual(
            request_payload[REVIEW_REQUEST_FIELD_EVENT],
            GITHUB_REVIEW_EVENT_REQUEST_CHANGES,
        )
        self.assertEqual(
            request_payload[REVIEW_REQUEST_FIELD_COMMENTS], inline_comments
        )

    def test_resolve_github_token_prefers_environment_variable(self) -> None:
        sentinel_token = "sentinel-token-from-environment"
        previous_token = os.environ.get(GH_TOKEN_ENV_VAR_NAME)
        os.environ[GH_TOKEN_ENV_VAR_NAME] = sentinel_token
        try:
            self.assertEqual(resolve_github_token(), sentinel_token)
        finally:
            if previous_token is None:
                os.environ.pop(GH_TOKEN_ENV_VAR_NAME, None)
            else:
                os.environ[GH_TOKEN_ENV_VAR_NAME] = previous_token

    def test_execute_review_post_attempt_returns_status_and_body(self) -> None:
        stub_server, stub_thread = spawn_stub_reviews_server(failure_count=0)
        try:
            endpoint_url = stub_reviews_server_base_url(stub_server) + "/reviews"
            status_code, reply_body = execute_review_post_attempt(
                endpoint_url, "unused-token", {"event": "APPROVE"}
            )
        finally:
            shutdown_stub_reviews_server(stub_server, stub_thread)
        self.assertEqual(status_code, STUB_HTTP_STATUS_OK)
        self.assertIn("html_url", reply_body)

    def test_post_review_with_retries_returns_posted_review_on_success(self) -> None:
        stub_server, stub_thread = spawn_stub_reviews_server(failure_count=0)
        try:
            endpoint_url = stub_reviews_server_base_url(stub_server) + "/reviews"
            posted_review = post_review_with_retries(
                endpoint_url, "unused-token", {"event": "APPROVE"}
            )
        finally:
            shutdown_stub_reviews_server(stub_server, stub_thread)
        self.assertEqual(posted_review.status_code, STUB_HTTP_STATUS_OK)
        self.assertTrue(posted_review.html_url.startswith("https://github.com/"))
        self.assertEqual(stub_server.request_count, 1)

    def test_extract_html_url_field_reads_html_url(self) -> None:
        review_reply = json.dumps(
            {"html_url": "https://github.com/o/r/pull/1#pullrequestreview-9"}
        )
        self.assertEqual(
            extract_html_url_field(review_reply),
            "https://github.com/o/r/pull/1#pullrequestreview-9",
        )

    def test_extract_html_url_field_rejects_missing_field(self) -> None:
        with self.assertRaises(RuntimeError):
            extract_html_url_field(json.dumps({"unrelated": "x"}))

    def test_post_audit_review_clean_state_posts_and_returns_html_url(self) -> None:
        stub_server, stub_thread = spawn_stub_reviews_server(failure_count=0)
        findings_path = self._write_findings_file([])
        previous_base_url = post_audit_thread.GITHUB_API_BASE_URL
        previous_token = os.environ.get(GH_TOKEN_ENV_VAR_NAME)
        os.environ[GH_TOKEN_ENV_VAR_NAME] = "unused-token-for-clean-post"
        post_audit_thread.GITHUB_API_BASE_URL = stub_reviews_server_base_url(stub_server)
        try:
            parsed_arguments = parse_command_line_arguments(
                [
                    CLI_FLAG_SKILL, SKILL_BUGTEAM,
                    CLI_FLAG_OWNER, LIVE_TEST_OWNER,
                    CLI_FLAG_REPO, LIVE_TEST_REPO,
                    CLI_FLAG_PR_NUMBER, "1",
                    CLI_FLAG_COMMIT, "abcdef1234567890",
                    CLI_FLAG_STATE, STATE_CLEAN,
                    CLI_FLAG_FINDINGS_JSON, str(findings_path),
                ]
            )
            posted_review = post_audit_review(parsed_arguments)
        finally:
            post_audit_thread.GITHUB_API_BASE_URL = previous_base_url
            if previous_token is None:
                os.environ.pop(GH_TOKEN_ENV_VAR_NAME, None)
            else:
                os.environ[GH_TOKEN_ENV_VAR_NAME] = previous_token
            shutdown_stub_reviews_server(stub_server, stub_thread)
        self.assertTrue(posted_review.html_url.startswith("https://github.com/"))
        self.assertGreaterEqual(stub_server.request_count, 1)


if __name__ == "__main__":
    unittest.main()
