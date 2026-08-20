# pr-converge skill

Drives a draft PR to convergence by driving the internal passes to clean first — a code-review pass and a bugteam audit — then running Cursor Bugbot and Copilot as terminal confirmation gates, applying TDD fixes, posting inline replies, and re-triggering the external reviewers each tick until all are clean on the same HEAD and the PR is mergeable.

**Trigger:** `/pr-converge`, "drive PR to convergence", "loop bugbot and bugteam", "babysit bugbot and bugteam", "until both are clean", "converge this PR".

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Full tick workflow, pre-flight checks, state schema, budget-aware tick boundaries, stop conditions |
| `pr_converge_skill_constants/constants.py` | Runtime and API constants (bot logins, review states, GH API path templates, regex patterns) |

## Subdirectories

| Directory | Role |
|---|---|
| `pr_converge_skill_constants/` | Importable constants module shared by skill scripts |
| `reference/` | Per-tick steps, convergence gates, fix protocol, obstacle runbooks, state schema, stop conditions, examples |
| `scripts/` | Python helpers (bugbot check, convergence check, Copilot review fetcher, fix-reply poster, reflow tool) and their tests |
| `workflows/` | ScheduleWakeup loop pacing specification (`pacer=schedule_wakeup`) |

## Conventions

- Pre-flight selects a pacer via `select_converge_pacer.py`: `schedule_wakeup` or `portable`. Missing `ScheduleWakeup` selects portable — it does not abort the skill.
- On `pacer=schedule_wakeup`, each invocation runs one tick and the next advances via `ScheduleWakeup`. On `pacer=portable`, the session runs ticks continuously (continue or in-session poll) until convergence, a stop condition, or a budget handoff.
- Loop state persists to `$CLAUDE_JOB_DIR/pr-converge-state.json` between ticks.
- Isolation uses `EnterWorktree` when present; otherwise the portable driver git worktree path, then `preflight_worktree.py`.
- All findings and PR reports state verified facts only — no hedging language.
- The GitHub MCP (`pull_request_read`, `pull_request_review_write`) is the primary path for PR inspection; `gh api` is the fallback.
- Three step-scoped agents (`fix_executor`, `thread_sweep`, `copilot_watch`) persist across ticks via the `persistent_agents` map in loop state; each tick resumes them with `SendMessage` and spawns a fresh named agent when a stored id is dead.
- The tick delegates shared mechanics to three sibling sub-skills: `reviewer-gates` (opt-out, Copilot quota, Bugbot trigger), `pr-fix-protocol` (fix sequence + unresolved-thread sweep), and `pr-loop-lifecycle` (run open/close). Target resolution happens inline in `reference/per-tick.md` Steps 1 and 1.5. Audit posting follows the `_shared/pr-loop/post-audit-thread-contract.md` contract, run through `_shared/pr-loop/scripts/post_audit_thread.py`.
