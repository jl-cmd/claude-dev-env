# ScheduleWakeup loop pacing (pr-converge)

Load this document for converge **loop pacing**. The pre-flight in `SKILL.md`
guarantees `ScheduleWakeup` is available before any tick runs. Shared bugbot
/ bugteam / Fix protocol steps stay in the main `SKILL.md`.

## Session behavior

Call `ScheduleWakeup` from this same session so the next tick fires back into **this** transcript with the prior tick's state line and PR context still addressable.

## Calling ScheduleWakeup

At end of tick (unless convergence or another stop condition already
omitted pacing), call `ScheduleWakeup` with:

- `delaySeconds: 270` whenever bugbot was just re-triggered (by the
  bugbot re-trigger in `../reference/per-tick.md`, by Fix protocol's
  mandatory re-trigger, or by BUGTEAM's same-tick re-trigger). Bugbot
  finishes a review in 1–4 minutes, so 270s stays under the 5-minute
  prompt-cache TTL with margin past bugbot's typical upper bound. The
  exception is the BUGBOT inline-lag branch (see below).
- `reason`: one short sentence on what is being awaited, including the
  current `phase` and `bugbot_clean_at` SHA when set.
- `prompt: "/pr-converge"` — re-enters this skill on the next firing.

## BUGBOT inline-lag

See [`../reference/per-tick.md`](../reference/per-tick.md) — the BUGBOT
inline-lag branch (review body says findings, inline API returns zero
matching for `current_head`) uses `delaySeconds: 90` because no
re-trigger fired and only GitHub's inline-comments API needs to catch up.

## Convergence

On convergence: **omit** further `ScheduleWakeup` calls.

## Stop / safety

On hard blockers or user stop: omit `ScheduleWakeup` per main skill **Stop conditions**.
