# Advisor Protocol

Shared spawn-once, consult-by-message protocol for a warm advisor. Two skills depend on this: `team-advisor` (binds the advisor for its own consulting session) and `orchestrator` (binds the same advisor and lets its own routed executor subagents consult it too). Executor spawn prompts are a third consumer, via the assembled Advisor block.

**First step of every bind:** detect the host profile (next section).
Walk the model-floor ladder, spawn `session-advisor`, or open the CLI fallback only after the host is known.
On a third-party host, skip straight to **Host profiles → Third-party host**.
On Claude, continue with **Model floor** and the rest of this document.

## Read map

The sections below hold the standing rules; open a reference file at the moment its row names.

| Moment | Open |
|---|---|
| Binding on a Claude host | [`reference/warm-up.md`](reference/warm-up.md) — spawn fields, Fable token, charter |
| Binding from a third-party host | [`reference/third-party-bind.md`](reference/third-party-bind.md) — CLI bind steps, fail-closed rule |
| `ADVISOR_SOL_XHIGH` is set | [`reference/sol-rung.md`](reference/sol-rung.md) — preflight, bind, fallback |
| Composing a consult | [`reference/consult-format.md`](reference/consult-format.md) — packet, new-evidence and report-back rules |
| Assembling an executor spawn prompt | [`reference/advisor-block.md`](reference/advisor-block.md) — the paste parts |
| Advisor drifts, dies, or the task pivots | [`reference/lifecycle.md`](reference/lifecycle.md) — re-spawn and re-bind steps |
| Logging or checking a bind walk | [`reference/spawn-walk-log.md`](reference/spawn-walk-log.md) — record shape, validator |
| Any CLI call to a Claude advisor | [`reference/cli-chain.md`](reference/cli-chain.md) — runner modes, alias table, resume |

## Host profiles

Detect the host profile **before** any model-floor walk. Source of truth for names and detection: `HOST_PROFILE_CLAUDE`, `HOST_PROFILE_THIRD_PARTY`, `ALL_HOST_PROFILES`, and `detect_host_profile(...)` in `$HOME/.claude/_shared/advisor/scripts/config/advisor_scripts_constants/model_tier_run_validator_constants.py` and `tier_model_ids.py`.

Detection order:

1. `ADVISOR_HOST_PROFILE=ThirdParty` or `=Claude` (explicit override; any letter case).
2. `THIRD_PARTY=1` (or `true` / `yes` / `on`) — a third-party (non-Claude) harness.
3. Default: Claude.

### Sol rung — any host

An optional **sol xhigh** rung sits above the Claude ladder on every host, switched by the flag `ADVISOR_SOL_XHIGH=1` (or `true` / `yes` / `on`), set in the environment or by the consuming skill's invocation.
Flag off: the walk starts at the host's Claude ladder, Fable first.
Flag on: run the Codex preflight and bind per [`reference/sol-rung.md`](reference/sol-rung.md); a failed preflight falls back to the Claude ladder.

### Claude host

Use the **Model floor** ladder below (sol when flagged, then Fable → Opus).
Warm-up spawns `subagent_type: session-advisor` via the Agent tool; consults go through `SendMessage` to that warm agent.
Assemble and paste each executor's Advisor block per the **Advisor block** section.

### Third-party host

On a third-party (non-Claude) harness, the shared CLI Claude-chain is the one path to a Claude advisor: bind a **max-tier Claude advisor** through it, per [`reference/third-party-bind.md`](reference/third-party-bind.md).
The bound Claude session is the advisor; this third-party session stays the executor.
Floor **Opus**; walk `candidate_tiers = ["Fable", "Opus"]` with `own_tier = Opus`; the sol rung binds ahead of the chain when open.
**Fail closed:** when every candidate fails, set `selected_tier = null` and a `fallback_reason`, report that the advisor is unreachable, and **stop** — ENDORSE / CORRECTION / PLAN / STOP come only from a bound advisor.
Executors report to the orchestrating session; that session consults the bound advisor and relays the four-signal reply.

## Model floor

**Claude host:** the advisor's model tier must be at or above the highest tier of any consumer that will reach it. Each consuming skill supplies its own consumer set when computing the floor:
- `team-advisor`: the sole consumer is the calling session itself, so the floor is just that session's own tier.
- `orchestrator`: the consumer set is the orchestrating session plus every tier named in its routing table, so the floor is the max of those.

Whatever the consumer set, the floor sits at Opus or above — use the stronger of Opus and the strongest consumer tier.

**Third-party host:** the CLI advisor floor is fixed at **Opus** (walk Fable → Opus only), whatever the session's own tier.

