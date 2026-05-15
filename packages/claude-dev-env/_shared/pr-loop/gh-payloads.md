# MCP-based payloads

Shared payload shapes for posting PR reviews and replies. Used by `bugteam`, `qbug`, `pr-converge`, `monitor-many`.

## Build payloads with MCP tools

Build payloads as structured arguments to MCP tools. Body content passes as a string parameter directly.

## One review per loop

Posting the per-loop audit review is handled by
[`_shared/pr-loop/scripts/post_audit_thread.py`](scripts/post_audit_thread.py).
The script owns the review-create/POST/retry flow internally; callers no longer
build the GitHub reviews-API payload themselves. See
[`skills/bugteam/SKILL.md` § Audit posting](../../skills/bugteam/SKILL.md#audit-posting)
for the contract and [`skills/bugteam/PROMPTS.md`](../../skills/bugteam/PROMPTS.md)
for the AUDIT-step invocation shape.

## Review body skeleton

The review body skeleton lives in
[`audit-reply-template.md`](audit-reply-template.md) between the
`<!-- audit-body-skeleton:start -->` and `<!-- audit-body-skeleton:end -->`
markers. `post_audit_thread.py` reads that skeleton at runtime and substitutes
its placeholders (`<Skill>`, `<state_label>`, `<heading>`, severity counts,
collapsed `<details>` block). Callers pass the skill name, state, commit SHA,
and findings JSON; the body shape is owned by the template.

## Reply to a finding

Call `add_reply_to_pull_request_comment` with the finding comment ID and a
reply body rendered from
[`audit-reply-template.md`](audit-reply-template.md):

```
add_reply_to_pull_request_comment(
    commentId=finding_comment_id,
    body=reply_body,
    owner=owner,
    repo=repo,
    pullNumber=pull_number
)
```

The `body` follows the unified reply skeleton documented in
[`audit-reply-template.md` § Template skeleton](audit-reply-template.md#template-skeleton).

## Anchor fallback (line not in diff)

Lines not in the PR diff cannot anchor an inline comment. The AUDIT teammate
keeps such findings out of the findings JSON handed to
`post_audit_thread.py`, lists them in the audit outcome XML under `<finding>`
with an empty `finding_comment_id`, and surfaces them in the calling skill's
user-facing output (chat reply to the user) rather than in the PR review body.

## Review POST failure

There is no fallback path. `post_audit_thread.py` exits `2` on retry
exhaustion (four non-2xx responses across the built-in `1s / 4s / 16s` backoff)
and the orchestrator halts with `error: post_audit_thread retry exhausted`.
A hard blocker on the audit-posting path is a halt condition, not a degraded
flat-issue-comment fall-through.

## Endpoints

- Review: handled by `post_audit_thread.py` (POSTs to
  `/repos/{owner}/{repo}/pulls/{N}/reviews` internally).
- Reply: `add_reply_to_pull_request_comment(...)`.

## SHA capture timing

`commit_id` and any `<head_sha_at_post_time>` reference: `git rev-parse HEAD` immediately before the POST, in the cwd of whichever subagent or process is posting.

