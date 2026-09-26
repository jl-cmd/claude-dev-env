"""Constants for the review_closure script.

Per the project's configuration conventions, script-level scalar constants
live in dev_env_scripts_constants alongside timing.py.
"""

GITHUB_API_ROOT: str = "https://api.github.com"
"""Root of the GitHub REST API."""

GITHUB_GRAPHQL_ENDPOINT: str = "https://api.github.com/graphql"
"""Endpoint that answers the review-thread query."""

PULL_REQUEST_ENDPOINT_TEMPLATE: str = "{api_root}/repos/{slug}/pulls/{number}"
"""REST route carrying one pull request."""

REVIEW_THREADS_ENDPOINT_TEMPLATE: str = (
    "{api_root}/repos/{slug}/pulls/{number}/ccr/review_threads"
)
"""REST route a Claude Code session has for review threads."""

CHECK_RUNS_ENDPOINT_TEMPLATE: str = (
    "{api_root}/repos/{slug}/commits/{sha}/check-runs?per_page={page_size}"
)
"""REST route carrying the check runs reported on one commit."""

REVIEW_THREAD_PAGE_SIZE: int = 100
"""How many review threads and comments one query asks for."""

CHECK_RUN_PAGE_SIZE: int = 100
"""How many check runs one request asks for."""

REVIEW_THREAD_QUERY: str = """
query($owner: String!, $name: String!, $number: Int!, $pageSize: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: $pageSize) {
        nodes {
          path
          isResolved
          isOutdated
          comments(first: $pageSize) {
            nodes {
              body
              author { login }
            }
          }
        }
      }
    }
  }
}
"""
"""GraphQL query for the review threads on one pull request."""

ALL_THREAD_NODE_KEYS: tuple[str, ...] = (
    "data",
    "repository",
    "pullRequest",
    "reviewThreads",
    "nodes",
)
"""Path from the GraphQL answer down to the review-thread list."""

ALL_RESOLVED_KEYS: tuple[str, ...] = ("isResolved", "resolved", "is_resolved")
"""Field names either route uses for a resolved review thread."""

ALL_OUTDATED_KEYS: tuple[str, ...] = ("isOutdated", "outdated", "is_outdated")
"""Field names either route uses for a thread whose code has been replaced."""

ALL_COMMENT_LIST_KEYS: tuple[str, ...] = ("comments", "all_comments")
"""Field names either route uses for a thread's comment list."""

COMMENT_NODES_KEY: str = "nodes"
"""GraphQL wraps a comment list in this field."""

COMMENT_BODY_KEY: str = "body"
"""Field carrying a comment's text."""

ALL_COMMENT_AUTHOR_KEYS: tuple[str, ...] = ("author", "user")
"""Field names either route uses for a comment's author."""

AUTHOR_LOGIN_KEY: str = "login"
"""Field carrying an author's GitHub login."""

THREAD_PATH_KEY: str = "path"
"""Field carrying the file a review thread points at."""

UNNAMED_THREAD_SUBJECT: str = "a review thread"
"""Subject text for a thread that names no file."""

RED_CIRCLE_MARKER: str = "\U0001f534"
"""The red circle a review marks a blocking finding with."""

APPROVALS_CHECK_NAME: str = "Claude Approvals"
"""Name of the check run whose rows carry blocking findings."""

ALL_BLOCKING_CONCLUSIONS: tuple[str, ...] = ("failure", "action_required")
"""Check-run conclusions that mean a blocking row is open on this head."""

APPROVALS_OPEN_REASON: str = (
    "the Claude Approvals check reports a blocking row on this commit"
)
"""Why a failing approvals check leaves the pull request open."""

RED_CIRCLE_OPEN_REASON: str = (
    "a blocking finding here carries no reply from the driving agent"
)
"""Why a red-circle thread stays open until the agent answers it."""

UNANSWERED_OPEN_REASON: str = "unresolved, with no reply from the driving agent"
"""Why an ordinary thread stays open."""

CHECK_RUNS_KEY: str = "check_runs"
"""Field carrying the check-run list in the REST answer."""

CHECK_RUN_NAME_KEY: str = "name"
"""Field carrying a check run's name."""

CHECK_RUN_CONCLUSION_KEY: str = "conclusion"
"""Field carrying a check run's conclusion."""

HEAD_KEY: str = "head"
"""Field carrying a pull request's head."""

SHA_KEY: str = "sha"
"""Field carrying a commit identifier."""

NUMBER_KEY: str = "number"
"""Field carrying a pull request number."""

USER_KEY: str = "user"
"""Field carrying the account that opened a pull request."""

SHORT_SHA_LENGTH: int = 7
"""How much of a commit identifier the verdict line prints."""

SLUG_SEPARATOR: str = "/"
"""Separator between owner and name in a repository slug."""

