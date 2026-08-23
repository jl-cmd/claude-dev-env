# _shared/advisor

Warm-advisor bind-and-consult protocol shared by `team-advisor`, `orchestrator`, `orchestrator-refresh`, and every executor subagent `orchestrator` routes work to. Changes here affect all of these simultaneously — treat this as a breaking-change surface.

Host profile is resolved from session identity first (Claude, Codex, or neither). Claude walks Fable then Sol in-session (CLI chain as the Fable fallback). Codex walks Sol in-session. A third-party host binds Fable through the CLI Claude-chain (fail closed when Fable and Sol cannot serve) with a separate executor paste block.

## Key documents

| File | Purpose |
|---|---|
| `advisor-protocol.md` | Router with a moment-keyed read map: session identity and host profiles first, model floor, warm-up and consult standing rules, lifecycle ownership, Advisor-block assembly rule, and the shared CLI Claude-chain — each with a stub pointing at its `reference/` detail file |

## Subdirectory

| Entry | Description |
|---|---|
| `scripts/` | `model_tier_run_validator.py` (spawn-walk log checks, including Codex Sol-first and optional Sol), `codex_sol_advisor.py` (read-only Sol bind and resume at shared `ADVISOR_EFFORT`), `tier_model_ids.py` (Claude aliases, Codex model ids, session identity, and host detection), and `advisor_scripts_constants` under `scripts/config/` (ladder, bind tokens, aliases, host profiles, identity tokens, shared effort, and SendMessage wait bound) |
| `reference/` | Progressive-disclosure detail behind protocol stub sections: `identity.md`, `warm-up.md`, `third-party-bind.md`, `sol-rung.md`, `consult-format.md`, `advisor-block.md`, `lifecycle.md`, `cli-chain.md`, and `spawn-walk-log.md` |

## Breaking-change rule

A change to session identity, host detection, the model-floor rule, the charter template, any host's Advisor block, or lifecycle ownership in `advisor-protocol.md` requires updating every consuming skill (`team-advisor`, `orchestrator`, `orchestrator-refresh`) in the same commit.
