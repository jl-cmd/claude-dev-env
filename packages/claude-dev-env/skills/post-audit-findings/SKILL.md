---
name: post-audit-findings
description: >-
  Publishes an audit pass as one GitHub PR review via the shared
  post_audit_thread.py: maps audit findings to the {path, line, side,
  severity, description, fix_summary} JSON shape (splitting failure_mode at
  the literal `Fix:` heading), partitions anchored vs unanchored findings so
  one bad anchor cannot reject the whole POST, handles the self-PR reviewer
  toggle via BUGTEAM_REVIEWER_ACCOUNT, and harvests finding comment ids and
  PRRT thread node ids for the fix loop. Invoked by audit skills (bugteam,
  qbug, findbugs) after each audit pass, CLEAN or DIRTY; not for ad-hoc PR
  comments or review replies.
---

# Post Audit Findings

**Core principle:** every audit pass — CLEAN or DIRTY — lands on the PR as exactly one review, so the unresolved-thread gate sees the pass and each finding becomes its own resolvable thread.

## How callers invoke this

- **Skill-capable contexts** (a lead session with the `Skill` tool): `Skill({skill: "post-audit-findings", args: "--skill <caller> --owner <O> --repo <R> --pr-number <N> --commit <head_sha> --state <CLEAN|DIRTY> --findings-json <path>"})`.
- **Fallback** (a subagent or teammate without the `Skill` tool): the caller's spawn prompt says "Read `~/.claude/skills/post-audit-findings/SKILL.md` and apply it with the parameters below."

`--skill <caller>` is required — the posted review names the audit skill that produced it. Capture `<head_sha>` once, at the start of the posting step, via `git rev-parse HEAD` in the worktree the diff was scoped against.

## Findings-JSON mapping

The findings file's root is a list of objects shaped `{path, line, side, severity, description, fix_summary}`. Map each audit finding:

- Finding `file` → `path`.
- The `failure_mode` field carries both the failure narrative AND the `Fix:` / `Validation:` text (per [`agents/code-quality-agent.md`](../../agents/code-quality-agent.md), "The `failure_mode` field is the audit-to-fix handoff"). Split it at the literal `Fix:` heading: the prefix becomes `description`; the suffix starting at `Fix:` (including the trailing `Validation:` clause) becomes `fix_summary`. When a finding omits the `Fix:` heading, write the full `failure_mode` text to BOTH fields so the script's `INLINE_COMMENT_BODY_TEMPLATE` still renders coherently.
- Set `side="RIGHT"` for every entry.
- On CLEAN, the file holds an empty array (`[]`).

## Anchored vs unanchored partition

Before serializing, partition findings into **anchored** (the line appears in the diff at `--commit`) and **unanchored** (it does not). Only anchored findings go into the JSON — the GitHub reviews API rejects the ENTIRE POST when any inline comment targets a line outside the diff, so a single unanchored entry breaks the whole review. Surface unanchored findings in the caller's user-facing report instead.

Zero anchored findings → `--state CLEAN`; one or more → `--state DIRTY`.

## Posting

```bash
python "$HOME/.claude/_shared/pr-loop/scripts/post_audit_thread.py" \
  --skill <caller> \
  --owner <owner> \
  --repo <repo> \
  --pr-number <N> \
  --commit <head_sha> \
  --state <CLEAN|DIRTY> \
  --findings-json <path>
```

The script POSTs one review to `/repos/{owner}/{repo}/pulls/{N}/reviews`: `event=APPROVE` on CLEAN (GitHub stores it as `state=APPROVED`; empty `comments[]`; body documents "no findings"), `event=REQUEST_CHANGES` on DIRTY (one inline anchored comment per finding; each becomes its own resolvable thread).

**Self-PR auto-toggle.** GitHub rejects both `APPROVE` and `REQUEST_CHANGES` with HTTP 422 when the authenticated identity matches the PR author. `post_audit_thread.py` detects this via `gh api user` + `gh api repos/<o>/<r>/pulls/<n>` and auto-resolves an alternate gh account's token for the reviews POST — the active `gh auth` account is not mutated; only the bearer token on the request changes, so no swap-back step exists.

Configuration:

- `GH_TOKEN` / `GITHUB_TOKEN` env vars take precedence over the toggle — set one to pin a reviewer identity by token.
- `BUGTEAM_REVIEWER_ACCOUNT` names which authenticated alternate to prefer (for example `BUGTEAM_REVIEWER_ACCOUNT=jl-cmd`). The env var name is shared across every skill that invokes `post_audit_thread.py`. When unset, the script falls back to the first alternate account `gh auth status` reports.
- The named alternate must be logged in (`gh auth login -h github.com -u <login>`) before the audit runs; on self-PR with no usable alternate the script exits 1 with a message pointing at `gh auth login`.

**Exit codes:** `0` — success; the new review's `html_url` prints to stdout (surface it in the caller's report). `1` — user input error. `2` — retry exhaustion (1s / 4s / 16s backoff across four attempts): a hard blocker. On exit 2 the caller halts the loop (`error: post_audit_thread retry exhausted`) or tells the user the review post failed and the unresolved-thread gate will not see this pass — never a silent retry.

## Harvest ids for the fix loop

After a DIRTY post, fetch the new review's threads once and record, per finding: the finding comment's URL, its numeric comment id (the reply anchor), and its thread node id (`PRRT_…`, the `resolve_thread` handle):

```
pull_request_read(method="get_review_comments", ...) → match comments to the new review id
```

Hand the id triple to the fix step — `pr-fix-protocol` consumes it for the reply-and-resolve unit. Harvesting at post time saves the fix executor a second fetch and pins the mapping before any thread state changes.

## Gotchas

- **One unanchored comment voids the whole review.** The partition is not an optimization; skipping it makes every DIRTY post a coin flip.
- **CLEAN still posts.** A pass that finds nothing and posts nothing is invisible to the unresolved-thread gate and to anyone auditing the loop's history.
- **Exit 2 is a stop, not a retry.** The script already retried with backoff; a caller looping on top of it hammers the API to no effect.

## Folder map

- `SKILL.md` — this file. The posting script and its body template constants live in `_shared/pr-loop/scripts/` (`post_audit_thread.py`, `pr_loop_shared_constants/post_audit_thread_constants.py`); the review-payload reference is `_shared/pr-loop/gh-payloads.md`.
