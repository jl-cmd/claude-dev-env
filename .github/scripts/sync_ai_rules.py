#!/usr/bin/env python3
"""Syncs AI review rules from the canonical source repo into two destination files."""

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TypedDict


SYNC_HEADER_START_MARKER = "<!-- SYNC-HEADER-START -->"
SYNC_HEADER_END_MARKER = "<!-- SYNC-HEADER-END -->"
DESTINATION_PATHS: tuple[str, ...] = (
    ".github/copilot-instructions.md",
    ".cursor/BUGBOT.md",
)
OPT_OUT_SENTINEL_PATH = ".github/sync-ai-rules.optout"
SOURCE_REPO = "jl-cmd/claude-code-config"
SOURCE_FILE_PATH = ".github/copilot-instructions.md"
LISTENER_WORKFLOW_RELATIVE_PATH = ".github/workflows/sync-ai-rules.yml"
RAW_GITHUB_CONTENT_BASE_URL = "https://raw.githubusercontent.com"
DEFAULT_SOURCE_BRANCH = "main"
DEFAULT_RAW_URL = (
    f"{RAW_GITHUB_CONTENT_BASE_URL}/{SOURCE_REPO}"
    f"/{DEFAULT_SOURCE_BRANCH}/{SOURCE_FILE_PATH}"
)
BOT_AUTHOR_NAME = "github-actions[bot]"
BOT_AUTHOR_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"
SYNC_BODY_SHA256_TRAILER_KEY = "Sync-Body-SHA256"
SOURCE_REPO_TRAILER_KEY = "Source-Repo"
SOURCE_PATH_TRAILER_KEY = "Source-Path"
SYNC_SOURCE_COMMIT_TRAILER_KEY = "Sync-Source-Commit"
GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_API_VERSION_HEADER = "2022-11-28"
HEADER_SEPARATOR_LENGTH = 2
SHA_DISPLAY_LENGTH = 16
UNKNOWN_COMMIT_PLACEHOLDER = "unknown"
FETCH_CANONICAL_TIMEOUT_SECONDS = 30
FETCH_CANONICAL_MAX_ATTEMPTS = 3
FETCH_CANONICAL_BACKOFF_BASE_SECONDS = 2
FETCH_CANONICAL_BACKOFF_EXPONENT_BASE = 2
GITHUB_API_REQUEST_TIMEOUT_SECONDS = 30
CANONICAL_BODY_MINIMUM_LENGTH_BYTES = 100
COMMIT_PUSH_MAX_ATTEMPTS = 3
COMMIT_PUSH_RETRY_SLEEP_SECONDS = 5
DRIFT_ISSUE_LABEL = "ai-rules-drift"
HTTP_STATUS_OK = 200
HTTP_STATUS_CREATED = 201


class DriftError(TypedDict):
    destination_path: str
    message: str


def normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n")


def compute_sha256(content: str) -> str:
    normalized_content = normalize_line_endings(content)
    return hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()


def build_sync_header(source_commit: str, synced_at: str) -> str:
    return (
        f"{SYNC_HEADER_START_MARKER}\n"
        f"<!--\n"
        f"AUTO-GENERATED — DO NOT EDIT.\n"
        f"Source of truth: {SOURCE_REPO}/{SOURCE_FILE_PATH}\n"
        f"Synced by: {LISTENER_WORKFLOW_RELATIVE_PATH}\n"
        f"Source commit: {source_commit}\n"
        f"Synced at: {synced_at}\n"
        f"-->\n"
        f"{SYNC_HEADER_END_MARKER}\n"
    )


def build_destination_content(
    canonical_body: str, source_commit: str, synced_at: str
) -> str:
    return build_sync_header(source_commit, synced_at) + "\n" + canonical_body


def strip_sync_header(content: str) -> Optional[str]:
    """Return body with sync header removed, or None if header sentinels are absent."""
    normalized_content = normalize_line_endings(content)
    start_position = normalized_content.find(SYNC_HEADER_START_MARKER)
    end_position = normalized_content.find(SYNC_HEADER_END_MARKER)
    if (
        start_position == -1
        or end_position == -1
        or end_position < start_position
    ):
        return None
    after_end_marker = end_position + len(SYNC_HEADER_END_MARKER)
    remaining = normalized_content[after_end_marker:]
    if remaining.startswith("\n\n"):
        return remaining[HEADER_SEPARATOR_LENGTH:]
    if remaining.startswith("\n"):
        return remaining[1:]
    return remaining


