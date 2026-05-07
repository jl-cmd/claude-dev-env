# pr-converge MCP tool references

The GitHub MCP server exposes pull request operations through the tools listed below. Pagination is handled server-side; callers receive the complete result set in a single response.

## MCP tools

### PR context: `pull_request_read(method="get")`

Read PR metadata:

    pull_request_read(method="get", pullNumber=NUMBER, owner=OWNER, repo=REPO)

Fields: `.number`, `.url`, `.head.sha`, `.base.ref`, `.head.ref`, `.isDraft`.

### Bugbot reviews: `pull_request_read(method="get_reviews")`

Fetch all reviews and filter for `cursor[bot]`:

    pull_request_read(method="get_reviews", pullNumber=NUMBER, owner=OWNER, repo=REPO)

Classification: clean if review body has no findings count; dirty if body matches "found N potential issue".

### Bugbot inline comments: `pull_request_read(method="get_review_comments")`

Fetch all review comments and filter for `cursor[bot]`, matching `pull_request_review_id` to the newest Bugbot review on the target commit:

    pull_request_read(method="get_review_comments", pullNumber=NUMBER, owner=OWNER, repo=REPO)

### PR head SHA: `pull_request_read(method="get")`

Read the current HEAD SHA from the PR:

    pull_request_read(method="get", pullNumber=NUMBER, owner=OWNER, repo=REPO)

Access `.head.sha` from the response.

### Trigger bugbot: `add_issue_comment`

Post the bugbot re-trigger comment:

    add_issue_comment(owner="OWNER", repo="REPO", issueNumber=NUMBER, body="bugbot run")

`bugbot run` is the only recognized re-trigger phrase; alternative phrasings silently no-op.

### Mark PR ready: `update_pull_request(draft=false)`

Mark a draft PR as ready for review:

    update_pull_request(pullNumber=NUMBER, owner=OWNER, repo=REPO, draft=false)

### Reply to inline comment: `add_reply_to_pull_request_comment`

Reply to an inline review comment thread:

    add_reply_to_pull_request_comment(
      commentId=COMMENT_ID,
      body=REPLY_BODY,
      owner=OWNER,
      repo=REPO,
      pullNumber=NUMBER
    )

### Mergeability: `pull_request_read(method="get")`

Read mergeability fields from the PR:

    pull_request_read(method="get", pullNumber=NUMBER, owner=OWNER, repo=REPO)

Fields: `.mergeable`, `.mergeable_state`, `.head.sha`.

### Copilot reviews: `pull_request_read(method="get_reviews")`

Fetch all reviews and filter for `copilot-pull-request-reviewer[bot]`:

    pull_request_read(method="get_reviews", pullNumber=NUMBER, owner=OWNER, repo=REPO)

Classification: `APPROVED` → clean, `CHANGES_REQUESTED` → dirty, `COMMENTED` with non-empty body → dirty.

### Copilot inline comments: `pull_request_read(method="get_review_comments")`

Fetch all review comments and filter for `copilot-pull-request-reviewer[bot]`, matching `pull_request_review_id` to the newest Copilot review on the target commit:

    pull_request_read(method="get_review_comments", pullNumber=NUMBER, owner=OWNER, repo=REPO)

### Request Copilot review: `add_issue_comment` or `request_copilot_review`

Two options:

1. Comment-based trigger:
   ```
   add_issue_comment(owner=OWNER, repo=REPO, issueNumber=NUMBER, body="@copilot review")
   ```
2. Dedicated MCP tool (when available):
   ```
   request_copilot_review(owner=OWNER, repo=REPO, pullNumber=NUMBER)
   ```

The `[bot]` suffix is load-bearing per `../../copilot-review/SKILL.md`.

### Claude reviews: `pull_request_read(method="get_reviews")`

Fetch all reviews and filter for login containing `claude`:

    pull_request_read(method="get_reviews", pullNumber=NUMBER, owner=OWNER, repo=REPO)

Classification: same state-based rules as Copilot reviews.

### Claude inline comments: `pull_request_read(method="get_review_comments")`

Fetch all review comments and filter for login containing `claude`, matching `pull_request_review_id` to the newest Claude review on the target commit:

    pull_request_read(method="get_review_comments", pullNumber=NUMBER, owner=OWNER, repo=REPO)

## Shared modules

No shared fetch core modules are needed. Each review or comment fetch is a single MCP tool call with client-side filtering by login.

## Tests

Unit tests for gh wrapper scripts are removed. Reviewer interaction is tested through the MCP server contract.
