# AI rules fleet rollout (one-off, April 2026)

Operator bash scripts kept for **recordkeeping** after the fleet go-live. They are **not**
maintained entry points: hardcoded PR numbers and repo lists are **stale** after merges.

| Script | Purpose (historical) |
|--------|----------------------|
| `merge-and-sync-all.sh` | Mark ready, merge listed bootstrap PRs, then `force_initial_overwrite` sync + status. |
| `propagate-sync-fix.sh` | Copy canonical `sync_ai_rules.py` from this repo into each target clone. |

Run only from a machine with `gh` auth and after editing lists to match reality. Prefer
`docs/ai-rules-sync.md` and the dispatcher workflow for ongoing sync.
