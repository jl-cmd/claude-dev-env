# _shared/advisor

Warm-advisor bind-and-consult protocol shared by `team-advisor`, `orchestrator`, `orchestrator-refresh`, and every executor subagent `orchestrator` routes work to. Changes here affect all of these simultaneously — treat this as a breaking-change surface.

Host profile (Claude vs third-party) is detected first; Claude walks the multi-tier Agent spawn ladder (CLI chain as fallback), a third-party host binds a max-tier Claude advisor through the CLI Claude-chain (fail closed when the chain cannot serve) with a separate executor paste block.

## Key documents

| File | Purpose |
|---|---|
| `advisor-protocol.md` | Router with a moment-keyed read map: host profiles first, model floor, warm-up and consult standing rules, lifecycle ownership, Advisor-block assembly rule, and the shared CLI Claude-chain — each with a stub pointing at its `reference/` detail file |

## Subdirectory

| Entry | Description |
|---|---|
| `scripts/` | `model_tier_run_validator.py` (spawn-walk log checks), `tier_model_ids.py` (`resolve_cli_model_id` / short CLI/Agent aliases / `detect_host_profile`), and `advisor_scripts_constants` under `scripts/config/` (ladder, short-alias map, host profiles, SendMessage wait bound) |
| `reference/` | Progressive-disclosure detail behind protocol stub sections: `warm-up.md` (Claude spawn fields, Fable token, charter template), `third-party-bind.md` (CLI bind steps, fail-closed rule), `sol-rung.md` (flag, Codex preflight, bind and fallback), `consult-format.md` (packet shape, new-evidence and report-back rules, reply handling), `advisor-block.md` (transport preambles, shared core, weak-executor add-on paste parts), `lifecycle.md` (per-host drift re-spawn / re-bind), `cli-chain.md` (runner modes, alias table, brief piping, `--resume` handling), and `spawn-walk-log.md` (record shape, log path, validator command and exit codes) |

## Breaking-change rule

A change to host detection, the model-floor rule, the charter template, either host's Advisor block, or lifecycle ownership in `advisor-protocol.md` requires updating every consuming skill (`team-advisor`, `orchestrator`, `orchestrator-refresh`) in the same commit.