QUERY_KEY: str = "query"
"""GraphQL payload field carrying the query text."""

VARIABLES_KEY: str = "variables"
"""GraphQL payload field carrying the query variables."""

OWNER_VARIABLE: str = "owner"
"""GraphQL variable naming the repository owner."""

NAME_VARIABLE: str = "name"
"""GraphQL variable naming the repository."""

NUMBER_VARIABLE: str = "number"
"""GraphQL variable naming the pull request number."""

PAGE_SIZE_VARIABLE: str = "pageSize"
"""GraphQL variable naming the page size."""

ALL_TOKEN_ENVIRONMENT_VARIABLES: tuple[str, ...] = (
    "GITHUB_TOKEN",
    "GH_TOKEN",
)
"""Environment variables that carry a GitHub token, in the order read."""

NO_SIGN_IN_MESSAGE: str = (
    "No GitHub token found. Set GITHUB_TOKEN or GH_TOKEN and run this again."
)
"""What to print when no token is available."""

COMMAND_DESCRIPTION: str = (
    "Report whether every review finding on a pull request head has been "
    "answered by the agent driving it."
)
"""Help text for the command."""

SLUG_ARGUMENT_HELP: str = "Repository as owner/name."
"""Help text for the repository argument."""

NUMBER_ARGUMENT_HELP: str = "Pull request number."
"""Help text for the pull request argument."""

DRIVER_LOGIN_ARGUMENT_HELP: str = (
    "A login whose comments count as the driving agent's reply. Repeatable. "
    "The account that opened the pull request always counts."
)
"""Help text for the driver login argument."""

CLOSED_VERDICT_LABEL: str = "CLOSED"
"""Verdict label for a pull request with every finding answered."""

OPEN_VERDICT_LABEL: str = "OPEN"
"""Verdict label for a pull request with a finding still waiting."""

CLOSED_DETAIL: str = "every review finding on this commit is answered"
"""Detail text on a closed verdict."""

OPEN_DETAIL_TEMPLATE: str = "{count} review finding(s) wait on the driving agent"
"""Detail text on an open verdict."""

VERDICT_LINE_TEMPLATE: str = "{label} {slug}#{number} {sha} :: {detail}"
"""Shape of the one verdict line this command prints."""

FINDING_LINE_TEMPLATE: str = "  - {subject}: {reason}"
"""Shape of each open-finding line printed under the verdict."""

CLOSED_EXIT_CODE: int = 0
"""Exit status when every finding is answered."""

OPEN_EXIT_CODE: int = 1
"""Exit status when a finding waits on the driving agent."""

ERROR_EXIT_CODE: int = 2
"""Exit status when the pull request state could not be read."""

REQUEST_TIMEOUT_SECONDS: int = 30
"""How long one GitHub request waits for an answer."""

REQUEST_FAILED_TEMPLATE: str = "{url} answered {status}"
"""What to report when GitHub answers with something other than success."""

GET_METHOD: str = "GET"
"""HTTP method for a read."""

POST_METHOD: str = "POST"
"""HTTP method the GraphQL query uses."""

COMMENT_IDS_KEY: str = "comment_ids"
"""Field the session route uses for a thread's comment identifiers."""

COMMENT_IDENTIFIER_KEY: str = "id"
"""Field carrying a review comment's identifier."""

REVIEW_COMMENTS_ENDPOINT_TEMPLATE: str = (
    "{api_root}/repos/{slug}/pulls/{number}/comments?per_page={page_size}&page={page}"
)
"""REST route carrying one page of a pull request's review comments."""

COMMENT_PAGE_SIZE: int = 100
"""How many review or top-level comments one page carries."""

MAX_COMMENT_PAGES: int = 20
"""How many comment pages one listing reads before it stops."""

TOP_LEVEL_COMMENTS_ENDPOINT_TEMPLATE: str = (
    "{api_root}/repos/{slug}/issues/{number}/comments?per_page={page_size}&page={page}"
)
"""REST route carrying one page of a pull request's top-level comments."""

HTML_URL_KEY: str = "html_url"
"""Field carrying the page address of a top-level comment."""

CREATED_AT_KEY: str = "created_at"
"""Field carrying when a top-level comment was posted."""

UPDATED_AT_KEY: str = "updated_at"
"""Field carrying when a top-level comment was last edited."""

TOP_LEVEL_OPEN_REASON_TEMPLATE: str = (
    "a top-level comment from {author} with no later top-level comment from "
    "the driving agent"
)
"""Why a top-level comment stays open until the agent posts after it."""

UNREADABLE_TOP_LEVEL_COMMENT_TEMPLATE: str = (
    "a top-level comment carries an unreadable timestamp: {record}"
)
"""What to report when a top-level comment's timestamps do not parse."""
