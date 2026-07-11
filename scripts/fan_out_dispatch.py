#!/usr/bin/env python3
"""
Dispatcher script for the fan-out AI rules sync system.

Enumerates target repos for the configured owner scopes, checks opt-out sentinels,
dispatches repository_dispatch events, then polls for listener run conclusions.
"""

import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional


def _ensure_repo_root_on_sys_path() -> None:
    repo_root = str(Path(__file__).resolve().parents[1])
    if repo_root in sys.path:
        sys.path.remove(repo_root)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


_ensure_repo_root_on_sys_path()

from config.constants import (
    ACTIONS_DISPATCH_FAILED,
    ACTIONS_DISPATCH_HTTP_FAILED,
    ACTIONS_DRIFT_COUNT,
    ACTIONS_ENUMERATION_HTTP_FAILED,
    ACTIONS_ENUMERATION_NETWORK_ERROR,
    ACTIONS_ENUMERATION_RETURNED_COUNT,
    ACTIONS_EXCLUDED_REPO_COUNT,
    ACTIONS_MALFORMED_REPO_ENTRY,
    ACTIONS_NO_TOKEN_FOR_OWNER,
    ACTIONS_NO_TOKEN_FOR_TARGET,
    ACTIONS_RATE_LIMITED,
    ACTIONS_WAIT_FOR_LISTENERS,
    ENV_GITHUB_STEP_SUMMARY,
    ENV_SOURCE_COMMIT,
    ENV_SOURCE_SHA,
    METRIC_DISPATCH_FAILED,
    METRIC_DISPATCH_OPTED_OUT,
    METRIC_DISPATCH_SUCCEEDED,
    METRIC_LISTENER_FAILURE,
    METRIC_LISTENER_MISSING,
    METRIC_LISTENER_OTHER,
    METRIC_LISTENER_PENDING,
    METRIC_LISTENER_POLL_ERROR,
    METRIC_LISTENER_SUCCESS,
    METRIC_TARGETS_CONSIDERED,
    NO_TARGET_REPOS_SUMMARY,
    STALE_SECTION_BODY,
    STALE_SECTION_HEADING,
    SUMMARY_HEADING,
    SUMMARY_METRIC_ROW_TEMPLATE,
    SUMMARY_TABLE_HEADER_ROW,
    SUMMARY_TABLE_ROW_JOIN,
    SUMMARY_TABLE_SEPARATOR_ROW,
)
from config.local_identity import (
    fanout_owner_scopes,
    token_env_var_name,
)


SOURCE_REPO_FULL_NAME = "jl-cmd/claude-dev-env"
SOURCE_FILE_RELATIVE_PATH = "AGENTS.md"
RAW_GITHUB_CONTENT_BASE_URL = "https://raw.githubusercontent.com"
DEFAULT_SOURCE_BRANCH = "main"
DISPATCH_EVENT_TYPE = "sync-ai-rules"
LISTENER_WORKFLOW_FILENAME = "sync-ai-rules.yml"
OPT_OUT_SENTINEL_RELATIVE_PATH = ".github/sync-ai-rules.optout"
GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_API_VERSION_HEADER = "2022-11-28"
DISPATCH_RATE_LIMIT_SLEEP_SECONDS = 0.85
RECONCILIATION_WAIT_SECONDS = 60
STALE_LISTENER_THRESHOLD_DAYS = 14
REPOS_PER_PAGE = 100
RETRY_AFTER_DEFAULT_SECONDS = 60
GITHUB_API_REQUEST_TIMEOUT_SECONDS = 30
LISTENER_POLL_MAX_ATTEMPTS = 10
LISTENER_POLL_INTERVAL_SECONDS = 30
HTTP_STATUS_OK = 200
HTTP_STATUS_NO_CONTENT = 204
HTTP_STATUS_FORBIDDEN = 403
HTTP_STATUS_NOT_FOUND = 404
HTTP_STATUS_TOO_MANY_REQUESTS = 429
SECONDS_PER_DAY = 86400

DISPATCH_STATUS_SUCCEEDED = "succeeded"
NETWORK_ERROR_STATUS_CODE = 0
DISPATCH_STATUS_OPTED_OUT = "opted-out"
DISPATCH_STATUS_FAILED = "dispatch-failed"
LISTENER_STATUS_MISSING = "listener-missing"
LISTENER_STATUS_PENDING = "pending"
LISTENER_STATUS_POLL_ERROR = "poll-error"
LISTENER_CONCLUSION_SUCCESS = "success"
LISTENER_CONCLUSION_FAILURE = "failure"
UNKNOWN_COMMIT_PLACEHOLDER = "unknown"