def fetch_canonical_body(raw_url: str) -> str:
    last_exception: Optional[BaseException] = None
    for attempt_index in range(FETCH_CANONICAL_MAX_ATTEMPTS):
        try:
            with urllib.request.urlopen(
                raw_url, timeout=FETCH_CANONICAL_TIMEOUT_SECONDS
            ) as http_response:
                return http_response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as fetch_error:
            last_exception = fetch_error
            if attempt_index == FETCH_CANONICAL_MAX_ATTEMPTS - 1:
                break
            sleep_seconds = FETCH_CANONICAL_BACKOFF_BASE_SECONDS * (
                FETCH_CANONICAL_BACKOFF_EXPONENT_BASE ** attempt_index
            )
            time.sleep(sleep_seconds)
    assert last_exception is not None
    raise last_exception


def find_last_bot_commit_hash(destination_path: str) -> Optional[str]:
    """Return the hash of the most recent github-actions[bot] commit touching destination_path."""
    completed = subprocess.run(
        ["git", "log", "--format=%H %ce", "--", destination_path],
        capture_output=True,
        text=True,
        check=True,
    )
    for each_log_line in completed.stdout.splitlines():
        hash_and_email = each_log_line.split(" ", 1)
        if len(hash_and_email) == 2 and hash_and_email[1].strip() == BOT_AUTHOR_EMAIL:
            return hash_and_email[0]
    return None


def extract_body_sha_from_commit(commit_hash: str) -> Optional[str]:
    """Parse the Sync-Body-SHA256 trailer from a commit message."""
    completed = subprocess.run(
        ["git", "show", "--format=%B", "--no-patch", commit_hash],
        capture_output=True,
        text=True,
        check=True,
    )
    trailer_prefix = f"{SYNC_BODY_SHA256_TRAILER_KEY}: "
    for message_line in completed.stdout.splitlines():
        if message_line.startswith(trailer_prefix):
            return message_line[len(trailer_prefix) :]
    return None


def check_destination_policy(
    destination_path: str,
    should_force_initial_overwrite: bool,
) -> Optional[str]:
    """
    Apply drift detection and first-sync policy.

    Returns an error string when the destination must not be written, None when safe to proceed.
    """
    destination = Path(destination_path)
    last_bot_commit_hash = find_last_bot_commit_hash(destination_path)

    if last_bot_commit_hash is None:
        if destination.exists():
            existing_content = destination.read_text(encoding="utf-8")
            if existing_content.strip():
                if not should_force_initial_overwrite:
                    return (
                        f"Destination {destination_path} exists with non-trivial content "
                        f"and no prior bot commit. Re-run with `force_initial_overwrite=true` "
                        f"to proceed, or delete the file to let the sync create it."
                    )
        return None

    stored_body_sha256 = extract_body_sha_from_commit(last_bot_commit_hash)
    if stored_body_sha256 is None:
        return None

    if not destination.exists():
        return None

    existing_content = destination.read_text(encoding="utf-8")
    existing_body = strip_sync_header(existing_content)
    if existing_body is None:
        if existing_content.strip() and not should_force_initial_overwrite:
            return (
                f"Drift detected in {destination_path}: "
                f"sync header markers are absent. The file appears to have been manually "
                f"replaced. Re-run with `force_initial_overwrite=true` to overwrite."
            )
        if not existing_content.strip():
            print(
                f"::warning::Destination {destination_path} lost its sync header; "
                f"treating as first sync.",
                file=sys.stderr,
            )
        return None

    actual_body_sha256 = compute_sha256(existing_body)
    if actual_body_sha256 != stored_body_sha256:
        return (
            f"Drift detected in {destination_path}: "
            f"expected body SHA256={stored_body_sha256[:SHA_DISPLAY_LENGTH]}…, "
            f"actual={actual_body_sha256[:SHA_DISPLAY_LENGTH]}…"
        )
    return None


