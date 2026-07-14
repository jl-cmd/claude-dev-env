# autoconverge

**Trigger:** `/autoconverge`, "autoconverge this PR", "converge this PR in one run", "run the converge workflow", "drive the PR to ready autonomously".

Drives one draft PR to convergence in a single autonomous workflow run. Each round runs a deterministic static sweep first, then a code-review pass, a bug-audit (with its adversarial second pass), and a self-review parity pass in parallel on the same HEAD, deduplicates findings, applies every fix in one commit, and re-verifies. Once the internal lenses are clean, Cursor Bugbot, Copilot, and Codex run as terminal confirmation gates, and the run marks the PR ready on convergence. State lives in the workflow journal; no `ScheduleWakeup` ticks.

## Subdirectories

| Directory | Role |
|---|---|
| `reference/` | Markdown docs the skill and workflow cite: round shape, stop conditions, gotchas, and closing report format. |
| `workflow/` | The `.mjs` convergence workflow, Python report scripts, test files, and the `autoconverge_report_constants/` package. |

## Key files

| File | Role |
|---|---|
| `SKILL.md` | Full entry-point protocol: pre-flight steps, worktree setup, `Workflow` call, budget-aware round boundaries, teardown, and the per-round convergence loop summary. |
| `workflow/converge.mjs` | Main convergence workflow. Runs a static sweep then the internal lenses each round, applies fixes, runs Bugbot, Copilot, and Codex as terminal gates, checks convergence, and marks the PR ready. |
| `workflow/aggregate_runs.py` | Merges every autoconverge journal for a PR into one deduped journal. |
| `workflow/convergence_summary.py` | Builds the convergence-summary agent prompt over the merged findings. |
| `workflow/render_report.py` | Builds the closing HTML report from the merged journal and summary. |
| `reference/convergence.md` | Round shape: the static sweep, the three parallel internal lenses, deduplication, fix commit, the terminal Bugbot, Copilot, and Codex gates, and the ready definition. |
| `reference/stop-conditions.md` | Every way the run ends short of ready, including the budget stop. |
| `reference/gotchas.md` | Hard-won failure lessons. |
| `reference/closing-report.md` | The closing HTML report: data source, build steps, publishing. |
| `reference/multi-pr.md` | The several-PRs path: per-PR worktrees, the `converge_multi.mjs` launch, per-PR teardown. |
| `reference/self-closing-loop.md` | The deferred-PR generations and the Conventional-Commit title rule. |
| `reference/headless-safety.md` | The agent-prompt headless-safety preamble and the rm auto-allow paths. |

## Entry point

Requires the `Workflow` tool. The `SKILL.md` body specifies the exact pre-flight sequence and `Workflow` call.
