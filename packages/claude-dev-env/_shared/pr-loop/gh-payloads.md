# MCP-based payloads

Shared payload shapes for posting PR reviews and replies. Used by `bugteam`, `qbug`, `pr-converge`, `monitor-many`.

## Build payloads with MCP tools

Build payloads as structured arguments to MCP tools. Body content passes as a string parameter directly.

## One review per loop

Call `pull_request_review_write` once per audit loop. Payload: `event: "COMMENT"`, the review body, and one `comments[]` object per anchored finding.

```
pull_request_review_write(
    method="create",
    event="COMMENT",
    body=review_body,
    commitID=head_sha,
    owner=owner,
    repo=repo,
    pullNumber=pull_number,
    comments=[
        {path: file_path, line: line_number, side: "RIGHT", body: finding_body}
    ]
)
```

Single-line anchors: `{path, line, side: "RIGHT", body}`. Multi-line anchors add `start_line` and `start_side: "RIGHT"`.

Zero findings still post one review. Body line: `## /<workflow> loop <N> audit: 0P0 / 0P1 / 0P2 → clean`. `comments: []`.

## Review body template

```
## /<workflow> loop <N> audit: <P0>P0 / <P1>P1 / <P2>P2

### Findings without a diff anchor
(only when needed)
- **[severity] title** — <file>:<line> — <one-line description>
```

`<workflow>` is the calling skill name (`bugteam`, `qbug`, `pr-converge`).

## Reply to a finding

Call `add_reply_to_pull_request_comment` with the finding comment ID and reply body:

```
add_reply_to_pull_request_comment(
    commentId=finding_comment_id,
    body=reply_body,
    owner=owner,
    repo=repo,
    pullNumber=pull_number
)
```

## Anchor fallback (line not in diff)

Lines not in the PR diff cannot anchor an inline comment. Omit them from `comments[]` and list under the review body's `### Findings without a diff anchor` section. Outcome record per finding: `used_fallback="true"`, empty `finding_comment_id`, `finding_comment_url` = parent review URL.

## Review POST failure fallback (issue comment)

When the review POST fails, call `add_issue_comment` with the full review body:

```
add_issue_comment(
    owner=owner,
    repo=repo,
    issueNumber=pull_number,
    body=fallback_body
)
```

All findings in the loop record `used_fallback="true"`; `finding_comment_url` = issue comment URL.

## Endpoints

- Review: `pull_request_review_write(method="create", ...)`
- Reply: `add_reply_to_pull_request_comment(...)`
- Fallback issue comment: `add_issue_comment(...)`

## SHA capture timing

`commit_id` and any `<head_sha_at_post_time>` reference: `git rev-parse HEAD` immediately before the POST, in the cwd of whichever subagent or process is posting.

