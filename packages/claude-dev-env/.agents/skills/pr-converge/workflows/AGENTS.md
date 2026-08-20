# pr-converge/workflows

Pacing workflow specification for the `pr-converge` loop.

## Key files

| File | Purpose |
|---|---|
| `schedule-wakeup-loop.md` | Specifies `ScheduleWakeup` call parameters, delays, and stop/convergence conditions for each tick |

## Conventions

- `per-tick.md` (in `../reference/`) references this file for Step 4 (schedule next wakeup). Read it before running Step 4.
- Default delay: `delaySeconds: 360`. Exception: BUGBOT inline-lag branch uses `delaySeconds: 90`.
- On convergence or a hard stop condition, omit the `ScheduleWakeup` call entirely.
- The `reason` field in each `ScheduleWakeup` call names what is being awaited, including the current `phase` and `bugbot_clean_at` SHA when set.
