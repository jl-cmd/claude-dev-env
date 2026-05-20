---
name: bugteam
description: >-
  Open pull request audit–fix until convergence: CODE_RULES gate, clean-room
  audit (`code-quality-agent`, opus) and fix (`clean-coder`, opus), per-loop
  GitHub reviews, 20-audit cap; grant then revoke `.claude/**`. Spawns
  background subagents (`Agent(..., run_in_background=true)`). Triggers: '/bugteam', 'run
  the bug team', 'auto-fix the PR until clean', 'loop audit and fix'.
---

# Bugteam

Audit–fix until convergence. Bugfind: `code-quality-agent`, fresh context each
loop, auditing all A–K categories. Bugfix: `clean-coder`. Hard cap: 20 audit
loops. Grant `.claude/**` at start, revoke always at end.

The audit agent loads the A–K category rubrics from
`$HOME/.claude/audit-rubrics/{category_rubrics,prompts}/` alongside
[`PROMPTS.md`](PROMPTS.md) and produces a single outcome XML per loop.

## Pre-flight

```bash
python "${CLAUDE_SKILL_DIR}/scripts/bugteam_preflight.py"
```

Auto-remediation runs automatically when `core.hooksPath` is the failing check;
other failures require manual fix before Step 0. Full detail:
[reference/team-setup.md](reference/team-setup.md) § Pre-flight.

## Refusals

First match wins; respond with the quoted line exactly and stop:

- **Disabled via environment.** When `CLAUDE_REVIEWS_DISABLED` contains the
  token `bugteam` (comma-separated, case-insensitive, whitespace-tolerant):
  `/bugteam is disabled via CLAUDE_REVIEWS_DISABLED.` The pre-flight script
  also exits 7 in this case so any caller invoking it directly halts on the
  same signal.
- **No PR or upstream diff.** `No PR or upstream diff. /bugteam needs a target.`
- **Dirty tree.** `Uncommitted changes detected. Stash, commit, or revert before
  /bugteam.`
- **Missing subagents.** Before Step 0, confirm `code-quality-agent` and
  `clean-coder` exist. Else: `Required subagent type <name> not installed.
  /bugteam needs both code-quality-agent and clean-coder available.`

## Audit posting

Every internal audit pass (CLEAN or DIRTY) ends with one call to
`post_audit_thread.py`. The script POSTs a single review to
`/repos/{owner}/{repo}/pulls/{N}/reviews` with `event=APPROVE` on CLEAN
(the request event; GitHub stores it as `state=APPROVED`; empty
`comments[]`, body documents "no findings") or
`event=REQUEST_CHANGES` on DIRTY (one inline anchored comment per
finding; each becomes its own resolvable thread). The mandate applies
whether bugteam runs inside `/pr-converge` or standalone.

**Self-PR auto-toggle.** GitHub rejects both `APPROVE` and
`REQUEST_CHANGES` reviews with HTTP 422 when the authenticated identity
matches the PR author ("Cannot approve/request changes on your own pull
request"). `post_audit_thread.py` detects this case via `gh api user` +
`gh api repos/<o>/<r>/pulls/<n>` and auto-resolves an alternate gh
account's token for the reviews POST — the active `gh auth` account is
not mutated; only the bearer token sent on the request changes. After
the POST the active account is still whoever it was before, so no
"swap back" step is needed.

Configuration:

- `GH_TOKEN` / `GITHUB_TOKEN` env vars take precedence over the toggle.
  Set them when you need to pin a specific reviewer identity by token
  rather than by account login.
- `BUGTEAM_REVIEWER_ACCOUNT` env var names which authenticated alternate
  to prefer when a toggle is needed (for example,
  `BUGTEAM_REVIEWER_ACCOUNT=jl-cmd`). When unset, the script falls back
  to the first alternate account `gh auth status` reports.
- The named alternate must be logged in (`gh auth login -h github.com -u
  <login>`) before the audit skill runs. The script exits 1 with a
  pointing-at-`gh auth login` message when self-PR is detected and no
  usable alternate is authenticated.

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

`--findings-json` points to a JSON file whose root is a list of objects
shaped `{path, line, side, severity, description, fix_summary}`. The
audit agent's persisted finding output maps as follows: finding `file`
→ `path`, and the agent's `failure_mode` field carries both the failure
narrative AND the `Fix:` / `Validation:` text per
[`agents/code-quality-agent.md`](../../agents/code-quality-agent.md)
("The `failure_mode` field is the audit-to-fix handoff"). Split
`failure_mode` at the literal `Fix:` heading: the prefix (the failure
narrative) becomes `description`, and the suffix starting at `Fix:`
(including the trailing `Validation:` clause) becomes `fix_summary`.
When the agent omits the `Fix:` heading on a given finding, write the
full `failure_mode` text to BOTH `description` and `fix_summary` so the
script's body template (`INLINE_COMMENT_BODY_TEMPLATE` in
[`_shared/pr-loop/scripts/pr_loop_shared_constants/post_audit_thread_constants.py`](../../_shared/pr-loop/scripts/pr_loop_shared_constants/post_audit_thread_constants.py))
still renders coherently. Set `side="RIGHT"` for every entry. On CLEAN,
pass an empty array (`[]`) so the script posts an APPROVE review
(GitHub stores it as `state=APPROVED`) with a "no findings" summary and
zero inline comments.

