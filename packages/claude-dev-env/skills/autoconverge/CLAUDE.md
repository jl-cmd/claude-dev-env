# autoconverge

**Trigger:** `/autoconverge`, "autoconverge this PR", "converge this PR in one run", "run the converge workflow", "drive the PR to ready autonomously".

Drives one draft PR to convergence in one autonomous run. On `pacer=workflow`, each round runs a deterministic static sweep first, then a code-review pass, a bug-audit (with its adversarial second pass), and a self-review parity pass in parallel on the same HEAD, deduplicates findings, applies every fix in one commit, and re-verifies; state lives in the workflow journal. On `pacer=portable`, the continuous driver in `_shared/pr-loop/portable-driver.md` runs the shared pr-converge phase machine with the same helpers and `check_convergence.py` ready definition. Once the internal passes are clean, Cursor Bugbot, Copilot, and Codex run as terminal confirmation gates, and the run marks the PR ready on convergence.

## Subdirectories

| Directory | Role |
|---|---|
| `reference/` | Markdown docs the skill and workflow cite: round shape, stop conditions, gotchas, and closing report format. |
| `workflow/` | The `.mjs` convergence workflow, Python report scripts, test files, and the `autoconverge_report_constants/` package. |

## Key files

| File | Role |
|---|---|
| `SKILL.md` | Full entry-point protocol: pacer selection, pre-flight steps, worktree setup, Workflow or portable path, budget-aware boundaries, teardown, and the convergence loop summary. |
| `workflow/converge.mjs` | Main convergence workflow. Runs a static sweep then the internal lenses each round, applies fixes, runs Bugbot, Copilot, and Codex as terminal gates, checks convergence, and marks the PR ready. |
| `workflow/aggregate_runs.py` | Merges every autoconverge journal for a PR into one deduped journal. |
| `workflow/convergence_summary.py` | Builds the convergence-summary agent prompt over the merged findings. |
| `workflow/render_report.py` | Builds the closing HTML report from the merged journal and summary. |
| `reference/convergence.md` | Round shape: the static sweep, the three parallel internal lenses, deduplication, fix commit, the terminal Bugbot, Copilot, and Codex gates, and the ready definition. |
| `reference/copilot-findings.md` | The Copilot gate tiering, per-finding verification, and the `userReview` return contract. |
| `reference/stop-conditions.md` | Every way the run ends short of ready, including the budget stop. |
| `reference/gotchas.md` | Hard-won failure lessons. |
| `reference/closing-report.md` | The closing HTML report: data source, build steps, publishing. |
| `reference/multi-pr.md` | The several-PRs path: per-PR worktrees, the `converge_multi.mjs` launch, per-PR teardown. |
| `reference/self-closing-loop.md` | The deferred-PR generations and the Conventional-Commit title rule. |
| `reference/headless-safety.md` | The agent-prompt headless-safety preamble and the rm auto-allow paths. |

## Entry point

Selects `workflow` or `portable` via `select_converge_pacer.py`. Missing
`Workflow` selects portable and continues — it does not abort. The `grok` arg
forces the portable pacer and routes loop edit, audit, and fix workers through
`resolve_worker_spawn.py` (grok-first, Claude fallback); code-review and the
code-verifier verdict stay on Claude. The `SKILL.md` body specifies the
pre-flight sequence and each pacer's run path.
