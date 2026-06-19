# autoconverge

**Trigger:** `/autoconverge`, "autoconverge this PR", "converge this PR in one run", "run the converge workflow", "drive the PR to ready autonomously".

Drives one draft PR to convergence in a single autonomous workflow run. Each round runs Cursor Bugbot, a code-review pass, and a bug-audit in parallel on the same HEAD, deduplicates findings, applies every fix in one commit, re-verifies, clears a Copilot wait-gate, and marks the PR ready on convergence. State lives in the workflow journal; no `ScheduleWakeup` ticks.

## Subdirectories

| Directory | Role |
|---|---|
| `reference/` | Markdown docs the skill and workflow cite: round shape, stop conditions, gotchas, and closing report format. |
| `workflow/` | The `.mjs` convergence workflow, Python report scripts, test files, and the `autoconverge_report_constants/` package. |

## Key files

| File | Role |
|---|---|
| `SKILL.md` | Full entry-point protocol: pre-flight steps, worktree setup, `Workflow` call, budget-aware round boundaries, teardown, and the per-round convergence loop summary. |
| `workflow/converge.mjs` | Main convergence workflow. Runs rounds, gates on Copilot, checks convergence, and marks the PR ready. |
| `workflow/aggregate_runs.py` | Merges every autoconverge journal for a PR into one deduped journal. |
| `workflow/convergence_summary.py` | Builds the convergence-summary agent prompt over the merged findings. |
| `workflow/render_report.py` | Builds the closing HTML report from the merged journal and summary. |
| `reference/convergence.md` | Round shape: the three parallel lenses, deduplication, fix commit, and the ready definition. |
| `reference/stop-conditions.md` | Every way the run ends short of ready. |
| `reference/gotchas.md` | Hard-won failure lessons. |
| `reference/closing-report.md` | Specification for the closing HTML report format. |

## Entry point

Requires the `Workflow` tool. The `SKILL.md` body specifies the exact pre-flight sequence and `Workflow` call.
