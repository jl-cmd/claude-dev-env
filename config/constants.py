"""Named string constants for the AI rules fan-out dispatcher summaries."""

SUMMARY_TABLE_HEADER_ROW = "| Metric | Count |"
SUMMARY_TABLE_SEPARATOR_ROW = "|--------|-------|"
SUMMARY_TABLE_ROW_JOIN = "\n"
METRIC_TARGETS_CONSIDERED = "Targets considered"
METRIC_DISPATCH_SUCCEEDED = "Dispatch succeeded"
METRIC_DISPATCH_FAILED = "Dispatch failed"
METRIC_DISPATCH_OPTED_OUT = "Dispatch opted out"
METRIC_LISTENER_SUCCESS = "Listener success"
METRIC_LISTENER_FAILURE = "Listener failure"
METRIC_LISTENER_PENDING = "Listener pending"
METRIC_LISTENER_POLL_ERROR = "Listener poll_error"
ENV_JONECHO_TOKEN = "JONECHO_TOKEN"
ENV_JLCMD_TOKEN = "JLCMD_TOKEN"
ENV_SOURCE_SHA = "SOURCE_SHA"
ENV_SOURCE_COMMIT = "SOURCE_COMMIT"
ENV_GITHUB_STEP_SUMMARY = "GITHUB_STEP_SUMMARY"
METRIC_LISTENER_MISSING = "Listener missing"
SUMMARY_HEADING = "## Fan-out AI Rules — Dispatch Summary\n\n"
STALE_SECTION_HEADING = "## Stale listeners"
NO_TARGET_REPOS_SUMMARY = "No target repos found."
ACTIONS_NO_TOKEN_FOR_OWNER = (
    "::warning::No installation token for an owner; skipping repo enumeration"
)
ACTIONS_EXCLUDED_REPO_COUNT = (
    "::notice::Excluded %s repositories from targets"
)
ACTIONS_MALFORMED_REPO_ENTRY = "::debug::Skipping malformed repo entry"
ACTIONS_NO_TOKEN_FOR_TARGET = (
    "::warning::No installation token available for a target owner; skipping a repo"
)
ACTIONS_DISPATCH_FAILED = "::warning::Failed to dispatch to a target repo"
ACTIONS_RATE_LIMITED = (
    "::warning::Rate limited on dispatch, retrying after %ss"
)
ACTIONS_DISPATCH_HTTP_FAILED = (
    "::warning::Dispatch to a target repo failed with HTTP %s"
)
ACTIONS_DRIFT_COUNT = (
    "::error::Drift detected or sync failed in %s target repo(s)"
)
ACTIONS_WAIT_FOR_LISTENERS = (
    "Dispatched to %s repos. Waiting %ss for listeners to start..."
)
STALE_SECTION_BODY = (
    "%s target repo(s) have no listener run in the past %s days."
)
SUMMARY_METRIC_ROW_TEMPLATE = "| %s | %s |"
