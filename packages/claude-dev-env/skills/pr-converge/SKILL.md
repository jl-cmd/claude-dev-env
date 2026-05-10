---
name: pr-converge
description: >-
  Drives the current PR to convergence by looping Cursor Bugbot, a
  second-opinion bug audit, and Copilot — applying TDD fixes, posting
  inline replies, and re-triggering reviewers each tick until all three
  reviewers are clean on the same HEAD. Use when the user says
  '/pr-converge', 'drive PR to convergence', 'loop bugbot and bugteam',
  'babysit bugbot and bugteam', 'until both are clean', or 'converge this
  PR'.
---

# PR Converge

One tick per invocation. Bugbot ↔ bugteam ↔ Copilot loop on a draft PR
until all three are clean on the same `HEAD` and mergeable.

## Pre-flight

`ScheduleWakeup` not in this turn's tool registry → abort. Report
`pr-converge requires ScheduleWakeup; aborting` and return.

## Gotchas

Highest-signal content. Append a bullet each time a tick fails in a new
way — these are the hard-won lessons that keep the loop honest. Once this
grows to 5 or more items, suggest spinning up a subagent to investigate, fix,
post a fresh PR in a fresh branch based on origin main to the user.

- **`ScheduleWakeup` not in subagent tool registries** — background
  `general-purpose` tick cannot schedule re-entry; only parent session
  with `ScheduleWakeup` in registry can call it.
- **Review body and inline comments desync for same `commit_id`** —
  "dirty body, zero inline rows at `current_head`" is **`inline_lag`**,
  not **`dirty`**. Bump `inline_lag_streak`, wait 90s, retry fetch.
- **`state.json` without §Concurrency lock loses merges** when teammates
  finish in same wall-clock window.
- **`tick_count` must not double-increment** — conversation state line
  only when **no** `state.json`; with `state.json`, only the
  orchestrator bump increments.
- **Duplicate `bugbot run` while review queued** — skip Step 3 when the
  latest `bugbot run` PR comment has an `:eyes:` or `:+1:` reaction;
  wait for review or HEAD change before re-triggering.
- **Bugbot unresponsive after `bugbot run` post** — after posting the
  trigger comment via `add_issue_comment`, capture the returned comment
  ID. Wait 15s, then check for reactions on that specific comment via
  `issue_read(method="get_comments", owner=OWNER, repo=REPO, issue_number=NUMBER)`
  matching on the captured ID. Zero reactions means bugbot is down; set
  `bugbot_down = true`, `phase = BUGTEAM`, and continue bugteam in the
  same tick instead of scheduling another bugbot wakeup.
- **Bot login fields differ by endpoint** — `get_reviews` returns
  `.user.login` (object), but `get_review_comments` returns `.author`
  (string, not an object). Threads use `is_outdated` (not `commit_id`) to
  indicate staleness. Always check the correct fields and use
  case-insensitive substring matching on login values, never strict
  equality.
- **COPILOT_WAIT → fix → COPILOT_WAIT cycle skips back-to-back-clean** —
  after fixing Copilot findings and pushing, `phase` MUST route to
  `BUGBOT`, not back to `COPILOT_WAIT`. The model will improvise
  COPILOT_WAIT behavior if per-tick.md Step 2 has no handler for it.
  The handler in per-tick.md exists to prevent exactly this path.

## First tick of a session

Read [`reference/state-schema.md`](reference/state-schema.md),
[`reference/ground-rules.md`](reference/ground-rules.md), then
[`reference/per-tick.md`](reference/per-tick.md).

## Match situation, read spoke

| Situation | Read |
|---|---|
| Starting any tick | [`reference/per-tick.md`](reference/per-tick.md) |
| Bugbot or audit finding to fix and push | [`reference/fix-protocol.md`](reference/fix-protocol.md) |
| Bugteam reports `convergence (zero findings)` AND `bugbot_clean_at == current_head` | [`reference/convergence-gates.md`](reference/convergence-gates.md) |
| Multi-PR session — `state.json` exists at `<TMPDIR>/pr-converge-<session_id>/` | [`reference/multi-pr-orchestration.md`](reference/multi-pr-orchestration.md) |
| Scheduling the next wakeup | [`workflows/schedule-wakeup-loop.md`](workflows/schedule-wakeup-loop.md) |
| Hard blocker, convergence reached, or user stops loop | [`reference/stop-conditions.md`](reference/stop-conditions.md) |
| All GitHub interactions use `plugin:github:github` MCP tools | [`reference/per-tick.md`](reference/per-tick.md) |
| Tick is ambiguous against the spokes above | [`reference/examples.md`](reference/examples.md) |

## Folder map

- `SKILL.md` — this hub.
- `reference/` — workflow detail per situation.
- `workflows/` — pacing implementations.
