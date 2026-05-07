---
name: monitor-open-prs
description: >-
  Discover every open pull request across the jl-cmd/* and JonEcho/*
  owner scopes, spawn /bugteam on each in parallel with the Groq-backed
  FIX implementer (BUGTEAM_FIX_IMPLEMENTER=groq-coder) and the bugbot
  re-trigger flag (--bugbot-retrigger), wrap the session in `bws run`
  to inject GROQ_API_KEY, and poll Cursor's bugbot replies after
  convergence so any post-Groq findings loop back through /bugteam.
  Triggers: '/monitor-open-prs', 'sweep the open PRs', 'groq-bugteam the backlog'.
---

# Monitor Open PRs

**Core principle:** One sweep covers every open PR across both owner scopes. Claude discovers PRs live via `scripts/discover_open_prs.py` which shells out to `gh search prs --owner <owner> --state open --json ...`, dispatches `/bugteam` per PR with `BUGTEAM_FIX_IMPLEMENTER=groq-coder` and `--bugbot-retrigger`, then polls Cursor's bugbot replies until each PR is quiet for a full backoff cycle.

## Contents

- When this skill applies — refusal cases and trigger conditions
- Discovery — `scripts/discover_open_prs.py` queries via `gh search prs` across both owner scopes
- Wrapping — `bws run` for GROQ_API_KEY injection
- Dispatch — `/bugteam --bugbot-retrigger <pr_numbers...>` with groq-coder + retrigger
- Post-convergence polling — bugbot replies and re-invocation
- `scripts/discover_open_prs.py` — the discovery helper

## When this skill applies

`/monitor-open-prs` authorizes one full sweep over all open PRs in both owner scopes.

Refusals — first match wins; respond with the quoted line exactly and stop:

- **bws not on PATH.** `bws not installed. /monitor-open-prs injects GROQ_API_KEY via Bitwarden Secrets Manager.`
- **GitHub API not accessible.** `get_me failed. /monitor-open-prs needs active GitHub MCP credentials.`
- **Dirty tree on the caller's repo.** `Uncommitted changes detected. Stash, commit, or revert before /monitor-open-prs.`
- **Required subagents missing.** Confirm `code-quality-agent`, `clean-coder`, and `groq-coder` exist. Else: `Required subagent type <name> not installed.`

## Discovery

Call `scripts/discover_open_prs.discover_open_prs(all_owners=["jl-cmd", "JonEcho"])` to merge the live open-PR list across both scopes. The helper shells out to `gh search prs --owner <owner> --state open --json number,repository,url,headRefName,baseRefName` for each owner scope and flattens the result to a uniform dict shape with keys `number`, `owner`, `repo`, `head_ref`, `base_ref`, `url`. Empty scopes contribute empty lists; an entirely empty sweep returns `[]` and exits cleanly.

## Secret Wrapping

Every `/bugteam` dispatch runs inside `bws run` so `GROQ_API_KEY` is injected from Bitwarden Secrets Manager without touching the filesystem. The project and secret UUIDs are fixed for this skill:

```bash
bws run \
  --project-id c69cedc5-aea1-4aa8-b350-b4300145d978 \
  -- \
  env BUGTEAM_FIX_IMPLEMENTER=groq-coder \
  /bugteam --bugbot-retrigger <pr_numbers...>
```

The `bws run` subshell resolves the project's secrets and exports them for the wrapped command. The `GROQ_API_KEY` secret's UUID inside that project is `b7e99a7f-2ecc-42b3-99a5-b434010622f9`. GitHub auth is not sourced through `bws` — existing MCP `get_me` credentials carry the session.

## Dispatch

For each discovered PR:

1. Resolve the PR's repo checkout (existing worktree or fresh `git clone`).
2. From that checkout, invoke `/bugteam --bugbot-retrigger <pr_number>` under the `bws run` wrapper from §Secret Wrapping.
3. The `BUGTEAM_FIX_IMPLEMENTER=groq-coder` env var routes the FIX role to the `groq-coder` subagent. The `--bugbot-retrigger` flag tells bugteam to post `bugbot run` as an issue comment after every successful FIX push so Cursor's bugbot re-evaluates the new commit.
4. Bugteam runs its own 10-loop audit/fix cycle per PR; this skill waits for each bugteam invocation to return before dispatching the next (or fanning out — see below).

**Fan-out (optional):** when the discovered list has more than one PR, the skill may spawn `/bugteam` dispatches in parallel by issuing multiple `Agent` calls in a single assistant message. Each dispatch operates in its own per-PR worktree (bugteam Step 1.1). Serialize when the caller sets an explicit `--serial` flag.

## Post-Convergence Polling

After a `/bugteam` invocation returns (converged, cap reached, stuck, or error), the PR may accumulate new Cursor bugbot comments within minutes. Poll for them:

1. Baseline: capture `since_timestamp` as the PR's last commit timestamp.
2. Every 60 seconds, call `pull_request_read(method="get", pullNumber=<pr_number>, owner=<owner>, repo=<repo>)` and filter the response's `comments` array for entries whose `.author.login` matches `"bugbot"` or `"cursor"` and `.createdAt` is after `<since_timestamp>`.
3. Back off: 60s → 120s → 240s → 480s → 960s. If five successive polls return empty, exit polling for this PR.
4. If bugbot posts a new finding in any poll, re-invoke `/bugteam <pr_number>` via the same `bws run` wrapper with the bugbot finding text seeded into the invocation's `bugs_to_fix` preamble. Reset the backoff.

### Polling Cost and Cadence

The five-step backoff sums to `60 + 120 + 240 + 480 + 960 = 1860` seconds (~31 minutes) of idle polling per PR before the skill declares bugbot quiet. A sweep over ten open PRs therefore retains up to ~5 wall-clock hours of bugbot-watch time beyond the active `/bugteam` work. Callers who need faster turnaround should pass `--serial` to disable fan-out (so polling starts only after the previous PR finishes) or accept the tradeoff: the backoff exists specifically to catch late bugbot analyses that can take several minutes to appear after a push.

## Final Report

After every PR has exited polling, emit:

```
/monitor-open-prs sweep summary
PRs discovered: <N>
  jl-cmd/*: <count>
  JonEcho/*: <count>
PRs converged clean: <count>
PRs hit 10-loop cap: <count>
PRs stuck: <count>
PRs errored: <count>
Bugbot re-triggers fired: <count>
Total Groq tokens consumed: <approx from /bugteam outcome summaries>
```

## Non-Negotiable Guardrails

- Never source secrets outside `bws run` — no `.env` files, no shell history, no logs.
- Never pass `--no-verify` or `--no-gpg-sign` to git in any dispatched bugteam run.
- Never open a PR from this skill; only comment on existing ones.
- Never merge or close PRs; the skill is read + audit + patch only.
