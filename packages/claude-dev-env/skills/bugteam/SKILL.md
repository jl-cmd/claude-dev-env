---
name: bugteam
description: >-
  Open pull request audit–fix until convergence: CODE_RULES gate, clean-room
  audit (`code-quality-agent`, opus) and fix (`clean-coder`), per-loop
  GitHub reviews, 20-audit cap; grant then revoke `.claude/**`. AUDIT routes
  through `resolve_worker_spawn.py` (headless tiers or Agent-tool fallback).
  Triggers: '/bugteam', 'run the bug team', 'auto-fix the PR until clean',
  'loop audit and fix'.
---

# Bugteam

Audit–fix until convergence. Bugfind: `code-quality-agent`, fresh process or
fresh agent context each loop, auditing all A–P categories via the
worker-spawn dispatcher. Bugfix: `clean-coder`. Hard cap: 20 audit loops.
Grant `.claude/**` at start, revoke always at end.

The audit agent loads the A–P category rubrics from
`$HOME/.claude/audit-rubrics/{category_rubrics,prompts}/` alongside
[`PROMPTS.md`](PROMPTS.md) and produces a single outcome XML per loop.

## Transport check (before any GitHub step)

Run `command -v gh`; when it succeeds, run `gh auth status`; once the PR
scope is resolved, run `gh api repos/<owner>/<repo> --jq .permissions.push`
and take `true` as the pass. When any check fails, run the
`pr-loop-cloud-transport` skill first and route every `gh` operation in this
skill through its substitution matrix.

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
  same signal. Gate semantics live in the `reviewer-gates` skill
  ([../reviewer-gates/SKILL.md](../reviewer-gates/SKILL.md)).
- **No PR or upstream diff.** `No PR or upstream diff. /bugteam needs a target.`
- **Dirty tree.** `Uncommitted changes detected. Stash, commit, or revert before
  /bugteam.`
- **Missing subagents.** Before Step 0, confirm `code-quality-agent` and
  `clean-coder` exist. Else: `Required subagent type <name> not installed.
  /bugteam needs both code-quality-agent and clean-coder available.`

## Audit posting

Every internal audit pass (CLEAN or DIRTY) ends with one posted GitHub PR
review; the mandate applies whether bugteam runs inside `/pr-converge` or
standalone. Run the shared posting helper
[`_shared/pr-loop/scripts/post_audit_thread.py`](../../_shared/pr-loop/scripts/post_audit_thread.py)
with `--skill bugteam`: map findings to the review-comment JSON (the
`failure_mode` split at the literal `Fix:` heading), partition anchored from
unanchored comments, honor the self-PR reviewer toggle
(`BUGTEAM_REVIEWER_ACCOUNT`) and the exit codes, and harvest the ids.

Bugteam-only obligations:

- The lead runs the posting step; the FIX teammate waits for the harvested
  ids before replying or resolving.
- Record each harvested `{finding_comment_id, finding_comment_url,
  thread_node_id}` triple into `loop_comment_index` (per-loop scope; see
  [reference/team-setup.md](reference/team-setup.md) § Loop state block) so
  the matching FIX action owns the reply-and-resolve unit.
- Exit-code policy: the bugteam row in
  [`../../_shared/pr-loop/post-audit-thread-contract.md`](../../_shared/pr-loop/post-audit-thread-contract.md)
  § Per-caller policy.

## Progress checklist

```
[ ] Step 0: project permissions granted
[ ] Step 1: PR scope resolved
[ ] Step 2: loop state set
[ ] Step 3: cycle complete (converged | cap reached | stuck | error)
[ ] Step 4: apply pr-loop-lifecycle Close
    Skill({skill: "pr-loop-lifecycle", args: "--skill bugteam close"})
    (see pr-loop-lifecycle/SKILL.md "How callers invoke this")
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
| Posting the end-of-pass audit review (APPROVE on CLEAN, REQUEST_CHANGES with inline anchored comments on DIRTY) | [§ Audit posting](#audit-posting), which runs [`_shared/pr-loop/scripts/post_audit_thread.py`](../../_shared/pr-loop/scripts/post_audit_thread.py) |
| Posting per-finding fix replies via GitHub MCP `add_reply_to_pull_request_comment` (rendered with the unified template at [`_shared/pr-loop/audit-reply-template.md`](../../_shared/pr-loop/audit-reply-template.md)) | [reference/github-pr-reviews.md](reference/github-pr-reviews.md) |
| Teardown, PR description rewrite composed by the lead, permission revoke, final report | [../pr-loop-lifecycle/reference/teardown-publish-permissions.md](../pr-loop-lifecycle/reference/teardown-publish-permissions.md) |
| Spawn-prompt XML, A–P category bindings, outcome XML schemas | [PROMPTS.md](PROMPTS.md) |
| Per-category audit content (sub-buckets, decision criteria, ready-to-send Variant C templates) | `$HOME/.claude/audit-rubrics/{category_rubrics,prompts}/` |
| Invariants and design rationale | [CONSTRAINTS.md](CONSTRAINTS.md), [reference/design-rationale.md](reference/design-rationale.md) |
| Audit-contract finding shape (Shape A / B), Haiku secondary, post-fix self-audit | [../../_shared/pr-loop/audit-contract.md](../../_shared/pr-loop/audit-contract.md) |
| Exit-scenario examples (converged, cap-reached, stuck, refusal, mixed-outcome) | [EXAMPLES.md](EXAMPLES.md) |
| Doc URLs and verbatim quotes | [sources.md](sources.md) |
| Historical Copilot gap analysis (superseded) | [reference/copilot-gap-analysis.md](reference/copilot-gap-analysis.md) |

## Folder map

- `SKILL.md` — this hub.
- `reference/` — workflow detail per situation.
- `scripts/` — utility scripts executed, not loaded as primary context.
- `PROMPTS.md` — spawn XML, A–P category bindings, outcome schemas.
- `CONSTRAINTS.md` — invariants.
- `EXAMPLES.md` — exit scenarios.
- `sources.md` — doc URLs and verbatim quotes.
- `~/.claude/audit-rubrics/` — installed by `npx claude-dev-env` from
  `packages/claude-dev-env/audit-rubrics/`; the audit agent reads all A–P
  rubrics under `category_rubrics/` and prompts under `prompts/`. Required
  at audit time alongside `PROMPTS.md`.
