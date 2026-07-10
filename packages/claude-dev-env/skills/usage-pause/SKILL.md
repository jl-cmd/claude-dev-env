---
name: usage-pause
description: >-
  Waits out the account's 5-hour usage window in ScheduleWakeup stages that keep
  every agent context warm. Accepts a manual override like '/usage-pause
  10:20pm' or '/usage-pause 74m'. Triggers: '/usage-pause', 'pause until the
  usage window resets', 'wait out the usage limit', 'usage limit pause'.
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
| `weekly_near_cap` | True when the weekly meter is at or past 90 percent |

On exit 2 the script prints `{"error": ...}`. Ask the user for a manual reset time via AskUserQuestion (offer clock-time and duration examples), then rerun with `--override`.

### Probe mechanism

The resolver gets a bearer token from one of two sources and sends `GET https://api.anthropic.com/api/oauth/usage` with `Authorization: Bearer <token>` and `anthropic-beta: oauth-2025-04-20`. This is the same endpoint the interactive `/usage` panel reads. The response carries a `five_hour` bucket and a `seven_day` bucket, each with `utilization` (percent spent) and `resets_at`.

Token sources, in order:

- The Claude Code CLI's OAuth access token in `~/.claude/.credentials.json` (`claudeAiOauth.accessToken`, honored only while its `expiresAt` sits in the future).
- The session ingress token in the file named by the `CLAUDE_SESSION_INGRESS_TOKEN_FILE` environment variable, read when the credential file token is unavailable. Claude Code cloud sessions set this variable and omit the credential file.

Fallbacks, in order: no usable token from either source, a failed request, or a response with no readable `five_hour` reset time all end in exit 2 — the manual-override ask above. The manual path works with no probe at all, so the skill functions even when both token sources are stale.

Why this probe and not the others:

- The interactive `/usage` panel shows the same data but has no scriptable output.
- `claude -p --output-format json` spends usage to answer and its metadata reports per-call token counts, not the account window clock.
- `anthropic-ratelimit-*` response headers cover API-key Messages traffic, not the subscription session window, and reading them also costs a request.
- Refreshing the OAuth token from a script is out of scope: token rotation would desync the refresh token the CLI has on disk and log the CLI out. The resolver only ever reads its token sources.

## Weekly limit guard

When `weekly_near_cap` is true, WARN the user — report `weekly_utilization` and `weekly_resets_at` — and stop. No pause choreography runs around the weekly limit; waiting out a weekly window is its own later build.

## Step 2 — the pause chain

Before the first sleep:

1. List active recurring loops (CronList). Record each one's schedule and prompt, then cancel it (CronDelete). Carry the recorded list inside the wakeup prompts so the state survives every stage.
2. Schedule the first stage with ScheduleWakeup, using the first duration in `stages_seconds` and the stage prompt template below.

The stage plan keeps every stage at or under 58 minutes (3480 seconds, inside the 3600-second clamp) and ends with a roughly 2-minute tail stage so the final firing lands just past the reset. A leftover too short to stand alone folds into the tail.

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
