# GitHub PR comments

Per-loop pull-request reviews and post-fix replies use two distinct transports:

- **Per-loop audit review** — posted via [`post_audit_thread.py`](../../../_shared/pr-loop/scripts/post_audit_thread.py). One review per audit pass. `APPROVE` on CLEAN (the request event; GitHub stores it as `state=APPROVED`; body documents "no findings", zero inline comments). `REQUEST_CHANGES` on DIRTY (one inline anchored comment per finding; each becomes its own resolvable thread).
- **Fix replies** — posted via the GitHub MCP `add_reply_to_pull_request_comment` after the fix commit lands. The reply body uses the unified template at [`../../../_shared/pr-loop/audit-reply-template.md`](../../../_shared/pr-loop/audit-reply-template.md); reply and `resolve_thread` are atomic per thread.

## Per-loop audit review (post_audit_thread.py)

Run the script at the end of every audit pass:

```
python "${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/post_audit_thread.py" \
  --skill bugteam \
  --owner <owner> \
  --repo <repo> \
  --pr-number <N> \
  --commit <head_sha> \
  --state <CLEAN|DIRTY> \
  --findings-json <path>
```

Capture `<head_sha>` via `git rev-parse HEAD` in the subagent cwd immediately before this call so the review attaches to the commit the audit actually scoped.

`--findings-json` points to a JSON file whose root is a list of objects shaped `{path, line, side, severity, description, fix_summary}`. Build it from the merged Shape A findings: finding `file` → `path`. Each finding's `failure_mode` carries the full audit-to-fix handoff text per [`agents/code-quality-agent.md`](../../../agents/code-quality-agent.md); split `failure_mode` at the literal `Fix:` heading so the failure narrative becomes `description` and the suffix beginning at `Fix:` (including the trailing `Validation:` clause) becomes `fix_summary`. When a finding's `failure_mode` omits the `Fix:` heading, write the full text to BOTH `description` and `fix_summary` so the script's body template (`INLINE_COMMENT_BODY_TEMPLATE` in [`scripts/config/post_audit_thread_constants.py`](../../../_shared/pr-loop/scripts/config/post_audit_thread_constants.py)) renders coherently. Set `side="RIGHT"` for every entry. On CLEAN the list is empty (`[]`); on DIRTY the list carries one entry per finding.

The script handles retries internally — 1s / 4s / 16s backoff across four attempts (one initial plus three retries). Exit codes:

- `0` — review posted; the new review's `html_url` is on stdout.
- `1` — user input error (bad arguments, malformed findings JSON, missing template).
- `2` — retry exhaustion. Hard blocker; the lead exits `error: post_audit_thread retry exhausted` without retrying and without falling back to a flat issue comment.

Harvest the parent review URL from stdout, then extract the numeric review id from the URL's `#pullrequestreview-<id>` suffix (the trailing URL fragment of `html_url`, the part after `#`). Fetch child-comment URLs via `pull_request_read(method="get_review_comments", owner=<owner>, repo=<repo>, pullNumber=<N>)` filtered to that review id. That same response carries each comment's PR review thread node id (e.g. `PRRT_kwDOxxx`) — capture it alongside the numeric comment id. Match children to findings in the order they appear in the findings JSON, and store the mapping as `loop_comment_index[finding_id]` carrying both `finding_comment_id` (numeric) and `thread_node_id` (`PRRT_kwDOxxx`) for the FIX step to reply against and resolve.

The script reads its body skeleton from [`../../../_shared/pr-loop/audit-reply-template.md`](../../../_shared/pr-loop/audit-reply-template.md) at runtime, so the template doc remains the single source of truth for the body shape — edits there propagate without restarting the caller.

## Fix reply (MCP)

After the fix commit lands, post one reply per finding thread and resolve the thread atomically.

```
mcp__plugin_github_github__add_reply_to_pull_request_comment(
  owner="<owner>",
  repo="<repo>",
  pullNumber=<number>,
  commentId=<finding_comment_id>,
  body="<reply body using unified template>"
)
```

The reply body uses the unified template from [`../../../_shared/pr-loop/audit-reply-template.md`](../../../_shared/pr-loop/audit-reply-template.md). Per-status `<status_line>` / `<action_heading>` values live in [`../PROMPTS.md`](../PROMPTS.md) § FIX execution step 8.

Immediately after the reply call returns, resolve the same thread:

```
mcp__plugin_github_github__pull_request_review_write(
  method="resolve_thread",
  owner="<owner>",
  repo="<repo>",
  pullNumber=<number>,
  threadId=<thread_node_id>
)
```

`<thread_node_id>` is the PR review thread node ID (`PRRT_kwDOxxx`) harvested above when calling `get_review_comments`, distinct from the numeric comment ID used in the reply call. See [obstacles/fix-resolve-thread.md](obstacles/fix-resolve-thread.md) for the full identifier-shape rationale.

The two calls form one atomic per-thread action. Do not yield to the lead between them. Do not batch all replies before any resolves.

## Anchor validation

GitHub's reviews endpoint rejects the entire POST if any inline comment in `comments[]` targets a line not present in the diff at `--commit`. Validate `(path, line)` against the captured diff before adding a finding to the findings JSON. Findings without a diff anchor stay out of the JSON; surface them in the calling skill's user-facing output instead so the audit pass still completes.

## GitHub MCP tools used

- `add_reply_to_pull_request_comment` — fix replies on existing review comments.
- `pull_request_review_write` (`method="resolve_thread"`) — thread resolution after the reply lands; called atomically with the reply.
- `pull_request_read` (`method="get_review_comments"`) — harvest child-comment ids/urls after the script's parent review posts.

Reference: https://github.com/github/github-mcp-server.
