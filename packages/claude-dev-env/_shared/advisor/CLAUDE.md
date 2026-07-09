# _shared/advisor

Warm-advisor spawn-and-consult protocol shared by `team-advisor` and `orchestrator`, and by every executor subagent `orchestrator` routes work to. Changes here affect all of these simultaneously — treat this as a breaking-change surface.

## Key documents

| File | Purpose |
|---|---|
| `advisor-protocol.md` | Model floor, warm-up spawn procedure and charter, consult format and cadence, lifecycle ownership, drift-respawn, the copy-paste Advisor block for executor spawns, and the CLI fallback chain |

## Subdirectory

| Entry | Description |
|---|---|
| `scripts/` | `model_tier_run_validator.py` (spawn-walk log checks), `tier_model_ids.py` (`resolve_cli_model_id` / short CLI/Agent aliases), and `advisor_scripts_constants` under `scripts/config/` (ladder, short-alias map, SendMessage wait bound) |

## Breaking-change rule

A change to the model-floor rule, the charter template, or the Advisor block in `advisor-protocol.md` requires updating every consuming skill (`team-advisor`, `orchestrator`) in the same commit.
