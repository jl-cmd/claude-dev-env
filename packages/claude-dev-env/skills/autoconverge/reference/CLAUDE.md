# reference

Reference documentation for the `autoconverge` skill. The `converge.mjs` workflow and the `SKILL.md` cite these files to define behavior precisely.

## Key files

| File | Role |
|---|---|
| `convergence.md` | Round shape: the static sweep, the three parallel internal lenses (code-review, bug-audit, self-review), deduplication, the fix commit step, the terminal Bugbot and Copilot gates, and the definition of a clean convergence. |
| `stop-conditions.md` | Every condition that ends the run short of ready: budget cap, iteration cap, blocker exit, static-sweep stall, Bugbot and Copilot bypass. |
| `gotchas.md` | Hard-won lessons from failed runs: PR title validation, conflicting PRs, worktree branch lock, resumed sessions rerooting, and minter issues. |
| `closing-report.md` | Specification for the closing HTML convergence report the teardown step builds and publishes. |
