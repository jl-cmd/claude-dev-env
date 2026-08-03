# Advisor Protocol

Shared spawn-once, consult-by-message protocol for a warm advisor. Two skills depend on this: `team-advisor` (binds the advisor for its own consulting session) and `orchestrator` (binds the same advisor and lets its own routed executor subagents consult it too). Executor spawn prompts are a third consumer, via the host-matched Advisor block below.

**First step of every bind:** detect the host profile (next section). Do not walk the model-floor ladder, spawn `session-advisor`, or open the CLI fallback until the host is known. On a third-party host, skip straight to **Host profiles → Third-party host**. On Claude, continue with **Model floor** and the rest of this document.

## Host profiles

Detect the host profile **before** any model-floor walk. Source of truth for names and detection: `HOST_PROFILE_CLAUDE`, `HOST_PROFILE_THIRD_PARTY`, `ALL_HOST_PROFILES`, and `detect_host_profile(...)` in `$HOME/.claude/_shared/advisor/scripts/config/advisor_scripts_constants/model_tier_run_validator_constants.py` and `tier_model_ids.py`.

Detection order:

1. `ADVISOR_HOST_PROFILE=ThirdParty` or `=Claude` (explicit override; any letter case).
2. `THIRD_PARTY=1` (or `true` / `yes` / `on`) — a third-party (non-Claude) harness.
3. Default: Claude.

### Claude host

Use the **Model floor** ladder below (sol when flagged, then Fable → Opus). Warm-up spawns `subagent_type: session-advisor` via the Agent tool; consults go through `SendMessage` to that warm agent. When every candidate down to the floor fails, take the CLI Claude-chain fallback. Paste the **Claude host** Advisor block into every executor spawn prompt.

An optional **sol xhigh** rung sits above Fable, switched by the flag `ADVISOR_SOL_XHIGH=1` (or `true` / `yes` / `on`), set in the environment or by the consuming skill's invocation.
Flag off: the walk starts at Fable.
Flag on: run the Codex preflight first — `python ~/.claude/skills/codex-review/scripts/codex_usage_probe.py` (repo home: `packages/claude-dev-env/skills/codex-review/scripts/`).
Preflight pass — exit 0 with `percent_left` above the gate threshold, or null — bind one Codex CLI session at the sol model with xhigh reasoning effort, chartered with the same standing-reviewer contract (ENDORSE / CORRECTION / PLAN / STOP, reply-only).
Preflight fail — non-zero exit or an exhausted meter — fall back to Fable and continue the normal ladder.

### Third-party host

A third-party (non-Claude) harness cannot spawn a Claude `session-advisor` through the Agent tool. Bind a **max-tier Claude advisor** through the shared CLI Claude-chain. Do **not** treat this third-party session as the advisor.

1. Detect host profile first (this section).
2. Set the advisor floor to **Opus** so the walk is `candidate_tiers = ["Fable", "Opus"]` with `own_tier = Opus`. When `ADVISOR_SOL_XHIGH` and the Codex preflight open the sol rung (see **Claude host**), bind sol xhigh first; the CLI Claude-chain walk below it starts at Fable.
3. **CLI bind (primary path):** for each candidate top-down, pipe a charter file into:

   ```
   python "$HOME/.claude/scripts/claude_chain_runner.py" --routing-mode ordered_account -- -p --model <alias> --effort <effort> --output-format json
   ```

   Use `--model fable --effort high` on Fable; use `--model opus --effort xhigh` on Opus.
   Opus routing follows [`rules/opus5-communication-contract.md`](../../rules/opus5-communication-contract.md).
   The caller picks the Fable effort from task scope; when the caller cannot judge scope well enough to pick, it asks the user through AskUserQuestion before binding, and `high` stays the stated default when no caller choice arrives.
   **Root advisor bind** uses `--routing-mode ordered_account`: the runner walks `~/.claude/claude-chain.json` in **config order** (primary launcher first, secondary next), and fails over to the next entry **only** on a usage-limit signature.
   Authentication, timeout, configuration, and other non-usage process errors stop at once with `terminal_status=advisor_blocked` (exit code 4 on the CLI) — they do **not** fall through to the next launcher.
   General (non-root) chain calls keep the default `--routing-mode usage_ranked`, which probes weekly remaining via `claude_chain_usage` / the usage-pause OAuth probe and ranks highest remaining first.
