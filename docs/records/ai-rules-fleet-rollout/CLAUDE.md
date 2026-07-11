# docs/records/ai-rules-fleet-rollout/

Operator scripts from the AI rules fleet bootstrap. **Not maintained.**

## Purpose

Holds one-off bash scripts that ran during fleet go-live. They are kept for
recordkeeping only. The hardcoded PR numbers and repo lists inside them are stale
after the merges they targeted finished.

For current sync operations, use `docs/ai-rules-sync.md` and the dispatcher workflow.

## Files

| File | Role |
|------|------|
| `README.md` | Explains each script's original purpose and confirms their stale status. |
| `merge-and-sync-all.sh` | Marked ready, merged the listed bootstrap PRs, then triggered a `force_initial_overwrite` sync for each target. |
| `propagate-sync-fix.sh` | Copied the canonical `sync_ai_rules.py` from this repo into each target clone. |
