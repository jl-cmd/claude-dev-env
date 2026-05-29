# ScheduleWakeup loop pacing (pr-converge)

Load this document for converge **loop pacing**. The pre-flight in `SKILL.md`
guarantees `ScheduleWakeup` is available before any tick runs. Shared bugbot
/ bugteam / Fix protocol steps stay in the main `SKILL.md`.

## Calling ScheduleWakeup

At end of every tick — across all phases (BUGBOT, CODE_REVIEW, BUGTEAM,
COPILOT_WAIT) without distinction — call `ScheduleWakeup` unless convergence
or another
stop condition already omitted pacing:

- `delaySeconds: 360` — default wakeup interval. Keeps the loop advancing
  through all phases. Exception: BUGBOT inline-lag branch (see below).
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
