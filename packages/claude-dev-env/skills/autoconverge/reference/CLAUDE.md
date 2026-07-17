# reference

Reference documentation for the `autoconverge` skill. The `converge.mjs` workflow and the `SKILL.md` cite these files to define behavior precisely.

## Key files

| File | Role |
|---|---|
| `convergence.md` | Round shape: the static sweep, the three parallel internal lenses (code-review, bug-audit, self-review), deduplication, the fix commit step, the terminal Bugbot, Copilot, and Codex gates, and the definition of a clean convergence. Portable built-in review points at the claude-review skill. |
| `copilot-findings.md` | The Copilot gate tiering, per-finding verification, and the `userReview` return contract. |
| `stop-conditions.md` | Every condition that ends the run short of ready: budget cap, iteration cap, blocker exit, static-sweep stall, Bugbot, Copilot, and Codex bypass. |
| `gotchas.md` | Hard-won lessons from failed runs: PR title validation, conflicting PRs, worktree branch lock, resumed sessions rerooting, and minter issues. |
| `closing-report.md` | The closing HTML convergence report the teardown step builds and publishes: data source, build steps, publishing. |
| `multi-pr.md` | The several-PRs path: per-PR worktrees, the `converge_multi.mjs` launch, per-PR teardown. |
| `self-closing-loop.md` | The deferred-PR generations the orchestrator converges after teardown, and the Conventional-Commit title rule on hardening PRs. |
| `headless-safety.md` | The headless-safety preamble every agent prompt carries, and the rm auto-allow paths. |
