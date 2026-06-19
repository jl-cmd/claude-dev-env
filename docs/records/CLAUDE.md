# docs/records/

One-off operator records kept for reference after their go-live events.

## Purpose

Stores bash scripts and runbooks from specific fleet operations. The files here
document what ran and why; they are **not** maintained entry points. Hardcoded
repo lists, PR numbers, and target sets in these scripts are stale after the
operations they supported finished.

For ongoing sync operations, use `docs/ai-rules-sync.md` and the dispatcher
workflow instead.

## Subdirectories

| Directory | Role |
|-----------|------|
| `ai-rules-fleet-rollout/` | Operator scripts from the AI rules fleet bootstrap. Has a README explaining each script's purpose and its stale status. |
