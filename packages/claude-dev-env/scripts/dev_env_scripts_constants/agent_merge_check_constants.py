"""Named constants for agent_merge_check, the agent merge check."""

from __future__ import annotations

GITHUB_API_ROOT = "https://api.github.com"
GITHUB_GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
PULL_REQUEST_ENDPOINT_TEMPLATE = "{api_root}/repos/{slug}/pulls/{number}"
REVIEW_THREADS_ENDPOINT_TEMPLATE = (
    "{api_root}/repos/{slug}/pulls/{number}/ccr/review_threads"
)
ACCEPT_HEADER = "Accept"
GITHUB_ACCEPT_TYPE = "application/vnd.github+json"
AUTHORIZATION_HEADER = "Authorization"
BEARER_PREFIX = "Bearer "
CONTENT_TYPE_HEADER = "Content-Type"
JSON_CONTENT_TYPE = "application/json"
UTF8_ENCODING = "utf-8"
REQUEST_TIMEOUT_SECONDS = 30

ALL_TOKEN_ENVIRONMENT_VARIABLES = ("GH_TOKEN", "GITHUB_TOKEN")

DRAFT_KEY = "draft"
MERGEABLE_STATE_KEY = "mergeable_state"
NUMBER_KEY = "number"
TITLE_KEY = "title"
HEAD_KEY = "head"
SHA_KEY = "sha"

MERGEABLE_STATE_CLEAN = "clean"
MERGEABLE_STATE_BEHIND = "behind"
MERGEABLE_STATE_DIRTY = "dirty"
MERGEABLE_STATE_BLOCKED = "blocked"
MERGEABLE_STATE_UNSTABLE = "unstable"
MERGEABLE_STATE_UNKNOWN = "unknown"
SETTLE_ATTEMPT_COUNT = 5
SETTLE_WAIT_SECONDS = 3

DRAFT_HOLD_REASON = (
    "The pull request is a draft, so it carries no verdict to merge on. "
    "Mark it ready once its checks pass."
)
BEHIND_HOLD_REASON = (
    "The head is behind the base branch and the branch rule requires an "
    "up-to-date head. Merge the base branch into this one and push."
)
DIRTY_HOLD_REASON = (
    "The head conflicts with the base branch. Merge the base branch into "
    "this one, resolve the conflict, and push."
)
BLOCKED_HOLD_REASON = (
    "A required status check is not passing on this head. Read the failing "
    "check, fix it, and push."
)
UNSTABLE_HOLD_REASON = (
    "A check on this head is failing or still running. Wait for it, and fix "
    "it when it comes back red."
)
ALL_HOLD_REASONS_BY_STATE = {
    MERGEABLE_STATE_BEHIND: BEHIND_HOLD_REASON,
    MERGEABLE_STATE_DIRTY: DIRTY_HOLD_REASON,
    MERGEABLE_STATE_BLOCKED: BLOCKED_HOLD_REASON,
    MERGEABLE_STATE_UNSTABLE: UNSTABLE_HOLD_REASON,
}
UNKNOWN_STATE_HOLD_TEMPLATE = (
    "GitHub reports the merge state as {state}, which this check does not "
    "treat as ready. Read the pull request page."
)
UNRESOLVED_THREADS_HOLD_TEMPLATE = (
    "{count} review thread(s) are open. Answer each one and resolve it."
)

MERGE_VERDICT_LABEL = "MERGE"
HOLD_VERDICT_LABEL = "HOLD"
VERDICT_LINE_TEMPLATE = "{label} {slug}#{number} {sha} :: {detail}"
SHORT_SHA_LENGTH = 7
READY_DETAIL = "green, no open review thread, ready for the agent to merge"

MERGE_EXIT_CODE = 0
HOLD_EXIT_CODE = 1
ERROR_EXIT_CODE = 2

NO_SIGN_IN_MESSAGE = "No GitHub token in the environment. Set GH_TOKEN or GITHUB_TOKEN."
SLUG_SEPARATOR = "/"
SLUG_ARGUMENT_HELP = "Repository as owner/name, such as jl-cmd/claude-dev-env."
NUMBER_ARGUMENT_HELP = "Pull request number."
COMMAND_DESCRIPTION = (
    "Report whether a pull request is ready for the agent that drives it to merge it."
)

REVIEW_THREAD_PAGE_SIZE = 100
UNRESOLVED_THREAD_QUERY = """
query($owner: String!, $name: String!, $number: Int!, $pageSize: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: $pageSize) {
        nodes { isResolved isOutdated }
      }
    }
  }
}
"""
QUERY_KEY = "query"
VARIABLES_KEY = "variables"
OWNER_VARIABLE = "owner"
NAME_VARIABLE = "name"
NUMBER_VARIABLE = "number"
PAGE_SIZE_VARIABLE = "pageSize"
DATA_KEY = "data"
REPOSITORY_KEY = "repository"
PULL_REQUEST_KEY = "pullRequest"
REVIEW_THREADS_KEY = "reviewThreads"
NODES_KEY = "nodes"
ALL_THREAD_NODE_KEYS = (
    DATA_KEY,
    REPOSITORY_KEY,
    PULL_REQUEST_KEY,
    REVIEW_THREADS_KEY,
    NODES_KEY,
)
ALL_RESOLVED_KEYS = ("isResolved", "is_resolved", "resolved")
ALL_OUTDATED_KEYS = ("isOutdated", "is_outdated", "outdated")
