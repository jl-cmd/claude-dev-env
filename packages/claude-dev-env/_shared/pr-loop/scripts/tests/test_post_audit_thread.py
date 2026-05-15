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

sys.modules.pop("config", None)
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

from config.post_audit_thread_constants import (  # noqa: E402
    ALL_GH_AUTH_TOKEN_COMMAND_PARTS,
    ALL_RETRY_BACKOFF_SECONDS,
    GH_TOKEN_ENV_VAR_NAME,
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
)
from post_audit_thread import build_reviews_endpoint_url  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
