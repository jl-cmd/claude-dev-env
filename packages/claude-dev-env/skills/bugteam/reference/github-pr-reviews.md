# GitHub PR comments (Step 2.5)

Per-loop pull-request reviews: findings render as a tree under one parent review (similar to Cursor Bugbot). **Teammates own all PR comment posting** — bugfind posts the review (parent body plus child finding comments in one batched POST); bugfix posts fix replies. Comment, review, and reply POSTs belong to teammates. The lead’s single PR write is the final description rewrite at Step 4.5 (`pr-description-writer`).

- **Per-loop review** — One `POST /pulls/<number>/reviews` per loop, posted by the bugfind teammate **after** auditing. The review body is the loop header (audit counts); the review’s `comments[]` array holds one anchored finding per P0/P1/P2 finding. GitHub renders a single collapsible thread with each finding as a child comment.

- **Fix replies** — Reply to each child finding comment after the commit lands. Body: `Fixed in <commit_sha>` if addressed, or `Could not address this loop: <one-line reason>` if not. The `/pulls/<number>/comments/<id>/replies` endpoint works on any review comment, including those created as part of a review.

**Ordering:** Bugfind audits first, buffers findings, validates anchors against the captured diff, then posts the review **once** at the end. The review body states the finding count authoritatively. Keep all posting in that single end-of-loop review POST.

## CLI shapes (teammate)

All three POSTs use the same pattern: build JSON with `jq` (`--rawfile` or `-Rs` so markdown with backticks, newlines, and quotes survives intact), then pipe to `gh api ... --input -` on stdin. This avoids shell-quoting edge cases.

### Per-loop review (one POST creates parent + children)

Build `comments[]` programmatically from buffered, diff-anchored findings. Single-line shape: `{path, line, side: "RIGHT", body: <finding markdown>}`. Multi-line: `{path, start_line, start_side: "RIGHT", line, side: "RIGHT", body: ...}` (all four anchor fields required).

```
jq -n \
  --rawfile review_body <tmp_review_body.md> \
  --arg commit_id "$(git rev-parse HEAD)" \
  --rawfile finding_body_1 <tmp_finding_1.md> \
  --arg path_1 "<file_1>" \
  --argjson line_1 <line_1> \
  [... one finding_body_K / path_K / line_K triple per anchored finding ...] \
  '{
     commit_id: $commit_id,
     event: "COMMENT",
     body: $review_body,
     comments: [
       {path: $path_1, line: $line_1, side: "RIGHT", body: $finding_body_1}
       [, ... one object per anchored finding ...]
     ]
   }' \
| gh api repos/<owner>/<repo>/pulls/<number>/reviews -X POST --input -
```

Response JSON includes the parent review `id` / `html_url` and a `comments` array of child comments (`id`, `html_url`). Harvest children in index order and align with the finding list.

### Fix reply

```
jq -Rs '{body: .}' < <tmp_reply.md> \
| gh api repos/<owner>/<repo>/pulls/<number>/comments/<finding_comment_id>/replies -X POST --input -
```

### Review POST failure fallback

Top-level PR comment via issue-comments (`{issue_number}` is the PR number):

```
jq -Rs '{body: .}' < <tmp_fallback.md> \
| gh api repos/<owner>/<repo>/issues/<number>/comments -X POST --input -
```

`<head_sha_at_post_time>` is the SHA at post time (`git rev-parse HEAD` in the teammate’s working directory immediately before the POST). The review anchors finding comments to the head SHA at audit time (before this loop’s fix lands).

Write each body (review body and every per-finding body) to its own temp file before the `jq` pipeline. Bodies stay inside files the pipeline reads — they reach GitHub inside the JSON payload — which keeps them compatible with the `gh-body-backtick-guard` hook that scans command-line `--body` arguments.

## Review body template (`<tmp_review_body.md>`)

```
## /bugteam loop <N> audit: <P0>P0 / <P1>P1 / <P2>P2

<if any findings could not be anchored to a diff line, include this section:>
### Findings without a diff anchor

- **[severity] title** — <file>:<line> — <one-line description>
```

If the audit returns zero findings, still post **one** review with `event=COMMENT`, empty `comments[]`, and body `## /bugteam loop <N> audit: 0P0 / 0P1 / 0P2 → clean` so each loop’s section is self-contained on the PR.

## Anchor-validation fallback (teammate)

GitHub rejects the entire review POST if any `comments[]` entry targets a line not in the diff. Before posting, validate every finding’s `(file, line)` against the captured diff. Findings not in the diff are **not** added to `comments[]`; list them in the review body under `### Findings without a diff anchor`. Outcome XML: `used_fallback="true"`, `finding_comment_id=""`, `finding_comment_url=<review_url>` (parent URL when there is no child). Log fallback count in outcome XML for the lead’s final report. The loop continues; anchor mismatch does not abort.

## Review POST failure fallback

If the review POST fails (rate limit, network, malformed payload), fall back to one top-level issue comment containing the review body plus every finding inline (severity, file:line, description). Every finding in that run: `used_fallback="true"`, `finding_comment_url` = issue-comment URL. Use the issue-comment CLI shape above.

## GitHub REST endpoints

- Per-loop batched review: `POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews` (required: `body`, `event=COMMENT`, `commit_id`; optional `comments[]` — each entry needs `path`, `body`, `line`, `side`)
- Fix reply: `POST /repos/{owner}/{repo}/pulls/{pull_number}/comments/{comment_id}/replies` (required: `body`)
- Review-POST failure fallback: `POST /repos/{owner}/{repo}/issues/{issue_number}/comments` (required: `body`; `{issue_number}` is the PR number)