Ladder, strongest first: sol (flag-gated, Codex CLI) → `Fable` → `Opus`.
Advisors bind at Opus or above; `Sonnet` and `Haiku` are executor tiers only.
Tier names are canonical Title Case; the validator accepts any letter case and normalizes to Title Case.
Read the floor tier — the lower bound only — then try binds top-down, stopping at the floor tier.
Each try resolves its candidate tier to the short model alias via the tier-to-alias map in [`reference/cli-chain.md`](reference/cli-chain.md).
The advisor is created at `selected_tier` — the first ladder tier that binds — which may sit above the floor.
When even the floor tier fails on a Claude host, move to the **CLI chain** fallback below.
On a third-party host the CLI chain is already the primary path, so floor failure fails closed per **Host profiles → Third-party host**.

Emit a structured spawn-walk log so the walk can be checked mechanically: [`reference/spawn-walk-log.md`](reference/spawn-walk-log.md).
The validator checks ladder shape only; host policy sits on top.

**Equal-tier pairings.** Bind a same-tier advisor when the goal is an independent second pass.
For irreversible or security-sensitive work, pair a top-tier executor with a top-tier advisor for independent frontier review.
The floor rule holds — the advisor sits at or above the strongest consumer's tier — and an equal-tier bind sits inside that bound.

## Warm-up (once per session)

On a **Claude host**, walk the candidate tiers top-down, spawning `session-advisor` in the background at each candidate's alias with the charter as its prompt — spawn fields and the charter template: [`reference/warm-up.md`](reference/warm-up.md).
A **Fable**-tier try carries the exact token `FABLE-SPAWN-AUTHORIZED` in its prompt — `hooks/blocking/fable_spawn_gate.py` denies a Fable-tier spawn without it.
Stop at the first successful spawn; that try's tier is `selected_tier`, and the warm agent lives at that tier for the rest of the session.
The agent finishes its first turn standing by. `SendMessage` alone resumes it; between consults it waits quietly.

On a **third-party host**, bind per [`reference/third-party-bind.md`](reference/third-party-bind.md) and charter the CLI session with the same charter — the reply contract is the same, and consults travel through the CLI runner.

## Consulting the warm agent

Send a consult at the trigger points `docs/references/advisor-tool.md` **When to call** defines — plan lock-in, believed completion, hard-to-reverse actions, repeated failure or stalled progress, and reconsidered approach.
The paste parts in [`reference/advisor-block.md`](reference/advisor-block.md) restate them for executors.

Each consult carries the sender's identity and assignment, the delta since the last consult, the live decision or blocker, and the paths or excerpts needed to answer well — full packet shape plus the new-evidence and report-back rules: [`reference/consult-format.md`](reference/consult-format.md).
Consult briefs embed the `docs/references/advisor-tool.md` **Brevity cue** line, sized per that section.

Treat the reply as a serious second opinion: a CORRECTION — whether it names a wrong step or a risk worth closing — is something to address before treating the plan or the work as done.
Route a STOP, or an unreachable advisor, upward per [`reference/consult-format.md`](reference/consult-format.md).

## Advisor block — assemble and paste into every executor spawn prompt

Assemble each executor's block from the parts in [`reference/advisor-block.md`](reference/advisor-block.md), in order: one transport preamble picked by host profile, then the shared core, then — for an executor at Sonnet or below — the weak-executor add-on.
Paste the assembled block at the **top** of the spawn prompt, ahead of any other sentence that mentions the advisor.
The assembled block is self-contained — the executor receives this text alone.

## Lifecycle ownership

The session that binds the advisor owns its whole lifecycle — first bind, drift re-spawn or re-bind, and shutdown.
Every other consumer reaches the advisor by message alone.
One shared advisor exists per orchestrated session, owned by the session that bound it.
Drift signals and the per-host re-spawn / re-bind steps: [`reference/lifecycle.md`](reference/lifecycle.md).

## CLI chain

The shared runner is `python "$HOME/.claude/scripts/claude_chain_runner.py" [--routing-mode usage_ranked|ordered_account] -- <claude args...>`.
Modes and failover, the tier-to-alias table, brief piping, and `--resume` session handling: [`reference/cli-chain.md`](reference/cli-chain.md).

**Third-party host:** the primary bind and consult path; the walk order and fail-closed rule live in [`reference/third-party-bind.md`](reference/third-party-bind.md).

**Claude host:** fall back to this runner exactly when one of these holds:
- The Agent-tool spawn errors at every candidate tier down to the floor — the tool itself is unavailable.
- `SendMessage` to the shared advisor errors, or draws no reply within the bound in `ADVISOR_SENDMESSAGE_REPLY_WAIT_SECONDS` (120) in `$HOME/.claude/_shared/advisor/scripts/config/advisor_scripts_constants/model_tier_run_validator_constants.py`, and a re-spawn also fails.
- The running session is itself a subagent barred from spawning further agents.

## State the mechanism

One warm agent, addressed by name, whose transcript accumulates across consults — each consult sends only the delta since the last one.
A consuming skill's own text states this mechanism; a token or cost saving becomes a claim only after a measured comparison against cold spawns.
