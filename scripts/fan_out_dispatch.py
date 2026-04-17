#!/usr/bin/env python3
"""
Dispatcher script for the fan-out AI rules sync system.

Enumerates target repos for JonEcho and jl-cmd, checks opt-out sentinels,
dispatches repository_dispatch events, then polls for listener run conclusions.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional


SOURCE_REPO_FULL_NAME = "jl-cmd/claude-code-config"
SOURCE_FILE_RELATIVE_PATH = ".github/copilot-instructions.md"
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
            print(
                "::error::Network error during enumeration; aborting run",
                file=sys.stderr,
            )
            break
        if status_code != HTTP_STATUS_OK or response_body is None:
            print(
                f"::error::Enumeration failed with HTTP {status_code}",
                file=sys.stderr,
            )
            break
        page_repos = response_body.get("repositories", [])
        all_repos.extend(page_repos)
        if len(page_repos) < REPOS_PER_PAGE:
            break
        page_number += 1
    print(
        f"::notice::Enumeration returned {len(all_repos)} repositories",
        file=sys.stderr,
    )
    return all_repos


def is_target_repo(repo: dict[str, object]) -> bool:
    owner_login = repo.get("owner", {}).get("login", "")
    is_owned_by_target_account = owner_login in ("JonEcho", "jl-cmd")
    is_archived = repo.get("archived", True)
    is_source_repo = repo.get("full_name") == SOURCE_REPO_FULL_NAME
    is_upstream_fork = repo.get("fork", False) and not is_owned_by_target_account

    is_included = (
        is_owned_by_target_account
        and not is_archived
        and not is_source_repo
        and not is_upstream_fork
    )

    if not is_included:
        full_name = repo.get("full_name", "")
        print(
            f"::notice::Excluding {full_name}: owner_match={is_owned_by_target_account} "
            f"archived={is_archived} source_repo={is_source_repo} "
            f"upstream_fork={is_upstream_fork}",
            file=sys.stderr,
        )
    return is_included


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
        print(
            f"::warning::Rate limited dispatching to {owner}/{repo_name}, retrying after "
            f"{sleep_seconds}s",
            file=sys.stderr,
        )
        time.sleep(sleep_seconds)
        status_code, _, _ = make_github_api_request(
            path, token, method="POST", payload=dispatch_payload
        )

    if status_code == HTTP_STATUS_NO_CONTENT:
        return True

    print(
        f"::warning::Dispatch to {owner}/{repo_name} failed with HTTP {status_code}",
        file=sys.stderr,
    )
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
    summary_file_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file_path:
        with open(summary_file_path, "a", encoding="utf-8") as summary_file:
            summary_file.write(text + "\n")
    else:
        print(text)


def build_summary_table(
    dispatch_status_by_repo: dict[str, str],
    conclusion_by_repo: dict[str, str],
    notes_by_repo: dict[str, str],
) -> str:
    table_rows = [
        "| Repo | Dispatch Status | Listener Conclusion | Notes |",
        "|------|----------------|---------------------|-------|",
    ]
    for full_repo_name in sorted(dispatch_status_by_repo):
        dispatch_status = dispatch_status_by_repo[full_repo_name]
        listener_conclusion = conclusion_by_repo.get(full_repo_name, "—")
        notes = notes_by_repo.get(full_repo_name, "")
        table_rows.append(
            f"| {full_repo_name} | {dispatch_status} | {listener_conclusion} | {notes} |"
        )
    return "\n".join(table_rows)


def build_stale_section(all_stale_repos: list[str]) -> str:
    if not all_stale_repos:
        return ""
    stale_entries = "\n".join(f"- {repo_name}" for repo_name in all_stale_repos)
    return f"\n\n## Stale listeners\n\nThese repos have no listener run in the past {STALE_LISTENER_THRESHOLD_DAYS} days:\n\n{stale_entries}"


def resolve_source_commit_from_environment() -> str:
    return os.environ.get("SOURCE_COMMIT") or UNKNOWN_COMMIT_PLACEHOLDER


def main() -> int:
    jonecho_token = os.environ.get("JONECHO_TOKEN", "")
    jlcmd_token = os.environ.get("JLCMD_TOKEN", "")
    source_commit = resolve_source_commit_from_environment()
    source_sha = os.environ.get("SOURCE_SHA", "")
    dispatched_at = datetime.now(timezone.utc).isoformat()

    raw_url = (
        f"{RAW_GITHUB_CONTENT_BASE_URL}/{SOURCE_REPO_FULL_NAME}"
        f"/{DEFAULT_SOURCE_BRANCH}/{SOURCE_FILE_RELATIVE_PATH}"
    )

    dispatch_payload = {
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

    token_by_owner = {"JonEcho": jonecho_token, "jl-cmd": jlcmd_token}

    all_candidate_repos: list[dict[str, object]] = []
    for owner, token in token_by_owner.items():
        if not token:
            print(
                f"::warning::No token for {owner}, skipping repo enumeration",
                file=sys.stderr,
            )
            continue
        owner_repos = enumerate_installation_repos(token)
        all_candidate_repos.extend(owner_repos)

    all_target_repos = [repo for repo in all_candidate_repos if is_target_repo(repo)]

    dispatch_status_by_repo: dict[str, str] = {}
    all_dispatched_repos: list[tuple[str, str, str]] = []

    for repo in all_target_repos:
        owner = (repo.get("owner") or {}).get("login")
        repo_name = repo.get("name")
        full_repo_name = repo.get("full_name")
        if not owner or not repo_name or not full_repo_name:
            print(f"::debug::Skipping malformed repo entry: {repo}", file=sys.stderr)
            continue
        token = token_by_owner.get(owner)
        if token is None:
            print(
                f"::warning::No installation token available for owner {owner}; skipping {full_repo_name}",
                file=sys.stderr,
            )
            continue

        if check_opt_out_sentinel(owner, repo_name, token):
            dispatch_status_by_repo[full_repo_name] = DISPATCH_STATUS_OPTED_OUT
            continue

        dispatch_succeeded = dispatch_sync_event_with_retry(
            owner, repo_name, token, dispatch_payload
        )
        if dispatch_succeeded:
            dispatch_status_by_repo[full_repo_name] = DISPATCH_STATUS_SUCCEEDED
            all_dispatched_repos.append((owner, repo_name, full_repo_name))
        else:
            dispatch_status_by_repo[full_repo_name] = DISPATCH_STATUS_FAILED
            print(f"::warning::Failed to dispatch to {full_repo_name}", file=sys.stderr)

        time.sleep(DISPATCH_RATE_LIMIT_SLEEP_SECONDS)

    if not dispatch_status_by_repo:
        write_step_summary("No target repos found.")
        return 0

    if not all_dispatched_repos:
        summary = (
            "## Fan-out AI Rules — Dispatch Summary\n\n"
            + build_summary_table(dispatch_status_by_repo, {}, {})
        )
        write_step_summary(summary)
        print(
            compute_exit_summary_line(dispatch_status_by_repo, {}),
            file=sys.stderr,
        )
        return compute_exit_code(dispatch_status_by_repo, {})

    print(
        f"Dispatched to {len(all_dispatched_repos)} repos. "
        f"Waiting {RECONCILIATION_WAIT_SECONDS}s for listeners to start...",
        file=sys.stderr,
    )
    time.sleep(RECONCILIATION_WAIT_SECONDS)

    conclusion_by_repo: dict[str, str] = {}
    notes_by_repo: dict[str, str] = {}
    all_stale_repos: list[str] = []
    stale_threshold_seconds = STALE_LISTENER_THRESHOLD_DAYS * SECONDS_PER_DAY

    for owner, repo_name, full_repo_name in all_dispatched_repos:
        token = token_by_owner.get(owner, "")
        conclusion = poll_listener_run_conclusion(
            owner, repo_name, token, dispatched_at
        )
        conclusion_by_repo[full_repo_name] = conclusion

        if conclusion == LISTENER_CONCLUSION_FAILURE:
            print(
                f"::error::Drift detected or sync failed in {full_repo_name}",
                file=sys.stderr,
            )
            notes_by_repo[full_repo_name] = "drift or sync error"
        elif conclusion == LISTENER_STATUS_MISSING:
            notes_by_repo[full_repo_name] = "listener not installed"
        elif conclusion == LISTENER_STATUS_POLL_ERROR:
            notes_by_repo[full_repo_name] = "poll error"
        elif conclusion == LISTENER_STATUS_PENDING:
            notes_by_repo[full_repo_name] = "pending after retries"

        if is_listener_stale(owner, repo_name, token, stale_threshold_seconds):
            all_stale_repos.append(full_repo_name)

    summary = (
        "## Fan-out AI Rules — Dispatch Summary\n\n"
        + build_summary_table(
            dispatch_status_by_repo, conclusion_by_repo, notes_by_repo
        )
        + build_stale_section(all_stale_repos)
    )
    write_step_summary(summary)

    exit_summary_line = compute_exit_summary_line(
        dispatch_status_by_repo, conclusion_by_repo
    )
    print(exit_summary_line, file=sys.stderr)

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
