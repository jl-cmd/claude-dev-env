# GitHub PR comments

Per-loop pull-request reviews: findings render as a tree under one parent
review. The audit agent posts the review. The fix agent posts replies after
its commit lands.

- **Per-loop review** — One review per loop. The review body is the loop
  header (audit counts); child comments are the anchored findings.
- **Fix replies** — Reply to each child finding comment after the commit
  lands. Body: `Fixed in <commit_sha>` if addressed, or `Could not address
  this loop: <one-line reason>` if not.

## MCP tool calls (no shell, no jq, no gh CLI)

Bodies are passed as plain string parameters to the MCP tool calls — the
tools handle JSON encoding internally, so backticks, newlines, and quoted
text inside the body survive without escaping. There are no temp files, no
`jq` pipelines, and no `gh api ... --input -` invocations.

### Per-loop review (three-step pending-review flow)

The `pull_request_review_write` tool does **not** accept a `comments[]`
array. The MCP-native shape is pending-review + per-comment add + submit.

1. Create the pending review:

   ```
   mcp__plugin_github_github__pull_request_review_write(
     method="create",
     owner="<owner>",
     repo="<repo>",
     pullNumber=<number>
   )
   ```

   Omit `event` so the review stays pending. Capture
   `<head_sha_at_post_time>` with `git rev-parse HEAD` in the subagent cwd
   immediately before this call.

2. For each anchored finding, in index order, call:

   ```
   mcp__plugin_github_github__add_comment_to_pending_review(
     owner="<owner>",
     repo="<repo>",
     pullNumber=<number>,
     path="<file>",
     line=<line>,
     side="RIGHT",
     subjectType="LINE",
     body="<finding markdown>"
   )
   ```

   For multi-line anchors also pass `startLine=<start>` and
   `startSide="RIGHT"`.

3. Submit the pending review with the loop-header body:

   ```
   mcp__plugin_github_github__pull_request_review_write(
     method="submit_pending",
     owner="<owner>",
     repo="<repo>",
     pullNumber=<number>,
     event="COMMENT",
     body="<review body>"
   )
   ```

   Harvest the parent review `html_url` and the child comment
   `id`/`html_url` entries from the submit_pending response. If the
   response does not surface child comments, follow up with
   `pull_request_read(method="get_review_comments", owner=<owner>,
   repo=<repo>, pullNumber=<number>)` filtered to the just-submitted review
   id and match child comments to anchored findings in the order they were
   added in step 2.

### Fix reply

```
mcp__plugin_github_github__add_reply_to_pull_request_comment(
  owner="<owner>",
  repo="<repo>",
  pullNumber=<number>,
  commentId=<finding_comment_id>,
  body="<reply text>"
)
```

### Review POST failure fallback

The three-step pending-review flow is the default path because GitHub
renders one collapsible review with anchored child comments. It is not
the only valid path. Bail out and use the issue-comment fallback below
when:

- Any of steps 1–3 fails (rate limit, network, malformed payload).
- Steps 1–2 succeed but step 3 fails repeatedly (two retries is plenty —
  do not loop on a broken pending review).
- The pending review is in an unrecoverable state mid-flow (orphaned
  pending from a prior aborted run, partial-add failures with no clean
  recovery path, MCP responses that do not parse).

Mechanical retry of the three-step flow when it is clearly stuck wastes
the loop. The judgment call belongs to the validator. Clean up first
with:

```
mcp__plugin_github_github__pull_request_review_write(
  method="delete_pending",
  owner="<owner>",
  repo="<repo>",
  pullNumber=<number>
)
```

then post one PR-level comment carrying the review header plus every
finding inline:

```
mcp__plugin_github_github__add_issue_comment(
  owner="<owner>",
  repo="<repo>",
  issue_number=<number>,
  body="<full fallback text>"
)
```

`issue_number` is the PR number for PR-level comments. Mark every finding
`used_fallback="true"` and set `finding_comment_url` to the issue-comment
URL.

## Review body template

The canonical review body formatter is
[`format_review_body.py`](../../_shared/pr-loop/scripts/format_review_body.py):

```
python scripts/format_review_body.py --loop <N> --p0-count <N> --p1-count <N> --p2-count <N> [--unanchored-count <N>]
```

Emits `## /bugteam loop <N> audit: <P0>P0 / <P1>P1 / <P2>P2` to stdout,
with an unanchored-findings section when `--unanchored-count > 0`.

If the audit returns zero findings, still post **one** review with
`event="COMMENT"`, no anchored child comments, and body
`## /bugteam loop <N> audit: 0P0 / 0P1 / 0P2 → clean` so each loop's
section is self-contained on the PR.

## Anchor-validation fallback

The MCP review-submit call rejects the entire submit if any of the
already-added pending comments target a line not in the diff. Before
calling `add_comment_to_pending_review`, validate every finding's
`(file, line)` against the captured diff. Findings not in the diff are
**not** added as anchored comments; list them in the review body under
`### Findings without a diff anchor`. Outcome XML: `used_fallback="true"`,
`finding_comment_id=""`, `finding_comment_url=<review_url>` (parent URL
when there is no child). Log fallback count in outcome XML for the lead's
final report. The loop continues; anchor mismatch does not abort.

## GitHub MCP tools used

- `pull_request_review_write` — methods `create`, `submit_pending`,
  `delete_pending`.
- `add_comment_to_pending_review` — anchored review comments.
- `add_reply_to_pull_request_comment` — fix replies on existing review
  comments.
- `add_issue_comment` — top-level PR comment fallback (`issue_number` is
  the PR number).
- `pull_request_read` (`get_review_comments`) — fallback for harvesting
  child-comment ids/urls if the submit_pending response does not surface
  them to the caller.

Reference: https://github.com/github/github-mcp-server.