def write_destination_if_needed(
    destination_path: str,
    canonical_body: str,
    source_commit: str,
    synced_at: str,
) -> bool:
    """Write destination only when the body differs from canonical. Returns True when written."""
    destination = Path(destination_path)

    if destination.exists():
        existing_content = destination.read_text(encoding="utf-8")
        existing_body = strip_sync_header(existing_content)
        if existing_body == canonical_body:
            return False

    desired_content = build_destination_content(
        canonical_body, source_commit, synced_at
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(desired_content, encoding="utf-8")
    return True


def open_github_issue(
    github_token: str,
    repository: str,
    title: str,
    issue_body_text: str,
    labels: Optional[list[str]] = None,
) -> None:
    issue_payload_dict: dict[str, object] = {"title": title, "body": issue_body_text}
    if labels:
        issue_payload_dict["labels"] = labels
    issue_payload = json.dumps(issue_payload_dict).encode("utf-8")
    api_request = urllib.request.Request(
        f"{GITHUB_API_BASE_URL}/repos/{repository}/issues",
        data=issue_payload,
        headers={
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION_HEADER,
        },
        method="POST",
    )
    with urllib.request.urlopen(
        api_request, timeout=GITHUB_API_REQUEST_TIMEOUT_SECONDS
    ) as http_response:
        status_code = http_response.status
    if status_code != HTTP_STATUS_CREATED:
        print(
            f"::error::Issue creation returned status {status_code}",
            file=sys.stderr,
        )
        raise RuntimeError(f"Issue creation returned status {status_code}")


def find_existing_drift_issue(
    github_token: str,
    repository: str,
    label: str,
) -> Optional[int]:
    encoded_label = urllib.parse.quote(label, safe="")
    url = (
        f"{GITHUB_API_BASE_URL}/repos/{repository}/issues"
        f"?state=open&labels={encoded_label}&per_page=1"
    )
    api_request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION_HEADER,
        },
        method="GET",
    )
    with urllib.request.urlopen(
        api_request, timeout=GITHUB_API_REQUEST_TIMEOUT_SECONDS
    ) as http_response:
        all_open_issues = json.loads(http_response.read().decode("utf-8"))
    if not isinstance(all_open_issues, list) or not all_open_issues:
        return None
    first_issue = all_open_issues[0]
    issue_number = first_issue.get("number")
    if isinstance(issue_number, int):
        return issue_number
    return None


def add_issue_comment(
    github_token: str,
    repository: str,
    issue_number: int,
    comment_body: str,
) -> None:
    comment_payload = json.dumps({"body": comment_body}).encode("utf-8")
    api_request = urllib.request.Request(
        f"{GITHUB_API_BASE_URL}/repos/{repository}/issues/{issue_number}/comments",
        data=comment_payload,
        headers={
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION_HEADER,
        },
        method="POST",
    )
    with urllib.request.urlopen(
        api_request, timeout=GITHUB_API_REQUEST_TIMEOUT_SECONDS
    ) as http_response:
        response_body_text = http_response.read().decode("utf-8")
        comment_status_code = http_response.status
    if comment_status_code != HTTP_STATUS_CREATED:
        raise RuntimeError(
            f"Comment creation returned status {comment_status_code}: {response_body_text}"
        )


def write_step_summary(text: str) -> None:
    summary_file_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file_path:
        with open(summary_file_path, "a", encoding="utf-8") as summary_file:
            summary_file.write(text + "\n")
    else:
        print(text, file=sys.stderr)


def build_commit_message(source_commit: str, canonical_body_sha256: str) -> str:
    return (
        f"chore: sync AI review rules from claude-code-config\n\n"
        f"{SOURCE_REPO_TRAILER_KEY}: {SOURCE_REPO}\n"
        f"{SOURCE_PATH_TRAILER_KEY}: {SOURCE_FILE_PATH}\n"
        f"{SYNC_SOURCE_COMMIT_TRAILER_KEY}: {source_commit}\n"
        f"{SYNC_BODY_SHA256_TRAILER_KEY}: {canonical_body_sha256}"
    )


def commit_and_push_sync(
    all_written_paths: list[str],
    source_commit: str,
    canonical_body_sha256: str,
) -> None:
    subprocess.run(["git", "config", "user.name", BOT_AUTHOR_NAME], check=True)
    subprocess.run(["git", "config", "user.email", BOT_AUTHOR_EMAIL], check=True)
    subprocess.run(["git", "add", "-f"] + all_written_paths, check=True)
    subprocess.run(
        [
            "git",
            "commit",
            "-m",
            build_commit_message(source_commit, canonical_body_sha256),
        ],
        check=True,
    )

    current_branch_name = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    last_push_error: Optional[subprocess.CalledProcessError] = None
    for attempt_index in range(COMMIT_PUSH_MAX_ATTEMPTS):
        try:
            subprocess.run(["git", "fetch", "origin"], check=True)
            subprocess.run(
                ["git", "pull", "--rebase", "origin", current_branch_name],
                check=True,
            )
            subprocess.run(["git", "push"], check=True)
            return
        except subprocess.CalledProcessError as push_error:
            last_push_error = push_error
            subprocess.run(
                ["git", "rebase", "--abort"],
                check=False,
                capture_output=True,
            )
            if attempt_index == COMMIT_PUSH_MAX_ATTEMPTS - 1:
                break
            time.sleep(COMMIT_PUSH_RETRY_SLEEP_SECONDS)
    assert last_push_error is not None
    raise last_push_error


