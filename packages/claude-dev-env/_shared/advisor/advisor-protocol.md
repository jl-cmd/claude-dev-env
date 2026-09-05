# Advisor Protocol

Shared spawn-once, consult-by-message protocol for a warm advisor.
`team-advisor` binds the advisor for its own consulting session.
Executor spawn prompts that skill issues consume the assembled Advisor
block.

**First step of every bind:** name the session identity and resolve the host profile (next section).
Walk the model-floor ladder, spawn the in-session advisor, or open the CLI fallback only after the host is known.
On a Codex host, skip straight to **Host profiles → Codex host**.
On a third-party host, skip straight to **Host profiles → Third-party host**.
On Claude, continue with **Model floor** and the rest of this document.

## Read map

The sections below hold the standing rules; open a reference file at the moment its row names.

| Moment | Open |
|---|---|
| Naming the session identity | [`reference/identity.md`](reference/identity.md) — Claude, Codex, or neither |
| Binding on a Claude host | [`reference/warm-up.md`](reference/warm-up.md) — spawn fields, Fable token, charter |
| Binding on a Codex host | [`reference/identity.md`](reference/identity.md) — in-session Astra spawn |
| Binding from a third-party host | [`reference/third-party-bind.md`](reference/third-party-bind.md) — CLI bind steps, fail-closed rule |
| Fable is out of usage | [`reference/astra-rung.md`](reference/astra-rung.md) — Astra fallback at shared effort |
| Composing a consult | [`reference/consult-format.md`](reference/consult-format.md) — packet, new-evidence and report-back rules |
| Assembling an executor spawn prompt | [`reference/advisor-block.md`](reference/advisor-block.md) — the paste parts |
| Advisor drifts, dies, or the task pivots | [`reference/lifecycle.md`](reference/lifecycle.md) — re-spawn and re-bind steps |
| Logging or checking a bind walk | [`reference/spawn-walk-log.md`](reference/spawn-walk-log.md) — record shape, validator |
| Any CLI call to a Claude advisor | [`reference/cli-chain.md`](reference/cli-chain.md) — runner modes, alias table, resume |

## Host profiles

Name the session identity **before** any model-floor walk. Source of truth for names and detection: `HOST_PROFILE_CLAUDE`, `HOST_PROFILE_CODEX`, `HOST_PROFILE_THIRD_PARTY`, `ALL_HOST_PROFILES`, `resolve_session_identity(...)`, and `detect_host_profile(...)` in `$HOME/.claude/_shared/advisor/scripts/config/advisor_scripts_constants/model_tier_run_validator_constants.py` and `tier_model_ids.py`.
Identity tokens and bind paths: [`reference/identity.md`](reference/identity.md).

Session identity:

1. Call `resolve_session_identity` with the session's named identity.
2. A `codex` token selects Codex. A `claude` token selects Claude. Any other identity selects ThirdParty.
3. When both tokens appear, Codex wins.

Mechanical override for scripts:

1. `ADVISOR_HOST_PROFILE=ThirdParty` or `=Claude` or `=Codex` (explicit override; any letter case).
2. `THIRD_PARTY=1` (or `true` / `yes` / `on`) — a third-party (non-Claude) harness.
3. Default: Claude.

### Shared effort — any host

Fable and Astra both read `ADVISOR_EFFORT` (`low`, `medium`, `high`, `xhigh`, `max`). The default is `low`.
Pass `--effort <level>` on the Astra helper to set effort for that Astra run.
Pass `--effort <level>` on the Claude CLI bind for Fable. An unset or unrecognized value uses `low`.

### Astra rung

On Claude and ThirdParty: when Fable is out of usage, bind Astra through the Codex helper.
Open that attempt with `ADVISOR_ASTRA=1` (or `true` / `yes` / `on`) in the environment, or pass `--enable-astra` on the helper invocation.
Flag off both ways: fail closed when Fable did not bind.
Flag on: run the Codex preflight and bind per [`reference/astra-rung.md`](reference/astra-rung.md); a failed preflight fails closed when Fable did not bind.

On Codex: Astra is the in-session default. The `ADVISOR_ASTRA` flag is not required. Fail closed when that spawn does not bind.

### Claude host

Use the **Model floor** ladder below (Fable first, then Astra when Fable is out of usage).
Warm-up spawns `subagent_type: session-advisor` via the Agent tool for Fable; consults go through `SendMessage` to that warm agent. Astra uses the Codex helper.
Assemble and paste each executor's Advisor block per the **Advisor block** section.

### Codex host

Spawn a native in-session Astra subagent at `resolve_codex_model_id("Astra")`.
Walk `candidate_tiers = ["Astra"]`. Record `{tier: "Astra", result: "spawned"}` on success.
**Fail closed:** when Astra does not bind, set `selected_tier = null` and a `fallback_reason`, report that the advisor is unreachable, and **stop**.
Do not walk Fable on a Codex host. Consults stay in-session with that Astra subagent.
Assemble and paste each executor's Advisor block per the **Advisor block** section.

