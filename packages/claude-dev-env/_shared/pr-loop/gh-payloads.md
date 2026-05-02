# gh API payloads

Shared payload shapes for posting PR reviews and replies. Used by `bugteam`, `qbug`, `pr-converge`, `monitor-many`.

## Build payloads with jq + gh api --input

Build JSON with `jq --rawfile` / `-Rs` reading per-finding markdown bodies from temp files; pipe to `gh api ... --input -`. Avoids shell-quoting hazards and satisfies the `gh-body-backtick-guard` hook.

## One review per loop

POST to `repos/<owner>/<repo>/pulls/<number>/reviews` once per audit loop. Payload: `event: "COMMENT"`, the review body, and one `comments[]` object per anchored finding.

```bash
jq -n \
  --rawfile review_body <tmp_review_body.md> \
  --arg commit_id "$(git rev-parse HEAD)" \
  --rawfile finding_body_1 <tmp_finding_1.md> \
  --arg path_1 "<file_1>" \
  --argjson line_1 <line_1> \
  [... one finding_body_K / path_K / line_K triple per finding ...] \
  '{
     commit_id: $commit_id,
     event: "COMMENT",
     body: $review_body,
     comments: [
       {path: $path_1, line: $line_1, side: "RIGHT", body: $finding_body_1}
       [, ... ]
     ]
   }' \
| gh api repos/<owner>/<repo>/pulls/<number>/reviews -X POST --input -
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

POST to `repos/<owner>/<repo>/pulls/<number>/comments/<finding_comment_id>/replies`:

```bash
jq -Rs '{body: .}' <tmp_reply.md \
| gh api repos/<owner>/<repo>/pulls/<number>/comments/<finding_comment_id>/replies -X POST --input -
```

## Anchor fallback (line not in diff)

Lines not in the PR diff cannot anchor an inline comment. Omit them from `comments[]` and list under the review body's `### Findings without a diff anchor` section. Outcome record per finding: `used_fallback="true"`, empty `finding_comment_id`, `finding_comment_url` = parent review URL.

## Review POST failure fallback (issue comment)

When the review POST fails, post one issue comment carrying the full review body to `repos/<owner>/<repo>/issues/<number>/comments`:

```bash
jq -Rs '{body: .}' <tmp_fallback.md \
| gh api repos/<owner>/<repo>/issues/<number>/comments -X POST --input -
```

All findings in the loop record `used_fallback="true"`; `finding_comment_url` = issue comment URL.

## Endpoints

- Review POST: `repos/{owner}/{repo}/pulls/{pull}/reviews`
- Reply POST: `repos/{owner}/{repo}/pulls/{pull}/comments/{id}/replies`
- Fallback issue comment: `repos/{owner}/{repo}/issues/{issue}/comments` (`issue` = PR number)

## SHA capture timing

`commit_id` and any `<head_sha_at_post_time>` reference: `git rev-parse HEAD` immediately before the POST, in the cwd of whichever subagent or process is posting.

## Body file UTF-8 encoding

Write each markdown body to a temp file via the BOM-free PowerShell pattern (`[IO.File]::WriteAllText($path, $content, [Text.UTF8Encoding]::new($false))`) before `gh api` consumes it. See `~/.claude/rules/gh-body-file.md`.
