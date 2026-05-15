"""Live smoke tests for post_audit_thread.py.

Runs against the real GitHub repo ``jl-cmd/claude-code-config``. Each
test opens a throwaway draft PR, runs the script, asserts the resulting
review and inline comments via ``gh api``, then closes the PR with
``--delete-branch``. Authentication uses ``gh auth token`` — empty token
fails loudly per spec.

Test files are exempt from the no-comment, magic-value, banned-identifier,
and constants-location enforcer rules.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
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
    GH_TOKEN_ENV_VAR_NAME,
    CLI_FLAG_COMMIT,
    CLI_FLAG_FINDINGS_JSON,
    CLI_FLAG_OWNER,
    CLI_FLAG_PR_NUMBER,
    CLI_FLAG_REPO,
    CLI_FLAG_SKILL,
    CLI_FLAG_STATE,
    INLINE_COMMENT_SIDE_RIGHT,
    JSON_FIELD_DESCRIPTION,
    JSON_FIELD_FIX_SUMMARY,
    JSON_FIELD_LINE,
    JSON_FIELD_PATH,
    JSON_FIELD_SEVERITY,
    JSON_FIELD_SIDE,
    SEVERITY_TAG_P0,
    SEVERITY_TAG_P1,
    SEVERITY_TAG_P2,
    SINGLE_REVIEW_API_PATH_TEMPLATE,
    SINGLE_REVIEW_COMMENTS_API_PATH_TEMPLATE,
    SKILL_BUGTEAM,
    STATE_CLEAN,
    STATE_DIRTY,
)

LIVE_TEST_OWNER = "jl-cmd"
LIVE_TEST_REPO = "claude-code-config"
LIVE_TEST_BRANCH_PREFIX = "pr-loop-test"
LIVE_TEST_PR_TITLE = "TEST: post_audit_thread smoke test (auto-closed)"
LIVE_TEST_PR_BODY = (
    "Throwaway PR for post_audit_thread.py live smoke tests. "
    "Auto-created by `test_post_audit_thread.py`; closed in `tearDown`."
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


def find_main_repository_root() -> Path:
    here = Path(__file__).resolve()
    for each_candidate in [here, *here.parents]:
        if (each_candidate / ".git").exists():
            return each_candidate
    raise RuntimeError(f"could not find .git anchor above {here}")


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
    main_repository_root: Path,
    worktree_directory: Path,
    branch_name: str,
) -> tuple[int, str]:
    subprocess.run(
        [
            "git",
            "-C",
            str(main_repository_root),
            "worktree",
            "add",
            "-b",
            branch_name,
            str(worktree_directory),
            "origin/main",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    fixture_path = worktree_directory / LIVE_TEST_FIXTURE_FILENAME
    fixture_path.write_text(LIVE_TEST_FIXTURE_CONTENT, encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(worktree_directory), "add", LIVE_TEST_FIXTURE_FILENAME],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(worktree_directory),
            "commit",
            "-m",
            "test: post_audit_thread.py live smoke fixture",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    head_sha_completion = subprocess.run(
        ["git", "-C", str(worktree_directory), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    head_sha = head_sha_completion.stdout.strip()
    subprocess.run(
        ["git", "-C", str(worktree_directory), "push", "-u", "origin", branch_name],
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
            cwd=str(worktree_directory),
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


def remove_local_worktree(
    main_repository_root: Path,
    worktree_directory: Path,
) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(main_repository_root),
            "worktree",
            "remove",
            "--force",
            str(worktree_directory),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    force_remove_directory(worktree_directory)


def delete_remote_branch(branch_name: str) -> None:
    subprocess.run(
        [
            "git",
            "push",
            "origin",
            "--delete",
            branch_name,
        ],
        capture_output=True,
        text=True,
        check=False,
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


class LivePostAuditThreadTests(unittest.TestCase):
    """Live smoke tests for post_audit_thread.py against jl-cmd/claude-code-config."""

    main_repository_root: Path
    audit_account_token: str

    @classmethod
    def setUpClass(cls) -> None:
        resolve_gh_auth_token()
        cls.audit_account_token = resolve_audit_account_token(
            LIVE_TEST_AUDIT_ACCOUNT_NAME
        )
        cls.main_repository_root = find_main_repository_root()

    def setUp(self) -> None:
        self.unique_suffix = uuid.uuid4().hex[:UUID_SUFFIX_LENGTH]
        self.branch_name = f"{LIVE_TEST_BRANCH_PREFIX}/{self.unique_suffix}"
        self.local_worktree_directory = Path(
            tempfile.mkdtemp(prefix=f"post-audit-thread-test-{self.unique_suffix}-")
        )
        self.pr_number: int = 0
        self.head_sha: str = ""
        try:
            self.pr_number, self.head_sha = create_throwaway_pr(
                self.main_repository_root,
                self.local_worktree_directory,
                self.branch_name,
            )
        except Exception:
            self._cleanup_remote_branch()
            self._cleanup_local_state()
            raise

    def tearDown(self) -> None:
        try:
            if self.pr_number > 0:
                close_throwaway_pr(self.pr_number)
        finally:
            self._cleanup_local_state()
            self._cleanup_remote_branch()

    def _cleanup_local_state(self) -> None:
        remove_local_worktree(self.main_repository_root, self.local_worktree_directory)

    def _cleanup_remote_branch(self) -> None:
        delete_remote_branch(self.branch_name)

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


if __name__ == "__main__":
    unittest.main()
