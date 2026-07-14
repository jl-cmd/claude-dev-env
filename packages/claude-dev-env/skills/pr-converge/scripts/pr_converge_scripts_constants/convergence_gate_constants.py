"""Named constants for the convergence gate IO leaves.

Holds the short-SHA length, the join separators for gate detail strings, and
the GraphQL query that lists a PR's review threads.
"""

SHORT_SHA_LENGTH: int = 7

THREAD_PATH_JOIN_SEPARATOR: str = "; "

PENDING_REVIEWER_JOIN_SEPARATOR: str = ", "

GRAPHQL_REVIEW_THREADS_QUERY: str = """
query($owner: String!, $repo: String!, $number: Int!, $first: Int!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: $first, after: $cursor) {
        nodes {
          isResolved
          isOutdated
          path
          comments(first: 1) {
            nodes {
              author { login }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""

FIXTURE_KEY_HEAD_SHA: str = "head_sha"
FIXTURE_KEY_PR_OBJECT: str = "pr_object"
FIXTURE_KEY_REVIEWS: str = "reviews"
FIXTURE_KEY_UNRESOLVED_BOT_THREADS_PASSED: str = "unresolved_bot_threads_passed"
FIXTURE_KEY_UNRESOLVED_BOT_THREADS_DETAIL: str = "unresolved_bot_threads_detail"
FIXTURE_KEY_PENDING_REVIEWS_PASSED: str = "pending_reviews_passed"
FIXTURE_KEY_PENDING_REVIEWS_DETAIL: str = "pending_reviews_detail"
FIXTURE_KEY_CODEX_PERCENT_LEFT: str = "codex_percent_left"
FIXTURE_KEY_CODEX_CLEAN_AT: str = "codex_clean_at"
FIXTURE_DEFAULT_THREADS_DETAIL: str = "0 unresolved"
FIXTURE_DEFAULT_PENDING_DETAIL: str = "none pending"
MERGEABLE_STATE_CLEAN: str = "clean"

CODEX_GATE_LABEL: str = "codex_clean_at == current_head"
CODEX_BYPASS_DETAIL: str = "bypassed (codex_down)"
CODEX_SKIPPED_USAGE_DETAIL: str = "skipped (codex review not required)"
CODEX_CLEAN_DETAIL_TEMPLATE: str = "clean at %s"
CODEX_MISSING_CLEAN_DETAIL_TEMPLATE: str = "no codex clean on %s"
CLAUDE_JOB_DIR_ENV_VAR_NAME: str = "CLAUDE_JOB_DIR"
PR_CONVERGE_STATE_FILENAME: str = "pr-converge-state.json"
CODEX_CLEAN_AT_STATE_KEY: str = "codex_clean_at"
CODEX_DOWN_STATE_KEY: str = "codex_down"
MINIMUM_ABBREVIATED_SHA_LENGTH: int = 7
