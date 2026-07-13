"""Named constants for the convergence gate IO leaves.

Holds the short-SHA length, the review field key the newest-first sort reads,
the join separators for gate detail strings, the fixture payload keys, and the
GraphQL query that lists a PR's review threads.
"""

SHORT_SHA_LENGTH: int = 7

REVIEW_SUBMITTED_AT_KEY: str = "submitted_at"

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
FIXTURE_DEFAULT_THREADS_DETAIL: str = "0 unresolved"
FIXTURE_DEFAULT_PENDING_DETAIL: str = "none pending"
MERGEABLE_STATE_CLEAN: str = "clean"

COPILOT_DOWN_BYPASS_NOTE: str = "copilot_down"
BUGBOT_DOWN_BYPASS_NOTE: str = "bugbot_down"
REVIEWER_UNAVAILABLE_NOTE_TEMPLATE: str = "{token} unavailable: {message}"
GATE_PROBE_ERROR_DETAIL_TEMPLATE: str = "enforced (probe error: {reason})"
SETTINGS_DISK_FALLBACK_LOG_TEMPLATE: str = (
    "reviewer-availability: settings.json unreadable; using process env for %s and %s"
)
