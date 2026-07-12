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
