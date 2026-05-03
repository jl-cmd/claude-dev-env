# ScheduleWakeup loop pacing (pr-converge)

Load this document when **`ScheduleWakeup` is available** in the parent harness session and you use it for converge **loop pacing** (primary /
  orchestrated-teams path). Follow it for **every** instruction below that depends on that choice. Shared bugbot / bugteam / Fix protocol steps
  stay in the main `SKILL.md`.

## Session behavior

Call `ScheduleWakeup` from this same session so the next tick fires back into **this** transcript with the prior tick's state line and PR
  context still addressable.

## Step 4 — `ScheduleWakeup` branch

At end of tick (unless convergence or another stop condition already omitted pacing), call `ScheduleWakeup` with:

- `delaySeconds: 270` whenever bugbot was just re-triggered (whether by Step 3 directly, by the Fix protocol's mandatory re-trigger, or by
  BUGTEAM branch 1's same-tick re-trigger). Bugbot finishes a review in 1–4 minutes, so 270s stays under the 5-minute prompt-cache TTL while
  giving a margin past bugbot's typical upper bound. The single exception is the BUGBOT inline-lag branch in Step 2 of the main skill, which
  uses `delaySeconds: 60` because no re-trigger fired and the only thing being awaited is GitHub's inline-comments API catching up.
- `reason`: one short sentence on what is being awaited, including the current `phase` and `bugbot_clean_at` SHA when set.
- `prompt: "/pr-converge"` — re-enters this skill on the next firing with default loop semantics (no need for the user to type `/loop`). If
  the parent harness requires the `/loop` wrapper for wakeups to execute, `prompt: "/loop /pr-converge"` is equivalent.

## BUGBOT inline-lag (this path only)

When Step 2 BUGBOT branch c routes to API lag and you are on **this** pacing path: complete Step 4 with `ScheduleWakeup` using `delaySeconds:
  60` (lag is short-lived).

## Convergence

On back-to-back clean: **omit** further `ScheduleWakeup` calls. Do not start the AHK auto-typer for loop pacing when this path is the active
  pacer.

## Stop / safety (this path)

On hard blockers or user stop: omit `ScheduleWakeup` per main skill **Stop conditions**. If the session never used AHK for pacing,
  skip AHK shutdown commands in the companion AHK workflow.
