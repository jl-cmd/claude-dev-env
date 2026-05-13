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
python "${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/preflight.py"
```

Auto-remediation runs automatically when `core.hooksPath` is the failing check;
other failures require manual fix before Step 0. Full detail:
[reference/team-setup.md](reference/team-setup.md) § Pre-flight.

## Refusals

First match wins; respond with the quoted line exactly and stop:

- **No PR or upstream diff.** `No PR or upstream diff. /bugteam needs a target.`
- **Dirty tree.** `Uncommitted changes detected. Stash, commit, or revert before
  /bugteam.`
- **Missing subagents.** Before Step 0, confirm `code-quality-agent` and
  `clean-coder` exist. Else: `Required subagent type <name> not installed.
  /bugteam needs both code-quality-agent and clean-coder available.`

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
| Posting per-loop reviews, fix replies, fallback PR comments via GitHub MCP | [reference/github-pr-reviews.md](reference/github-pr-reviews.md) |
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