### Third-party host

On a third-party (non-Claude, non-Codex) harness, the shared CLI Claude-chain is the one path to a Claude advisor: bind Fable through it, per [`reference/third-party-bind.md`](reference/third-party-bind.md).
The bound Claude session is the advisor; this third-party session stays the executor.
Walk `candidate_tiers = ["Fable"]`. When Fable is out of usage, the Astra rung binds after Fable (`candidate_tiers = ["Fable", "Astra"]`).
**Cursor Astra first shot:** when the walk reaches Astra (or the user asks for Astra), bind through `codex_astra_advisor.py --bind --enable-astra` on the first tool call (see the GOTCHA in [`reference/third-party-bind.md`](reference/third-party-bind.md)) — not the Agent tool, and not a probe-path hunt.
**Fail closed:** when every candidate fails, set `selected_tier = null` and a `fallback_reason`, report that the advisor is unreachable, and **stop** — ENDORSE / CORRECTION / PLAN / STOP come only from a bound advisor.
Executors report to the orchestrating session; that session consults the bound advisor and relays the four-signal reply.

## Model floor

On Claude and ThirdParty the advisor ladder is `Fable` first, then Astra (flag-gated, Codex CLI) when Fable is out of usage.
On Codex the walk is Astra only, in-session.
Opus is not an advisor candidate. `Sonnet` and `Haiku` are executor tiers only.
Consumer `own_tier` is recorded on the spawn-walk log; it does not add Opus to the advisor walk.
Tier names are canonical Title Case; the validator accepts any letter case and normalizes to Title Case.
Try binds top-down. Fable resolves to the short model alias in [`reference/cli-chain.md`](reference/cli-chain.md); Astra resolves through `resolve_codex_model_id("Astra")` to `gpt-6-astra`.
The advisor is created at `selected_tier` — the first ladder tier that binds.
When Fable fails on a Claude host, try Astra if the flag is on, else fail closed. The CLI chain is the Fable bind path on a third-party host and the Claude-host fallback for Fable; it does not bind Opus as advisor.
On a Codex host a failed Astra spawn fails closed per **Host profiles → Codex host**.
On a third-party host the CLI chain is already the primary path, so a failed Fable (and Astra, when enabled) walk fails closed per **Host profiles → Third-party host**.

Emit a structured spawn-walk log so the walk can be checked mechanically: [`reference/spawn-walk-log.md`](reference/spawn-walk-log.md).
The validator checks ladder shape only; host policy sits on top.

**Equal-tier pairings.** Bind Fable for an independent second pass on irreversible or security-sensitive work. The advisor is Fable or Astra.

## Warm-up (once per session)

On a **Claude host**, spawn `session-advisor` at the Fable alias with the charter as its prompt. When Fable is out of usage and the Astra rung is open, bind Astra through the Codex helper instead.
A **Fable**-tier try carries the exact token `FABLE-SPAWN-AUTHORIZED` in its prompt — `hooks/blocking/fable_spawn_gate.py` denies a Fable-tier spawn without it.
Full spawn fields and the charter template: [`reference/warm-up.md`](reference/warm-up.md).

On a **Codex host**, spawn a native in-session Astra subagent with the same charter. Bind fields: [`reference/identity.md`](reference/identity.md) and [`reference/warm-up.md`](reference/warm-up.md).

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

The session that binds the advisor owns its whole lifecycle — first bind, drift re-spawn or re-bind, and shutdown; every other consumer reaches the advisor by message alone.
Drift signals and the per-host re-spawn / re-bind steps: [`reference/lifecycle.md`](reference/lifecycle.md).

## CLI chain

The shared runner is `python "$HOME/.claude/scripts/claude_chain_runner.py" [--routing-mode usage_ranked|ordered_account] -- <claude args...>`.
Modes and failover, the tier-to-alias table, brief piping, and `--resume` session handling: [`reference/cli-chain.md`](reference/cli-chain.md).

**Third-party host:** the primary bind and consult path; the walk order and fail-closed rule live in [`reference/third-party-bind.md`](reference/third-party-bind.md).

**Codex host:** do not use this runner as the primary path. Astra binds in-session.

**Claude host:** fall back to this runner exactly when one of these holds:
- The Agent-tool spawn errors at every candidate tier down to the floor — the tool itself is unavailable.
- `SendMessage` to the shared advisor errors, or draws no reply within the bound in `ADVISOR_SENDMESSAGE_REPLY_WAIT_SECONDS` (120) in `$HOME/.claude/_shared/advisor/scripts/config/advisor_scripts_constants/model_tier_run_validator_constants.py`, and a re-spawn also fails.
- The running session is itself a subagent barred from spawning further agents.

## State the mechanism

One warm agent, addressed by name, whose transcript accumulates across consults — each consult sends only the delta since the last one.
A consuming skill's own text states this mechanism; a token or cost saving becomes a claim only after a measured comparison against cold spawns.
