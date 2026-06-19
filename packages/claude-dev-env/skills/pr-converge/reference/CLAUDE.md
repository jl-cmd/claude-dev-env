# pr-converge/reference

Reference documents for the `pr-converge` skill. These files define the per-tick step sequence, convergence gates, fix protocol, stop conditions, state schema, multi-PR orchestration, and examples.

## Key files

| File | Purpose |
|---|---|
| `per-tick.md` | Step-by-step procedure for one tick (resolve HEAD, run BUGBOT, CODE_REVIEW, BUGTEAM, COPILOT_WAIT phases, schedule next wakeup) |
| `convergence-gates.md` | Six gates that must all pass before the PR is marked ready for review |
| `fix-protocol.md` | How to apply fixes: TDD first, one commit per fix round, reply to each finding inline |
| `ground-rules.md` | Non-negotiable constraints for the convergence loop |
| `stop-conditions.md` | Conditions that end the loop without convergence (cap reached, stuck, user stop) |
| `state-schema.md` | Fields in `pr-converge-state.json` and their meanings |
| `multi-pr-orchestration.md` | How to run the loop across multiple PRs in parallel |
| `examples.md` | Worked examples of tick sequences |

## Subdirectories

| Directory | Role |
|---|---|
| `obstacles/` | Per-obstacle runbooks for known failure modes in the convergence loop |

## Conventions

- `per-tick.md` is the primary reference loaded during each tick. The pacing workflow lives in `../workflows/schedule-wakeup-loop.md`.
- Every gate in `convergence-gates.md` must produce evidence before the next gate runs.
