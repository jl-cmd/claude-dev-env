---
name: usage-pause
description: 5-hour usage window, agent context warm, weekly limit is near its cap. Triggers: '/usage-pause', 'pause until the usage window resets', 'wait out the usage limit', 'usage limit pause', 'usage limit', 'pause usage', 'usage pause'.
argument-hint: "[reset time like 10:20pm | duration like 74m]"
---

# /usage-pause

Pause on purpose before a usage limit kills in-flight work. The skill reads the 5-hour session window's reset time and remaining headroom, breaks the wait into ScheduleWakeup stages, keeps every agent context warm through the pause with checkpoint pings, and hands control back after the reset.

## Step 1 — resolve the usage window

Run the bundled resolver:

```
python "${CLAUDE_SKILL_DIR}/scripts/resolve_usage_window.py"
```

With an argument (`/usage-pause 10:20pm`, `/usage-pause 74m`), skip the probe and pass it through:

```
python "${CLAUDE_SKILL_DIR}/scripts/resolve_usage_window.py" --override "10:20pm"
```

On exit 0 the script prints one JSON object:

| Field | Meaning |
|---|---|
| `source` | `probe` or `override` |
| `reset_at` | When the 5-hour window resets (ISO-8601, local zone) |
| `seconds_until_reset` | The wait the stage plan covers |
| `stages_seconds` | The ScheduleWakeup stage durations, in firing order |
| `session_utilization` | Percent of the 5-hour window spent (null on override) |
| `weekly_utilization` | Percent of the weekly window spent (null on override) |
| `weekly_resets_at` | When the weekly window resets (null on override) |
| `weekly_near_cap` | True when the weekly meter is at or past the warn threshold |

On exit 2 the script prints `{"error": ...}`. Ask the user for a manual reset time via AskUserQuestion (offer clock-time and duration examples), then rerun with `--override`.

### Probe mechanism

`scripts/resolve_usage_window.py` is the source of truth for live probe behavior. Endpoint URL, header names/values, credential path and token keys, response bucket keys, stage sizing, and the weekly warn threshold all live in `scripts/usage_pause_constants/resolve_usage_window_constants.py` — read those modules for the current values; do not restate them here.

In short: the resolver picks a bearer token, probes the OAuth usage endpoint the interactive `/usage` panel uses, and returns the session and weekly buckets with utilization and reset times. Token sources, in order:

1. The Claude Code CLI's stored OAuth access token (honored only while unexpired).
2. The session ingress bearer token file named by `CLAUDE_SESSION_INGRESS_TOKEN_FILE` (cloud sessions).

Fallbacks, in order: both token sources unavailable (expired/unreadable credential and no ingress file), a failed request, or a response with no readable session-window reset time all end in exit 2 — the manual-override ask above. The manual path works with no probe at all, so the skill functions even when both token sources are unavailable.

Why this probe and not the others:

- The interactive `/usage` panel shows the same data but has no scriptable output.
- `claude -p --output-format json` spends usage to answer and its metadata reports per-call token counts, not the account window clock.
- `anthropic-ratelimit-*` response headers cover API-key Messages traffic, not the subscription session window, and reading them also costs a request.
- Refreshing the OAuth token from a script is out of scope: token rotation would desync the refresh token the CLI has on disk and log the CLI out. The resolver only ever reads tokens (credential file or session ingress file).

## Weekly limit guard

When `weekly_near_cap` is true, WARN the user — report `weekly_utilization` and `weekly_resets_at` — and stop. No pause choreography runs around the weekly limit; waiting out a weekly window is its own later build.

## Step 2 — the pause chain

Before the first sleep:

1. List active recurring loops (CronList). Record each one's schedule and prompt, then cancel it (CronDelete). Carry the recorded list inside the wakeup prompts so the state survives every stage.
2. Schedule the first stage with ScheduleWakeup, using the first duration in `stages_seconds` and the stage prompt template below.

The stage plan (`stages_seconds` from the resolver) keeps every stage under the maximum stage length and ends with a short tail so the final firing lands just past the reset. Stage sizing constants live in `scripts/usage_pause_constants/resolve_usage_window_constants.py`; a leftover too short to stand alone folds into the tail.

Every wakeup does exactly three things — ping, record, schedule — and dispatches no new work. The cache rationale: an unpinged idle agent left past the cache window resumes cold and re-reads its whole transcript, so pings run tighter than the cache lifetime and keep each agent's next real invocation cheap.

### Stage wakeup prompt template

```
/usage-pause stage <stage_number> of <stage_total>: pausing until <reset_time_local>.
Remaining chain (seconds): <remaining_stage_durations>. Cancelled crons: <cancelled_crons_json>.
1. Ping every live agent AND every idle-but-warm agent with exactly this one line:
   "status checkpoint: reply with where you stand, do not start new work"
   An unpinged idle agent past the cache window resumes cold and re-reads its whole
   transcript; the ping keeps its next real invocation cheap.
2. Record any finished agent results on the task list. Dispatch nothing.
3. Take the first duration off the remaining chain and ScheduleWakeup it, passing this
   same prompt with that duration removed and the stage number advanced. When the
   remaining chain is empty, schedule nothing further and treat the next firing as final.
```

### Final wakeup prompt template

```
/usage-pause final stage: the 5-hour window reset at <reset_time_local>.
1. Ping every live and idle-but-warm agent with exactly:
   "status checkpoint: reply with where you stand, do not start new work"
2. Record any finished agent results on the task list.
3. Restore every cron in <cancelled_crons_json>: CronCreate each one with its recorded
   schedule and prompt.
4. Hand control back to normal orchestration and resume work from the task list.
```

Fill each `<slot>` at schedule time: `<remaining_stage_durations>` is the tail of `stages_seconds` after the stage being scheduled, and `<cancelled_crons_json>` is the recorded cron list from pause time, carried verbatim through every stage.

## Layout

| File | Role |
|---|---|
| `SKILL.md` | This flow: resolve, weekly guard, stage chain, templates |
| `scripts/resolve_usage_window.py` | The window resolver and stage planner CLI |
| `scripts/test_resolve_usage_window.py` | Behavioral tests for parsing, staging, token reading, extraction, CLI |
| `scripts/usage_pause_constants/resolve_usage_window_constants.py` | Endpoint, credential keys, stage sizing, thresholds, result keys |

## Gotchas

- The stored access token lives about 8 hours and the CLI rewrites it on its own schedule, so a mid-afternoon probe can find it expired even while the CLI itself still works. That is the designed exit-2 path: give a manual time.