Exit codes: `0` on success (emits the new review's `html_url` to
stdout); `1` on user input error; `2` on retry exhaustion (1s / 4s /
16s backoff across four attempts total). Exit 2 is a hard blocker; the
lead halts the loop and exits `error: post_audit_thread retry
exhausted` without retrying.

## Progress checklist

```
[ ] Step 0: project permissions granted
[ ] Step 1: PR scope resolved
[ ] Step 2: loop state set
[ ] Step 3: cycle complete (converged | cap reached | stuck | error)
[ ] Step 4: working tree clean
[ ] Step 4.5: PR description rewritten (or skip warning logged)
[ ] Step 5: project permissions revoked
[ ] Step 6: final report printed
```

## First invocation of a session

Read [reference/team-setup.md](reference/team-setup.md), then
[reference/audit-and-teammates.md](reference/audit-and-teammates.md), then
[reference/github-pr-reviews.md](reference/github-pr-reviews.md) for an
end-to-end mental model before starting Step 0.

## Match situation, read spoke

| Situation | Read |
|---|---|
| Pre-flight, project permissions, PR scope, loop state, run-name / temp-dir | [reference/team-setup.md](reference/team-setup.md) |
| `--bugbot-retrigger` flag behavior | [reference/team-setup.md](reference/team-setup.md) |
| AUDIT action and code-rules pre-audit gate, pre-cycle walk, cycle decision tree | [reference/audit-and-teammates.md](reference/audit-and-teammates.md) |
| FIX action and verify-push semantics | [reference/audit-and-teammates.md](reference/audit-and-teammates.md) |
| Posting the end-of-pass audit review via `post_audit_thread.py` (APPROVE on CLEAN — the request event; GitHub stores it as `state=APPROVED` — REQUEST_CHANGES with inline anchored comments on DIRTY) | [§ Audit posting](#audit-posting) |
| Posting per-finding fix replies via GitHub MCP `add_reply_to_pull_request_comment` (rendered with the unified template at [`_shared/pr-loop/audit-reply-template.md`](../../_shared/pr-loop/audit-reply-template.md)) | [reference/github-pr-reviews.md](reference/github-pr-reviews.md) |
| Teardown, PR description rewrite via `pr-description-writer`, permission revoke, final report | [reference/teardown-publish-permissions.md](reference/teardown-publish-permissions.md) |
| Spawn-prompt XML, A–K category bindings, outcome XML schemas | [PROMPTS.md](PROMPTS.md) |
| Per-category audit content (sub-buckets, decision criteria, ready-to-send Variant C templates) | `$HOME/.claude/audit-rubrics/{category_rubrics,prompts}/` |
| Invariants and design rationale | [CONSTRAINTS.md](CONSTRAINTS.md), [reference/design-rationale.md](reference/design-rationale.md) |
| Audit-contract finding shape (Shape A / B), Haiku secondary, post-fix self-audit | [reference/audit-contract.md](reference/audit-contract.md) |
| Exit-scenario examples (converged, cap-reached, stuck, refusal, mixed-outcome) | [EXAMPLES.md](EXAMPLES.md) |
| Doc URLs and verbatim quotes | [sources.md](sources.md) |
| Historical Copilot gap analysis (superseded) | [reference/copilot-gap-analysis.md](reference/copilot-gap-analysis.md) |

## Folder map

- `SKILL.md` — this hub.
- `reference/` — workflow detail per situation.
- `scripts/` — utility scripts executed, not loaded as primary context.
- `PROMPTS.md` — spawn XML, A–K category bindings, outcome schemas.
- `CONSTRAINTS.md` — invariants.
- `EXAMPLES.md` — exit scenarios.
- `sources.md` — doc URLs and verbatim quotes.
- `~/.claude/audit-rubrics/` — installed by `npx claude-dev-env` from
  `packages/claude-dev-env/audit-rubrics/`; the audit agent reads all A–K
  rubrics under `category_rubrics/` and prompts under `prompts/`. Required
  at audit time alongside `PROMPTS.md`.
