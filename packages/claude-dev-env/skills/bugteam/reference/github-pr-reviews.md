# GitHub PR comments (bugteam-only)

Transport, exit codes, retry/backoff, and payload shapes live in
[`../../../_shared/pr-loop/gh-payloads.md`](../../../_shared/pr-loop/gh-payloads.md)
and
[`post_audit_thread.py`](../../../_shared/pr-loop/scripts/post_audit_thread.py).
Read those for how the review POST runs; this file covers only bugteam lead and
FIX behavior around that transport.

## Lead posts the audit review

The lead runs `post_audit_thread.py` at the end of every audit pass:

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

Capture `<head_sha>` via `git rev-parse HEAD` in the subagent cwd immediately
before this call so the review attaches to the commit the audit actually scoped.

- **CLEAN** — `APPROVE` event (GitHub stores `state=APPROVED`); body documents
  "no findings"; empty findings list (`[]`); zero inline comments.
- **DIRTY** — `REQUEST_CHANGES`; one inline anchored comment per finding (each
  becomes its own resolvable thread).

## Findings JSON (Shape A `Fix:` split)

`--findings-json` is a JSON list of
`{path, line, side, severity, description, fix_summary}`. Build it from the
merged Shape A findings: finding `file` → `path`. Each finding's `failure_mode`
carries the full audit-to-fix handoff text per
[`agents/code-quality-agent.md`](../../../agents/code-quality-agent.md); split
`failure_mode` at the literal `Fix:` heading so the failure narrative becomes
`description` and the suffix beginning at `Fix:` (including the trailing
`Validation:` clause) becomes `fix_summary`. When a finding's `failure_mode`
omits the `Fix:` heading, write the full text to BOTH `description` and
`fix_summary`. Set `side="RIGHT"` for every entry.

## Anchor validation before JSON

Validate `(path, line)` against the captured diff before adding a finding to the
findings JSON. GitHub rejects the entire review POST when any inline comment
targets a line missing from the diff at `--commit`. Findings without a diff
anchor stay out of the JSON; surface them in the calling skill's user-facing
output so the audit pass still completes.

## FIX waits for harvest (`loop_comment_index`)

FIX does not reply until harvest completes. After a successful post:

1. Read the parent review URL from stdout; extract the numeric review id from
   the `#pullrequestreview-<id>` suffix.
2. Fetch child comments via
   `pull_request_read(method="get_review_comments", ...)` filtered to that
   review id.
3. Capture each comment's PR review thread node id (`PRRT_kwDOxxx`) alongside
   the numeric comment id.
4. Match children to findings in findings-JSON order; store
   `loop_comment_index[finding_id]` with `finding_comment_id` (numeric) and
   `thread_node_id` (`PRRT_kwDOxxx`).

## Atomic reply + resolve

After the fix commit lands, post one reply per finding thread and resolve that
thread as one atomic action. Do not yield to the lead between the two calls. Do
not batch all replies before any resolves.

```
add_reply_to_pull_request_comment(
  owner="<owner>",
  repo="<repo>",
  pullNumber=<number>,
  commentId=<finding_comment_id>,
  body="<reply body using unified template>"
)

pull_request_review_write(
  method="resolve_thread",
  owner="<owner>",
  repo="<repo>",
  pullNumber=<number>,
  threadId=<thread_node_id>
)
```

Reply body template:
[`../../../_shared/pr-loop/audit-reply-template.md`](../../../_shared/pr-loop/audit-reply-template.md).
Per-status `<status_line>` / `<action_heading>` values live in
[`../PROMPTS.md`](../PROMPTS.md) § FIX execution step 8. Identifier-shape
rationale: [obstacles/fix-resolve-thread.md](obstacles/fix-resolve-thread.md).