dispatch_logger = logging.getLogger(__name__)
if not dispatch_logger.handlers:
    _stderr_handler = logging.StreamHandler(sys.stderr)
    _stderr_handler.setFormatter(logging.Formatter("%(message)s"))
    dispatch_logger.addHandler(_stderr_handler)
    dispatch_logger.setLevel(logging.INFO)
    dispatch_logger.propagate = False


def make_github_api_request(
    path: str,
    token: str,
    method: str = "GET",
    payload: Optional[dict[str, object]] = None,
) -> tuple[int, Optional[dict[str, object]], Optional[int]]:
    url = f"{GITHUB_API_BASE_URL}{path}"
    payload_bytes = json.dumps(payload).encode("utf-8") if payload else None
    api_request = urllib.request.Request(
        url,
        data=payload_bytes,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION_HEADER,
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(
            api_request, timeout=GITHUB_API_REQUEST_TIMEOUT_SECONDS
        ) as http_response:
            status_code = http_response.status
            if status_code == HTTP_STATUS_NO_CONTENT:
                return status_code, None, None
            return (
                status_code,
                json.loads(http_response.read().decode("utf-8")),
                None,
            )
    except urllib.error.HTTPError as http_error:
        retry_after_header = http_error.headers.get("Retry-After")
        retry_after_seconds: Optional[int] = None
        if retry_after_header is not None:
            try:
                retry_after_seconds = int(retry_after_header)
            except (TypeError, ValueError):
                try:
                    parsed_moment = parsedate_to_datetime(retry_after_header)
                except (TypeError, ValueError):
                    parsed_moment = None
                if parsed_moment is not None:
                    if parsed_moment.tzinfo is None:
                        parsed_moment = parsed_moment.replace(tzinfo=timezone.utc)
                    retry_after_seconds = max(
                        0,
                        int(
                            (
                                parsed_moment - datetime.now(timezone.utc)
                            ).total_seconds()
                        ),
                    )
        return http_error.code, None, retry_after_seconds
    except (urllib.error.URLError, TimeoutError):
        return 0, None, None


def enumerate_installation_repos(token: str) -> list[dict[str, object]]:
    all_repos: list[dict[str, object]] = []
    page_number = 1
    while True:
        path = (
            f"/installation/repositories?per_page={REPOS_PER_PAGE}&page={page_number}"
        )
        status_code, response_body, _ = make_github_api_request(path, token)
        if status_code == NETWORK_ERROR_STATUS_CODE:
            dispatch_logger.error(ACTIONS_ENUMERATION_NETWORK_ERROR)
            break
        if status_code != HTTP_STATUS_OK or response_body is None:
            dispatch_logger.error(ACTIONS_ENUMERATION_HTTP_FAILED, status_code)
            break
        page_repos = response_body.get("repositories", [])
        all_repos.extend(page_repos)
        if len(page_repos) < REPOS_PER_PAGE:
            break
        page_number += 1
    dispatch_logger.info(ACTIONS_ENUMERATION_RETURNED_COUNT, len(all_repos))
    return all_repos


def is_target_repo(repo: dict[str, object]) -> bool:
    owner_login = repo.get("owner", {}).get("login", "")
    is_owned_by_target_account = owner_login in fanout_owner_scopes()
    is_archived = repo.get("archived", True)
    is_upstream_fork = repo.get("fork", False) and not is_owned_by_target_account
    return (
        is_owned_by_target_account
        and not is_archived
        and not is_upstream_fork
    )


def check_opt_out_sentinel(owner: str, repo_name: str, token: str) -> bool:
    path = f"/repos/{owner}/{repo_name}/contents/{OPT_OUT_SENTINEL_RELATIVE_PATH}"
    status_code, _, _ = make_github_api_request(path, token)
    return status_code == HTTP_STATUS_OK


def parse_iso_timestamp(timestamp_text: str) -> Optional[datetime]:
    if not timestamp_text:
        return None
    try:
        return datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
    except ValueError:
        return None


def dispatch_sync_event_with_retry(
    owner: str,
    repo_name: str,
    token: str,
    dispatch_payload: dict[str, object],
) -> bool:
    path = f"/repos/{owner}/{repo_name}/dispatches"
    status_code, _, retry_after_seconds = make_github_api_request(
        path, token, method="POST", payload=dispatch_payload
    )

    if status_code == HTTP_STATUS_TOO_MANY_REQUESTS:
        sleep_seconds = (
            retry_after_seconds
            if retry_after_seconds is not None
            else RETRY_AFTER_DEFAULT_SECONDS
        )
        dispatch_logger.warning(ACTIONS_RATE_LIMITED, sleep_seconds)
        time.sleep(sleep_seconds)
        status_code, _, _ = make_github_api_request(
            path, token, method="POST", payload=dispatch_payload
        )

    if status_code == HTTP_STATUS_NO_CONTENT:
        return True

    dispatch_logger.warning(ACTIONS_DISPATCH_HTTP_FAILED, status_code)
    return False


def poll_listener_run_conclusion(
    owner: str,
    repo_name: str,
    token: str,
    dispatched_at: str,
) -> str:
    path = (
        f"/repos/{owner}/{repo_name}/actions/workflows"
        f"/{LISTENER_WORKFLOW_FILENAME}/runs"
        f"?event=repository_dispatch&per_page=1"
    )
    dispatched_at_parsed = parse_iso_timestamp(dispatched_at)

    all_attempts_were_network_errors = True
    for attempt_index in range(LISTENER_POLL_MAX_ATTEMPTS):
        status_code, response_body, _ = make_github_api_request(path, token)
        if status_code == HTTP_STATUS_NOT_FOUND:
            return LISTENER_STATUS_MISSING
        if status_code == NETWORK_ERROR_STATUS_CODE:
            time.sleep(LISTENER_POLL_INTERVAL_SECONDS)
            continue
        all_attempts_were_network_errors = False
        if status_code != HTTP_STATUS_OK or response_body is None:
            return LISTENER_STATUS_POLL_ERROR

        all_workflow_runs = response_body.get("workflow_runs", [])
        if not all_workflow_runs:
            if attempt_index == LISTENER_POLL_MAX_ATTEMPTS - 1:
                return LISTENER_STATUS_MISSING
            time.sleep(LISTENER_POLL_INTERVAL_SECONDS)
            continue

        most_recent_run = all_workflow_runs[0]
        run_created_at_text = most_recent_run.get("created_at", "")
        run_created_at_parsed = parse_iso_timestamp(run_created_at_text)

        run_is_for_current_dispatch = (
            dispatched_at_parsed is not None
            and run_created_at_parsed is not None
            and run_created_at_parsed >= dispatched_at_parsed
        )
        if not run_is_for_current_dispatch:
            if attempt_index == LISTENER_POLL_MAX_ATTEMPTS - 1:
                return LISTENER_STATUS_PENDING
            time.sleep(LISTENER_POLL_INTERVAL_SECONDS)
            continue

        conclusion = most_recent_run.get("conclusion")
        if isinstance(conclusion, str):
            return conclusion

        if attempt_index == LISTENER_POLL_MAX_ATTEMPTS - 1:
            return LISTENER_STATUS_PENDING
        time.sleep(LISTENER_POLL_INTERVAL_SECONDS)

    if all_attempts_were_network_errors:
        return LISTENER_STATUS_POLL_ERROR
    return LISTENER_STATUS_PENDING


def is_listener_stale(
    owner: str,
    repo_name: str,
    token: str,
    stale_threshold_seconds: int,
) -> bool:
    path = (
        f"/repos/{owner}/{repo_name}/actions/workflows"
        f"/{LISTENER_WORKFLOW_FILENAME}/runs"
        f"?per_page=1"
    )
    status_code, response_body, _ = make_github_api_request(path, token)
    if status_code == HTTP_STATUS_NOT_FOUND or response_body is None:
        return True

    all_workflow_runs = response_body.get("workflow_runs", [])
    if not all_workflow_runs:
        return True

    most_recent_run = all_workflow_runs[0]
    run_created_at = most_recent_run.get("created_at", "")
    if not run_created_at:
        return True

    now_timestamp = datetime.now(timezone.utc).timestamp()
    run_timestamp = datetime.fromisoformat(
        run_created_at.replace("Z", "+00:00")
    ).timestamp()
    elapsed_seconds = now_timestamp - run_timestamp
    return elapsed_seconds > stale_threshold_seconds


def write_step_summary(text: str) -> None:
    summary_file_path = os.environ.get(ENV_GITHUB_STEP_SUMMARY)
    if summary_file_path:
        with open(summary_file_path, "a", encoding="utf-8") as summary_file:
            summary_file.write(text + "\n")
    else:
        print(text)


def _count_repos_with_status(
    all_status_by_repo: dict[str, str],
    expected_status: str,
) -> int:
    return sum(
        1
        for each_status in all_status_by_repo.values()
        if each_status == expected_status
    )


def _build_dispatch_metric_rows(
    all_dispatch_status_by_repo: dict[str, str],
) -> list[tuple[str, int]]:
    return [
        (METRIC_TARGETS_CONSIDERED, len(all_dispatch_status_by_repo)),
        (
            METRIC_DISPATCH_SUCCEEDED,
            _count_repos_with_status(
                all_dispatch_status_by_repo, DISPATCH_STATUS_SUCCEEDED
            ),
        ),
        (
            METRIC_DISPATCH_FAILED,
            _count_repos_with_status(
                all_dispatch_status_by_repo, DISPATCH_STATUS_FAILED
            ),
        ),
        (
            METRIC_DISPATCH_OPTED_OUT,
            _count_repos_with_status(
                all_dispatch_status_by_repo, DISPATCH_STATUS_OPTED_OUT
            ),
        ),
    ]


def _build_enumerated_listener_rows(
    all_conclusion_by_repo: dict[str, str],
) -> list[tuple[str, int]]:
    return [
        (
            METRIC_LISTENER_SUCCESS,
            _count_repos_with_status(
                all_conclusion_by_repo, LISTENER_CONCLUSION_SUCCESS
            ),
        ),
        (
            METRIC_LISTENER_FAILURE,
            _count_repos_with_status(
                all_conclusion_by_repo, LISTENER_CONCLUSION_FAILURE
            ),
        ),
        (
            METRIC_LISTENER_PENDING,
            _count_repos_with_status(
                all_conclusion_by_repo, LISTENER_STATUS_PENDING
            ),
        ),
        (
            METRIC_LISTENER_POLL_ERROR,
            _count_repos_with_status(
                all_conclusion_by_repo, LISTENER_STATUS_POLL_ERROR
            ),
        ),
        (
            METRIC_LISTENER_MISSING,
            _count_repos_with_status(
                all_conclusion_by_repo, LISTENER_STATUS_MISSING
            ),
        ),
    ]


def _build_summary_metric_rows(
    all_dispatch_status_by_repo: dict[str, str],
    all_conclusion_by_repo: dict[str, str],
) -> list[tuple[str, int]]:
    dispatch_metric_rows = _build_dispatch_metric_rows(all_dispatch_status_by_repo)
    enumerated_listener_rows = _build_enumerated_listener_rows(all_conclusion_by_repo)
    enumerated_listener_total = sum(
        each_count for _, each_count in enumerated_listener_rows
    )
    other_listener_count = len(all_conclusion_by_repo) - enumerated_listener_total
    listener_other_row = [(METRIC_LISTENER_OTHER, other_listener_count)]
    return dispatch_metric_rows + enumerated_listener_rows + listener_other_row


def build_summary_table(
    all_dispatch_status_by_repo: dict[str, str],
    all_conclusion_by_repo: dict[str, str],
) -> str:
    all_metric_rows = _build_summary_metric_rows(
        all_dispatch_status_by_repo, all_conclusion_by_repo
    )
    all_table_rows = [SUMMARY_TABLE_HEADER_ROW, SUMMARY_TABLE_SEPARATOR_ROW]
    for each_metric, each_count in all_metric_rows:
        all_table_rows.append(
            SUMMARY_METRIC_ROW_TEMPLATE % (each_metric, each_count)
        )
    return SUMMARY_TABLE_ROW_JOIN.join(all_table_rows)


def build_stale_section(all_stale_repos: list[str]) -> str:
    if not all_stale_repos:
        return ""
    stale_repo_count = len(all_stale_repos)
    stale_section_body = STALE_SECTION_BODY % (
        stale_repo_count,
        STALE_LISTENER_THRESHOLD_DAYS,
    )
    return (
        f"\n\n{STALE_SECTION_HEADING}\n\n"
        f"{stale_section_body}"
    )


def resolve_source_commit_from_environment() -> str:
    return os.environ.get(ENV_SOURCE_COMMIT) or UNKNOWN_COMMIT_PLACEHOLDER


def _build_dispatch_payload(
    source_commit: str,
    source_sha: str,
    dispatched_at: str,
) -> dict[str, object]:
    raw_url = (
        f"{RAW_GITHUB_CONTENT_BASE_URL}/{SOURCE_REPO_FULL_NAME}"
        f"/{DEFAULT_SOURCE_BRANCH}/{SOURCE_FILE_RELATIVE_PATH}"
    )
    return {
        "event_type": DISPATCH_EVENT_TYPE,
        "client_payload": {
            "source_repo": SOURCE_REPO_FULL_NAME,
            "source_path": SOURCE_FILE_RELATIVE_PATH,
            "source_sha": source_sha,
            "source_commit": source_commit,
            "raw_url": raw_url,
            "dispatched_at": dispatched_at,
        },
    }


def _collect_candidate_repos(
    token_by_owner: dict[str, str],
) -> list[dict[str, object]]:
    all_candidate_repos: list[dict[str, object]] = []
    for each_owner, each_token in token_by_owner.items():
        if not each_token:
            dispatch_logger.warning(ACTIONS_NO_TOKEN_FOR_OWNER)
            continue
        owner_repos = enumerate_installation_repos(each_token)
        all_candidate_repos.extend(owner_repos)
    return all_candidate_repos


def _dispatch_to_targets(
    all_target_repos: list[dict[str, object]],
    token_by_owner: dict[str, str],
    all_dispatch_payload: dict[str, object],
) -> tuple[dict[str, str], list[tuple[str, str, str]]]:
    dispatch_status_by_repo: dict[str, str] = {}
    all_dispatched_repos: list[tuple[str, str, str]] = []
    malformed_repo_count = 0
    for each_repo in all_target_repos:
        owner = (each_repo.get("owner") or {}).get("login")
        repo_name = each_repo.get("name")
        full_repo_name = each_repo.get("full_name")
        if not owner or not repo_name or not full_repo_name:
            malformed_repo_count += 1
            continue
        token = token_by_owner.get(owner)
        if token is None:
            dispatch_logger.warning(ACTIONS_NO_TOKEN_FOR_TARGET)
            continue
        if check_opt_out_sentinel(owner, repo_name, token):
            dispatch_status_by_repo[full_repo_name] = DISPATCH_STATUS_OPTED_OUT
            continue
        dispatch_succeeded = dispatch_sync_event_with_retry(
            owner, repo_name, token, all_dispatch_payload
        )
        if dispatch_succeeded:
            dispatch_status_by_repo[full_repo_name] = DISPATCH_STATUS_SUCCEEDED
            all_dispatched_repos.append((owner, repo_name, full_repo_name))
        else:
            dispatch_status_by_repo[full_repo_name] = DISPATCH_STATUS_FAILED
            dispatch_logger.warning(ACTIONS_DISPATCH_FAILED)
        time.sleep(DISPATCH_RATE_LIMIT_SLEEP_SECONDS)
    if malformed_repo_count > 0:
        dispatch_logger.warning(ACTIONS_MALFORMED_REPO_ENTRY, malformed_repo_count)
    return dispatch_status_by_repo, all_dispatched_repos


def _poll_dispatched_listeners(
    all_dispatched_repos: list[tuple[str, str, str]],
    token_by_owner: dict[str, str],
    dispatched_at: str,
) -> tuple[dict[str, str], list[str], int]:
    conclusion_by_repo: dict[str, str] = {}
    all_stale_repos: list[str] = []
    stale_threshold_seconds = STALE_LISTENER_THRESHOLD_DAYS * SECONDS_PER_DAY
    failed_listener_total = 0
    for each_owner, each_repo_name, each_full_repo_name in all_dispatched_repos:
        token = token_by_owner.get(each_owner, "")
        conclusion = poll_listener_run_conclusion(
            each_owner, each_repo_name, token, dispatched_at
        )
        conclusion_by_repo[each_full_repo_name] = conclusion
        if conclusion == LISTENER_CONCLUSION_FAILURE:
            failed_listener_total += 1
        if is_listener_stale(
            each_owner, each_repo_name, token, stale_threshold_seconds
        ):
            all_stale_repos.append(each_full_repo_name)
    return conclusion_by_repo, all_stale_repos, failed_listener_total


def main() -> int:
    source_commit = resolve_source_commit_from_environment()
    source_sha = os.environ.get(ENV_SOURCE_SHA, "")
    dispatched_at = datetime.now(timezone.utc).isoformat()
    all_dispatch_payload = _build_dispatch_payload(
        source_commit, source_sha, dispatched_at
    )
    token_by_owner = {
        each_owner_scope: os.environ.get(token_env_var_name(each_owner_scope), "")
        for each_owner_scope in fanout_owner_scopes()
    }
    all_candidate_repos = _collect_candidate_repos(token_by_owner)
    all_target_repos = [
        each_repo for each_repo in all_candidate_repos if is_target_repo(each_repo)
    ]
    excluded_repo_count = len(all_candidate_repos) - len(all_target_repos)
    if excluded_repo_count > 0:
        dispatch_logger.info(ACTIONS_EXCLUDED_REPO_COUNT, excluded_repo_count)
    dispatch_status_by_repo, all_dispatched_repos = _dispatch_to_targets(
        all_target_repos, token_by_owner, all_dispatch_payload
    )
    if not dispatch_status_by_repo:
        write_step_summary(NO_TARGET_REPOS_SUMMARY)
        return 0
    if not all_dispatched_repos:
        summary = SUMMARY_HEADING + build_summary_table(dispatch_status_by_repo, {})
        write_step_summary(summary)
        dispatch_logger.info(
            "%s", compute_exit_summary_line(dispatch_status_by_repo, {})
        )
        return compute_exit_code(dispatch_status_by_repo, {})
    dispatch_logger.info(
        ACTIONS_WAIT_FOR_LISTENERS,
        len(all_dispatched_repos),
        RECONCILIATION_WAIT_SECONDS,
    )
    time.sleep(RECONCILIATION_WAIT_SECONDS)
    conclusion_by_repo, all_stale_repos, failed_listener_total = (
        _poll_dispatched_listeners(
            all_dispatched_repos, token_by_owner, dispatched_at
        )
    )
    if failed_listener_total > 0:
        dispatch_logger.error(ACTIONS_DRIFT_COUNT, failed_listener_total)
    summary = (
        SUMMARY_HEADING
        + build_summary_table(dispatch_status_by_repo, conclusion_by_repo)
        + build_stale_section(all_stale_repos)
    )
    write_step_summary(summary)
    dispatch_logger.info(
        "%s",
        compute_exit_summary_line(dispatch_status_by_repo, conclusion_by_repo),
    )
    return compute_exit_code(dispatch_status_by_repo, conclusion_by_repo)


def compute_exit_summary_line(
    dispatch_status_by_repo: dict[str, str],
    conclusion_by_repo: dict[str, str],
) -> str:
    dispatch_success_count = sum(
        1 for status in dispatch_status_by_repo.values() if status == DISPATCH_STATUS_SUCCEEDED
    )
    dispatch_failed_count = sum(
        1 for status in dispatch_status_by_repo.values() if status == DISPATCH_STATUS_FAILED
    )
    dispatch_opted_out_count = sum(
        1 for status in dispatch_status_by_repo.values() if status == DISPATCH_STATUS_OPTED_OUT
    )
    conclusion_success_count = sum(
        1 for each_conclusion in conclusion_by_repo.values() if each_conclusion == LISTENER_CONCLUSION_SUCCESS
    )
    conclusion_failure_count = sum(
        1 for each_conclusion in conclusion_by_repo.values() if each_conclusion == LISTENER_CONCLUSION_FAILURE
    )
    conclusion_pending_count = sum(
        1 for each_conclusion in conclusion_by_repo.values() if each_conclusion == LISTENER_STATUS_PENDING
    )
    conclusion_poll_error_count = sum(
        1 for each_conclusion in conclusion_by_repo.values() if each_conclusion == LISTENER_STATUS_POLL_ERROR
    )
    return (
        f"dispatch_success={dispatch_success_count} "
        f"dispatch_failed={dispatch_failed_count} "
        f"dispatch_opted_out={dispatch_opted_out_count} "
        f"conclusion_success={conclusion_success_count} "
        f"conclusion_failure={conclusion_failure_count} "
        f"conclusion_pending={conclusion_pending_count} "
        f"conclusion_poll_error={conclusion_poll_error_count}"
    )


def compute_exit_code(
    dispatch_status_by_repo: dict[str, str],
    conclusion_by_repo: dict[str, str],
) -> int:
    any_dispatch_failed = any(
        status == DISPATCH_STATUS_FAILED
        for status in dispatch_status_by_repo.values()
    )
    failing_conclusions = {
        LISTENER_CONCLUSION_FAILURE,
        LISTENER_STATUS_PENDING,
        LISTENER_STATUS_POLL_ERROR,
    }
    any_conclusion_failed = any(
        each_conclusion in failing_conclusions for each_conclusion in conclusion_by_repo.values()
    )
    if any_dispatch_failed or any_conclusion_failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
