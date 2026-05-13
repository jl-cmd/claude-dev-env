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

    add_issue_comment(owner="OWNER", repo="REPO", issue_number=NUMBER, body="bugbot run")

`bugbot run` is the only recognized re-trigger phrase; alternative phrasings silently no-op.

### Mark PR ready: `update_pull_request(draft=false)`

Mark a draft PR as ready for review:

    update_pull_request(pullNumber=NUMBER, owner=OWNER, repo=REPO, draft=false)

### Reply to inline comment: `python scripts/post_fix_reply.py`

Reply to an inline review comment thread:

```
python scripts/post_fix_reply.py --owner <O> --repo <R> --pr-number <N> \
  --in-reply-to <COMMENT_ID> --body "<reply text>"
```

Omit `--in-reply-to` to post a general PR comment instead.

### Mergeability: `pull_request_read(method="get")`

Read mergeability fields from the PR:

    pull_request_read(method="get", pullNumber=NUMBER, owner=OWNER, repo=REPO)

Fields: `.mergeable`, `.mergeable_state`, `.head.sha`.

### Copilot reviews: `python scripts/fetch_copilot_reviews.py`

```
python scripts/fetch_copilot_reviews.py --owner <O> --repo <R> --pr-number <N>
```

Returns JSON array of Copilot reviews newest-first. Classification:
`APPROVED` → clean, `CHANGES_REQUESTED` → dirty, `COMMENTED` with
non-empty body → dirty.

### Copilot inline comments: `pull_request_read(method="get_review_comments")`

Fetch via MCP and filter for Copilot inline threads:

    pull_request_read(method="get_review_comments", pullNumber=NUMBER, owner=OWNER, repo=REPO)
      → filter threads where `is_outdated == false` AND `is_resolved == false`
        AND any comment author matches copilot (case-insensitive)
        AND `pull_request_review_id` matches latest Copilot review on target commit

### Request Copilot review: `gh api` REST endpoint

```
gh api --method POST repos/<O>/<R>/pulls/<N>/requested_reviewers \
  -f 'reviewers[]=copilot-pull-request-reviewer[bot]'
```

Check for an existing pending review first with
`python scripts/check_pending_reviews.py --owner <O> --repo <R> --pr-number <N> --user copilot`.

## Shared modules

Shared Python utilities live under `_shared/pr-loop/scripts/` — `_xml_utils.py` for XML serialization, `_cli_utils.py` for CLI guards, `_path_resolver.py` for canonical path resolution. These serve `/bugteam`, `/qbug`, `/findbugs`, and `/fixbugs` equally.

## Tests

Unit tests for gh wrapper scripts are removed. Reviewer interaction is tested through the MCP server contract.