4. Stop at the first successful bind. Record `{tier, result: "cli"}` and set `selected_tier` to that tier. Persist `session_id` from the JSON events (any event carries it; the runner also surfaces it on `ChainInvocationOutcome.session_id`; reply text is the `type == "result"` event's `.result` field). Run every bind and every later consult with cwd set to the repo root the work is for — Claude sessions are project-scoped by working directory.
5. **Fail closed:** when every candidate fails (chain exhausted, `advisor_blocked`, or model unavailable), set `selected_tier = null` and a `fallback_reason`, report that the advisor is unreachable, and **stop**. Do **not** answer ENDORSE / CORRECTION / PLAN / STOP as this third-party session. Do **not** self-endorse.
6. Paste the **Third-party host** Advisor block into every executor spawn prompt — never the Claude SendMessage block. Executors report to the orchestrating session; that session consults the bound Claude CLI advisor and relays the four-signal reply.

Resolve a third-party session's own model field with `resolve_cli_model_id("ThirdParty")` → `third-party` when a host model alias is required. The **advisor** bind uses Fable/Opus aliases only.

## Model floor

**Claude host:** the advisor's model tier must be at or above the highest tier of any consumer that will reach it. Each consuming skill supplies its own consumer set when computing the floor:
- `team-advisor`: the sole consumer is the calling session itself, so the floor is just that session's own tier.
- `orchestrator`: the consumer set is the orchestrating session plus every tier named in its routing table, so the floor is the max of those.

Whatever the consumer set, the floor sits at Opus or above — use the stronger of Opus and the strongest consumer tier.

**Third-party host:** the CLI advisor floor is fixed at **Opus** (walk Fable → Opus only). The third-party session's own tier is not the advisor floor — see **Host profiles → Third-party host**.

Ladder, strongest first: sol (flag-gated, Codex CLI) → `Fable` → `Opus`.
Advisors bind at Opus or above; `Sonnet` and `Haiku` are executor tiers only.
Tier names are canonical Title Case; the validator accepts any letter case and normalizes to Title Case.
The sol rung binds per **Host profiles → Claude host** (`ADVISOR_SOL_XHIGH` plus the Codex preflight); the Claude walk below it starts at Fable.
Read the floor tier — the lower bound only — then try binds top-down, stopping at the floor tier.
On a Claude host, each walk try sets the Agent tool `model:` field to the short alias for that candidate tier (`resolve_cli_model_id(candidate_tier)` — for example `opus`, not Title Case `Opus`).
On a third-party host, each walk try uses the CLI chain with that alias and the effort flags in **Host profiles → Third-party host**.
The advisor is created at `selected_tier` — the first ladder tier that binds — which may sit above the floor.
When even the floor tier fails on a Claude host, move to the CLI fallback below.
On a third-party host the CLI chain is already the primary path, so floor failure fails closed: report unreachable.

Emit a structured spawn-walk log so the walk can be checked mechanically.
Record shape, log path, the validator command, and its exit codes: [`reference/spawn-walk-log.md`](reference/spawn-walk-log.md).
The validator checks ladder shape only.
Host policy sits on top: a third-party host with `selected_tier=null` after an exhausted Fable→Opus walk fails closed — report unreachable and leave the four signals to a bound advisor.

**Equal-tier pairings.** Bind a same-tier advisor when the goal is an independent second pass.
For irreversible or security-sensitive work, pair a top-tier executor with a top-tier advisor for independent frontier review.
The floor rule holds — the advisor sits at or above the strongest consumer's tier — and an equal-tier bind sits inside that bound.

## Warm-up (once per session)

On a **third-party host**, follow **Host profiles → Third-party host** (CLI Claude-chain bind at Fable then Opus; no Agent-tool `session-advisor` spawn). Charter the CLI session as a standing reviewer that only answers with ENDORSE / CORRECTION / PLAN / STOP — same consult contract as the Agent path, without SendMessage.

On a **Claude host**, the consuming skill's session walks the candidate tiers top-down. For each attempt, spawn with:
- `subagent_type: session-advisor` (see [`agents/session-advisor.md`](../../agents/session-advisor.md) for the full signal contract).
- `model`: the short alias for that attempt's candidate tier via `resolve_cli_model_id` (alias table: [`reference/cli-chain.md`](reference/cli-chain.md)) — for example `opus`, not Title Case `Opus`. The floor is only the lower bound of the walk; the walk still tries stronger tiers first.
- `name`: a name the session and every consumer will use to reach it (e.g. `team-advisor-agent`).
- `run_in_background: true`.
- `prompt`: the charter below. A **Fable**-tier attempt carries the exact token `FABLE-SPAWN-AUTHORIZED` in that prompt — `hooks/blocking/fable_spawn_gate.py` denies every `Agent` or `Task` spawn at `model: fable` whose prompt lacks that token. An attempt at any other tier needs no token.

Stop at the first successful spawn. That attempt's tier is `selected_tier`; the warm agent lives at that tier for the rest of the session. If every candidate down to the floor fails, take the CLI fallback below.

Charter (the spawn prompt): the agent's role — standing reviewer, never edits files or runs commands, only answers via SendMessage — the repo path, and the session's current goal in two or three sentences. On a Fable-tier attempt, include the exact token `FABLE-SPAWN-AUTHORIZED` as plain text in this prompt (substring match; the gate does not verify who placed it). State plainly:
- Every consult carries: who is asking (name and assignment), what changed since their last consult, the live decision or question, and any load-bearing paths or excerpts.
- Reply via SendMessage to whoever sent the consult, by name — never route a reply through the spawning session or "main." Many different consumers may reach this one agent; each reply goes back to its own sender.
- Treat each consult on its own terms, keyed to the sender's stated assignment. Different consumers' consults will interleave in this one transcript — don't blend context across consumers unless a consult explicitly asks for that.
- If a consult re-raises a question already answered, with nothing new attached, reply by restating the prior answer and naming it as a restatement.

The agent finishes its first turn standing by. `SendMessage` alone is what resumes it — no polling loop, no `ScheduleWakeup` keep-alive.

## Consulting the warm agent

Send a consult whenever one of these holds:
- A nontrivial plan is about to be locked in and acted on.
- The consumer believes its assigned work is finished.
- A commit, push, or other hard-to-reverse action is about to run.
- The same failure has come back more than once, or progress has stalled.
- The chosen approach is being reconsidered.

Each consult carries, in order: who you are and your assignment (only needed on a shared advisor with multiple consumers — skip this for a single-consumer team-advisor session), the delta since your last consult (what was done, in order, with real output where it matters — never a full recap), the live decision or blocker, and any paths or excerpts needed to answer well.

Consult briefs embed the parenthesized brevity line addressed to the advisor — `(Advisor: please keep your guidance under 80 words — I need a focused starting point, not a comprehensive plan.)` — and cap requests at roughly 80 percent of the true ceiling.

**New-evidence rule.** Re-raise a question the advisor already answered only when you have something new to attach — the result of attempting the advised step, fresh tool output, or a changed constraint. Without new evidence, act on the standing answer.

**Report-back rule.** After a CORRECTION or PLAN, your next consult on that topic opens with what happened when you followed it.

Treat the reply as a serious second opinion: a CORRECTION — whether it names a wrong step or a risk worth closing — is something to address before treating the plan or the work as done. A STOP, or a consult that finds the advisor unreachable, is reported up rather than retried — team-advisor's sole consumer is the session itself, so it reports to the user; orchestrator's executors report to the orchestrating session, which decides. When the advisor becomes unreachable, report that to the session that owns its lifecycle (see below); that session alone decides whether to respawn (Claude Agent or third-party CLI re-bind). A third-party host that cannot re-bind fails closed and reports to the user — it does not answer the four signals as itself.

## Advisor block — paste the host-matched block into every executor spawn prompt

Each paragraph is self-contained — the executor receives only this text, not the rest of this document, so it carries everything it needs on its own. Paste **exactly one** block, chosen by host profile.

### Claude host (SendMessage to warm advisor)

> A shared session advisor named `<name>` is reachable via SendMessage. Consult it before locking in a nontrivial approach, once you believe your assignment is done, before any hard-to-reverse action, when the same failure repeats or progress has stalled, and when the chosen approach is being reconsidered. Open each consult with who you are and your assignment, then: what you tried, the exact decision or blocker, and relevant paths or excerpts. Re-raise something it already answered only when you have new evidence to attach — the result of trying its advice, fresh output, or a changed constraint; otherwise act on its standing answer. After a CORRECTION or PLAN, your next consult on that topic opens with what happened when you followed it. Its replies open with one of ENDORSE, CORRECTION, PLAN, or STOP — treat CORRECTION and PLAN as actions to take. On STOP, or if the advisor is unreachable, report that back to whoever assigned you and leave lifecycle decisions to the session that owns the advisor.

### Claude host, Sonnet-or-below executor

This variant applies when the executor's own tier is Sonnet or below. Paste it at the **top** of the executor spawn prompt, ahead of any other sentence that mentions the advisor.

> A shared session advisor named `<name>` is reachable via SendMessage. Everything the advisor sees arrives in your consults: the first is a complete, self-contained packet — your assignment, what you tried in order, real output, the live decision, and any load-bearing paths or excerpts — and every later consult carries only the delta since your last one. Send your first consult right after orientation and before your first write, and send a completion consult once your writes and test output exist — that completion consult asks the advisor to hunt for missing requirements, untested behavior, wrong assumptions, unhandled edge cases, evidence gaps, and early completion claims. Consult before locking in a nontrivial approach, once you believe your assignment is done, before reaching for any task-list tool, before any hard-to-reverse action, when the same failure repeats or progress has stalled, and when the chosen approach is being reconsidered — budget two to three consults for the task, at every material fork. Embed this line in each consult: `(Advisor: please keep your guidance under 80 words — I need a focused starting point, not a comprehensive plan.)` Re-raise something it already answered only when you have new evidence to attach — the result of trying its advice, fresh output, or a changed constraint; otherwise act on its standing answer. After a CORRECTION or PLAN, your next consult on that topic opens with what happened when you followed it. Its replies open with one of ENDORSE, CORRECTION, PLAN, or STOP — treat CORRECTION and PLAN as actions to take. On a transient failure, retry once, then carry on with the evidence you have and record that you did; if the advisor is unreachable, report that back to whoever assigned you and leave lifecycle decisions and the four signals to the session that owns the advisor.

### Third-party host (Claude CLI advisor; report to orchestrating session)

> The orchestrating session owns a standing advisor for this run.
> The advisor chain, strongest first: sol xhigh through the Codex CLI when the sol flag and its preflight open that rung, then Claude Fable at effort high, then Claude Opus at effort xhigh through the CLI Claude-chain.
> The orchestrating session is your one path to it: report blockers and hard decisions to the session that assigned you, and it relays the advisor's reply.
> Report before locking in a nontrivial approach, once you believe your assignment is done, before any hard-to-reverse action, when the same failure repeats or progress has stalled, and when the chosen approach is being reconsidered.
> Open each report with who you are and your assignment, then: what you tried, the exact decision or blocker, and relevant paths or excerpts.
> Re-raise something already answered only when you have new evidence to attach — the result of trying prior advice, fresh output, or a changed constraint; otherwise act on the standing answer.
> After a CORRECTION or PLAN, your next report on that topic opens with what happened when you followed it.
> Replies open with one of ENDORSE, CORRECTION, PLAN, or STOP — treat CORRECTION and PLAN as actions to take.
> On STOP, or when the orchestrating session reports the advisor unreachable, stop work and surface that upward; advisor binding and the four signals stay with the orchestrating session and its bound advisor.

## Lifecycle ownership

### Claude host

The session that spawns the shared advisor owns its whole lifecycle — spawn, drift-respawn, and shutdown. Every other consumer (executors, or any other consulting session) only ever sends it messages; none of them spawn, respawn, or shut it down themselves. One shared advisor exists per orchestrated session, owned by the session that spawned it.

**Re-spawn on drift.** If a reply shows the agent working from a stale picture, or the session pivots to an unrelated task, the owning session ends that agent and spawns a fresh one with a new charter, rather than forcing the old context to stretch across two different jobs. A **Fable**-tier re-spawn carries the exact token `FABLE-SPAWN-AUTHORIZED` in that fresh prompt, as a Fable-tier warm-up attempt does.

### Third-party host

The orchestrating session owns the Claude CLI advisor bind for the whole run — first bind, re-bind on drift or lost `session_id`, and fail-closed report when the chain cannot serve.

**Re-bind on drift.** If a reply shows a stale picture, the task pivots, or `--resume` fails after a usage-limit failover (session stores are per binary/account), re-bind through `claude_chain_runner.py` with the charter plus a compact recap of consults so far, capture the new `session_id`, and log a fresh Fable→Opus walk with `result: "cli"` on success. Executors keep reporting to the orchestrating session; they never bind a replacement advisor themselves.

## CLI chain

The shared runner is `python "$HOME/.claude/scripts/claude_chain_runner.py" [--routing-mode usage_ranked|ordered_account] -- <claude args...>`.
Modes and failover, the tier-to-alias table, brief piping, and `--resume` session handling: [`reference/cli-chain.md`](reference/cli-chain.md).

**Third-party host:** this runner is the **primary** advisor bind and consult path.
Root advisor bind and consult use ordered-account mode; when the walk exhausts or returns `advisor_blocked`, fail closed.

**Claude host:** fall back to this runner when any of these holds, rather than on judgment call:
- The Agent-tool spawn errors at every candidate tier down to the floor — the tool itself, not just the top tier, is unavailable.
- `SendMessage` to the shared advisor errors, or draws no reply within the bound in `ADVISOR_SENDMESSAGE_REPLY_WAIT_SECONDS` (120) in `$HOME/.claude/_shared/advisor/scripts/config/advisor_scripts_constants/model_tier_run_validator_constants.py`, and a re-spawn also fails.
- The running session is itself a subagent barred from spawning further agents.

## Mechanism, not a measured saving

One warm agent, addressed by name, whose transcript accumulates across consults — each consult sends only the delta since the last one. Whether this yields a measured token or cost saving over repeated cold spawns has not been directly verified from inside a session; state the mechanism, not a caching claim, in any consuming skill's own text.
