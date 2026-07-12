"""String constants for the AI rules fan-out dispatcher: summary-table labels and row templates, GitHub Actions annotation templates, the per-repo conclusion-report status labels, the private-target redaction format, the listener-runs query template, and environment-variable names."""

SUMMARY_TABLE_HEADER_ROW: str = "| Metric | Count |"
SUMMARY_TABLE_SEPARATOR_ROW: str = "|--------|-------|"
SUMMARY_TABLE_ROW_JOIN: str = "\n"
METRIC_TARGETS_CONSIDERED: str = "Targets considered"
METRIC_DISPATCH_SUCCEEDED: str = "Dispatch succeeded"
METRIC_DISPATCH_FAILED: str = "Dispatch failed"
METRIC_DISPATCH_OPTED_OUT: str = "Dispatch opted out"
METRIC_LISTENER_SUCCESS: str = "Listener success"
METRIC_LISTENER_FAILURE: str = "Listener failure"
METRIC_LISTENER_PENDING: str = "Listener pending"
METRIC_LISTENER_POLL_ERROR: str = "Listener poll error"
METRIC_LISTENER_OTHER: str = "Listener other"
ENV_SOURCE_SHA: str = "SOURCE_SHA"
ENV_SOURCE_COMMIT: str = "SOURCE_COMMIT"
ENV_GITHUB_STEP_SUMMARY: str = "GITHUB_STEP_SUMMARY"
METRIC_LISTENER_MISSING: str = "Listener missing"
SUMMARY_HEADING: str = "## Fan-out AI Rules — Dispatch Summary\n\n"
STALE_SECTION_HEADING: str = "## Stale listeners"
NO_TARGET_REPOS_SUMMARY: str = "No target repos found."
ACTIONS_NO_TOKEN_FOR_OWNER: str = (
    "::warning::No installation token for an owner; skipping repo enumeration"
)
ACTIONS_EXCLUDED_REPO_COUNT: str = (
    "::notice::Excluded %s repositories from targets"
)
ACTIONS_MALFORMED_REPO_ENTRY: str = "::warning::Skipped %s malformed repo entries"
ACTIONS_NO_TOKEN_FOR_TARGET: str = (
    "::warning::No installation token available for a target owner; skipping a repo"
)
ACTIONS_DISPATCH_FAILED: str = "::warning::Failed to dispatch to a target repo"
ACTIONS_RATE_LIMITED: str = (
    "::warning::Rate limited on dispatch, retrying after %ss"
)
ACTIONS_DISPATCH_HTTP_FAILED: str = (
    "::warning::Dispatch to a target repo failed with HTTP %s"
)
ACTIONS_ENUMERATION_NETWORK_ERROR: str = (
    "::error::Network error during enumeration; aborting run"
)
ACTIONS_ENUMERATION_HTTP_FAILED: str = (
    "::error::Enumeration failed with HTTP %s"
)
ACTIONS_ENUMERATION_RETURNED_COUNT: str = (
    "::notice::Enumeration returned %s repositories"
)
ACTIONS_DRIFT_COUNT: str = (
    "::error::Drift detected or sync failed in %s target repo(s)"
)
ACTIONS_WAIT_FOR_LISTENERS: str = (
    "Dispatched to %s repos. Waiting %ss for listeners to start..."
)
STALE_SECTION_BODY: str = (
    "%s target repo(s) have no listener run in the past %s days."
)
SUMMARY_METRIC_ROW_TEMPLATE: str = "| %s | %s |"
ENV_DISPATCHED_AT: str = "DISPATCHED_AT"
REPO_FULL_NAME_SEPARATOR: str = "/"
REDACTED_REPO_HASH_PREFIX_LENGTH: int = 8
REDACTED_REPO_IDENTIFIER_TEMPLATE: str = "%s/[redacted:%s]"
REPO_CONCLUSION_LOG_TEMPLATE: str = "::notice::Target %s dispatch conclusion: %s"
LISTENER_RUNS_QUERY_TEMPLATE: str = (
    "/repos/%s/%s/actions/workflows/%s/runs?event=repository_dispatch&per_page=1"
)
REPORT_STATUS_SUCCEEDED: str = "succeeded"
REPORT_STATUS_FAILED: str = "failed"
REPORT_STATUS_LISTENER_MISSING: str = "listener-missing"
REPORT_STATUS_NO_MATCHING_RUN: str = "no-matching-run"
REPORT_STATUS_OPTED_OUT: str = "opted-out"
