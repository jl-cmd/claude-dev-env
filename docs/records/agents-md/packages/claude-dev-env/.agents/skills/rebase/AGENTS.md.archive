# rebase

Rebase a branch onto its base ref with verification gates that catch logically broken results before pushing.

**Trigger:** `/rebase`, "rebase this branch", "PR has merge conflicts", "rebase onto main", force-push to update remote branch history.

## Purpose

The default failure mode for a rebase is shipping code that compiled but does not run. This skill prevents that by running real import checks, test collection, and symbol scans after every rebase — not just syntax validation.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | The complete skill — four phases (pre-rebase analysis, during rebase, verification gates, push). No companion files. |

## Four phases

| Phase | Key actions |
|---|---|
| 1 — Pre-rebase analysis | Resolve base via `gh pr view`, classify scenario (stacked/squash/long-lived), fetch fresh, scan commit messages for deleted/renamed symbols |
| 2 — During rebase | Verify `--skip` with a diff, audit auto-merged files with `git diff --name-only --diff-filter=M ORIG_HEAD` |
| 3 — Verification gates | `python -m compileall`, `pytest --collect-only -q`, targeted test run, reference scan for removals |
| 4 — Push | Explicit authorization required; `--force-with-lease=<branch>:<sha>` only; verify mergeability after push |

## Conventions

- Force-push requires explicit operator authorization every time — auto mode does not bypass this.
- `--force-with-lease=<branch>:<sha>` only; bare `--force` is refused.
- Never force-push `main`, `master`, `release/*`, `production`, or any multi-author branch.
- Symbol scans prefer Serena (`find_referencing_symbols`) then the Grep tool, then shell grep as a last resort.
- `ORIG_HEAD` is the correct ref for auto-merged file audits mid-rebase; `HEAD@{1}` shifts per step.
