# _shared/advisor

Warm-advisor bind-and-consult protocol shared by `team-advisor`, `orchestrator`, `orchestrator-refresh`, and every executor subagent `orchestrator` routes work to. Changes here affect all of these simultaneously — treat this as a breaking-change surface.

Host profile (Claude vs third-party) is detected first; Claude walks the multi-tier Agent spawn ladder (CLI chain as fallback), a third-party host binds a max-tier Claude advisor through the CLI Claude-chain (fail closed when the chain cannot serve) with a separate executor paste block.

## Key documents

| File | Purpose |
|---|---|
| `advisor-protocol.md` | Host profiles first, model floor, warm-up / CLI bind procedure and charter, consult format and cadence, lifecycle ownership (Agent spawn on Claude / CLI re-bind on a third-party host), host-matched Advisor blocks for executor spawns, and the shared CLI Claude-chain |

## Subdirectory

| Entry | Description |
|---|---|
| `scripts/` | `model_tier_run_validator.py` (spawn-walk log checks), `tier_model_ids.py` (`resolve_cli_model_id` / short CLI/Agent aliases / `detect_host_profile`), and `advisor_scripts_constants` under `scripts/config/` (ladder, short-alias map, host profiles, SendMessage wait bound) |

## Breaking-change rule

A change to host detection, the model-floor rule, the charter template, either host's Advisor block, or lifecycle ownership in `advisor-protocol.md` requires updating every consuming skill (`team-advisor`, `orchestrator`, `orchestrator-refresh`) in the same commit.