def report_drift_errors(
    all_errors: list[DriftError],
    github_token: str,
    github_repository: str,
) -> None:
    for each_error in all_errors:
        print(f"::error::{each_error['message']}", file=sys.stderr)

    affected_destination_paths: list[str] = [
        each_destination_path
        for each_destination_path in DESTINATION_PATHS
        if any(
            each_error["destination_path"] == each_destination_path
            for each_error in all_errors
        )
    ]

    issue_body_text = (
        "## AI Rules Sync: Drift Detected\n\n"
        + "\n".join(f"- {each_error['message']}" for each_error in all_errors)
        + "\n\n**Action required:** Resolve the drift manually, or delete the affected "
        "file(s) and re-run with `force_initial_overwrite=true`."
    )

    if github_token and github_repository and affected_destination_paths:
        try:
            existing_issue_number = find_existing_drift_issue(
                github_token, github_repository, DRIFT_ISSUE_LABEL
            )
        except Exception as lookup_error:
            print(
                f"::warning::Failed to look up existing drift issue: {lookup_error}",
                file=sys.stderr,
            )
            existing_issue_number = None

        try:
            if existing_issue_number is not None:
                add_issue_comment(
                    github_token,
                    github_repository,
                    existing_issue_number,
                    issue_body_text,
                )
            else:
                issue_title = (
                    "AI rules sync: drift detected in "
                    + ", ".join(affected_destination_paths)
                )
                open_github_issue(
                    github_token,
                    github_repository,
                    issue_title,
                    issue_body_text,
                    labels=[DRIFT_ISSUE_LABEL],
                )
        except Exception as issue_error:
            print(
                f"::warning::Failed to open GitHub Issue: {issue_error}",
                file=sys.stderr,
            )

    drift_summary = "## Sync failed: drift detected\n\n" + "\n".join(
        f"- {each_error['message']}" for each_error in all_errors
    )
    write_step_summary(drift_summary)


def main() -> int:
    github_token = os.environ.get("GITHUB_TOKEN", "")
    github_repository = os.environ.get("GITHUB_REPOSITORY", "")
    source_commit = os.environ.get("SOURCE_COMMIT") or UNKNOWN_COMMIT_PLACEHOLDER
    raw_url = os.environ.get("RAW_URL") or DEFAULT_RAW_URL
    should_force_initial_overwrite = (
        (os.environ.get("FORCE_INITIAL_OVERWRITE") or "false").lower() == "true"
    )

    if Path(OPT_OUT_SENTINEL_PATH).exists():
        write_step_summary("Opted out via sentinel file.")
        return 0

    try:
        canonical_body = fetch_canonical_body(raw_url)
    except Exception as fetch_error:
        print(
            f"::error::Failed to fetch canonical file: {fetch_error}", file=sys.stderr
        )
        return 1

    if not canonical_body.strip():
        print("::error::Canonical file is empty.", file=sys.stderr)
        return 1

    if len(canonical_body.encode("utf-8")) < CANONICAL_BODY_MINIMUM_LENGTH_BYTES:
        print(
            f"::error::Canonical body shorter than "
            f"{CANONICAL_BODY_MINIMUM_LENGTH_BYTES} bytes; suspected truncation",
            file=sys.stderr,
        )
        return 1

    canonical_body_sha256 = compute_sha256(canonical_body)

    all_policy_errors: list[DriftError] = []
    for destination_path in DESTINATION_PATHS:
        policy_error_message = check_destination_policy(
            destination_path,
            should_force_initial_overwrite,
        )
        if policy_error_message:
            all_policy_errors.append(
                DriftError(
                    destination_path=destination_path,
                    message=policy_error_message,
                )
            )

    if all_policy_errors:
        report_drift_errors(all_policy_errors, github_token, github_repository)
        return 1

    synced_at = datetime.now(timezone.utc).isoformat()
    all_written_paths: list[str] = []

    for destination_path in DESTINATION_PATHS:
        was_written = write_destination_if_needed(
            destination_path,
            canonical_body,
            source_commit,
            synced_at,
        )
        if was_written:
            all_written_paths.append(destination_path)

    if not all_written_paths:
        write_step_summary("No changes needed.")
        return 0

    commit_and_push_sync(all_written_paths, source_commit, canonical_body_sha256)

    success_summary = (
        f"## Sync complete\n\n"
        f"- Source commit: `{source_commit}`\n"
        f"- Body SHA256: `{canonical_body_sha256}`\n"
        f"- Destinations updated: "
        + ", ".join(f"`{each_path}`" for each_path in all_written_paths)
    )
    write_step_summary(success_summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
