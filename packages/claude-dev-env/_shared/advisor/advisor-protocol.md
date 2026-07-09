# Advisor Protocol

Shared spawn-once, consult-by-message protocol for a warm advisor agent. Two skills depend on this: `team-advisor` (spawns the advisor for its own consulting session) and `orchestrator` (spawns the same advisor and lets its own routed executor subagents consult it too). Executor spawn prompts are a third consumer, via the copy-paste Advisor block below.

## Model floor

The advisor's model tier must be at or above the highest tier of any consumer that will reach it. Each consuming skill supplies its own consumer set when computing the floor:
- `team-advisor`: the sole consumer is the calling session itself, so the floor is just that session's own tier.
- `orchestrator`: the consumer set is the orchestrating session plus every tier named in its routing table, so the floor is the max of those.

Ladder, strongest first (canonical Title Case names: `Fable`, `Opus`, `Sonnet`, `Haiku`; the validator accepts any letter case and normalizes to Title Case): Fable, Opus, Sonnet, Haiku. Read the floor tier — the lower bound only — then try the warm-agent spawn top-down from Fable, stopping at the floor tier — never spawn below it. Each walk attempt sets `model` to that attempt's candidate tier. The warm agent is created at `selected_tier` (the first tier that actually spawned), which may sit above the floor. If even the floor tier's spawn fails, move to the CLI fallback below rather than spawning below the floor.

Emit a structured spawn-walk log so it can be checked mechanically rather than inferred from a transcript. Record: `own_tier` (the floor tier read at the top of this section), `candidate_tiers` (the ladder slice down to that floor), `attempts` (one `{tier, result}` entry appended as each spawn try happens, `result` one of `spawned` or a failure reason such as `unavailable`), and `selected_tier` (the tier of the first `spawned` entry, or `null` paired with a `fallback_reason` string when none spawned and the CLI fallback took over). Write the log as JSON with those field names to a path the session controls — typically `<job-temp-dir>/model-tier-run.json` (or the OS temp directory when no job directory exists). Check it with:

```
python "$HOME/.claude/_shared/advisor/scripts/model_tier_run_validator.py" <path-to-model-tier-run.json>
```

Exit code `0` means every invariant holds; `1` means a ladder invariant failed; `2` means the path or JSON was unusable. The same checks are available in-process via `validate_model_tier_run(run)`.

## Warm-up (once per session)

The consuming skill's session walks the candidate tiers top-down. For each attempt, spawn with:
- `subagent_type: session-advisor` (see [`agents/session-advisor.md`](../../agents/session-advisor.md) for the full signal contract).
- `model`: that attempt's candidate tier (not the floor — the floor is only the lower bound of the walk).
- `name`: a name the session and every consumer will use to reach it (e.g. `team-advisor-agent`).
- `run_in_background: true`.

Stop at the first successful spawn. That attempt's tier is `selected_tier`; the warm agent lives at that tier for the rest of the session. If every candidate down to the floor fails, take the CLI fallback below.

Charter (the spawn prompt): the agent's role — standing reviewer, never edits files or runs commands, only answers via SendMessage — the repo path, and the session's current goal in two or three sentences. State plainly:
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

**New-evidence rule.** Re-raise a question the advisor already answered only when you have something new to attach — the result of attempting the advised step, fresh tool output, or a changed constraint. Without new evidence, act on the standing answer.

**Report-back rule.** After a CORRECTION or PLAN, your next consult on that topic opens with what happened when you followed it.

Treat the reply as a serious second opinion: a CORRECTION — whether it names a wrong step or a risk worth closing — is something to address before treating the plan or the work as done. A STOP, or a consult that finds the advisor unreachable, is reported up rather than retried — team-advisor's sole consumer is the session itself, so it reports to the user; orchestrator's executors report to the orchestrating session, which decides. When the advisor becomes unreachable, report that to the session that owns its lifecycle (see below); that session alone decides whether to respawn.

## Advisor block — copy verbatim into every executor spawn prompt

This paragraph is self-contained — the executor receives only this text, not the rest of this document, so it carries everything it needs on its own:

> A shared session advisor named `<name>` is reachable via SendMessage. Consult it before locking in a nontrivial approach, once you believe your assignment is done, before any hard-to-reverse action, and when the same failure repeats. Open each consult with who you are and your assignment, then: what you tried, the exact decision or blocker, and relevant paths or excerpts. Re-raise something it already answered only when you have new evidence to attach — the result of trying its advice, fresh output, or a changed constraint; otherwise act on its standing answer. After a CORRECTION or PLAN, your next consult on that topic opens with what happened when you followed it. Its replies open with one of ENDORSE, CORRECTION, PLAN, or STOP — treat CORRECTION and PLAN as actions to take. On STOP, or if the advisor is unreachable, report that back to whoever assigned you and leave lifecycle decisions to the session that owns the advisor.

## Lifecycle ownership

The session that spawns the shared advisor owns its whole lifecycle — spawn, drift-respawn, and shutdown. Every other consumer (executors, or any other consulting session) only ever sends it messages; none of them spawn, respawn, or shut it down themselves. One shared advisor exists per orchestrated session, owned by the session that spawned it.

**Re-spawn on drift.** If a reply shows the agent working from a stale picture, or the session pivots to an unrelated task, the owning session ends that agent and spawns a fresh one with a new charter, rather than forcing the old context to stretch across two different jobs.

## Fallback: the CLI chain

Fall back to the CLI when any of these holds, rather than on judgment call:
- The Agent-tool spawn errors at every candidate tier down to the floor — the tool itself, not just the top tier, is unavailable.
- `SendMessage` to the shared advisor errors, or draws no reply within **120 seconds** (`ADVISOR_SENDMESSAGE_REPLY_WAIT_SECONDS` in `$HOME/.claude/_shared/advisor/scripts/config/advisor_scripts_constants/model_tier_run_validator_constants.py`), and a re-spawn also fails.
- The running session is itself a subagent barred from spawning further agents.

Map the resolved floor tier to its CLI / Agent model alias before the first call — the CLI's `--model` flag and the Agent tool's `model:` field take the short aliases below, not free-form ladder prose. Source of truth: `ALL_CLI_MODEL_ID_BY_TIER` and `resolve_cli_model_id(tier)` in the same constants package / `tier_model_ids.py` helper:

| Ladder tier (Title Case) | CLI / Agent `model` alias |
|---|---|
| Fable | `fable` |
| Opus | `opus` |
| Sonnet | `sonnet` |
| Haiku | `haiku` |

Resolve in code with `python -c "from tier_model_ids import resolve_cli_model_id; print(resolve_cli_model_id('Opus'))"` from `$HOME/.claude/_shared/advisor/scripts/` (any letter case accepted; unknown tiers raise `ValueError`). Use `python "$HOME/.claude/scripts/claude_chain_runner.py" -- -p --model <model alias> --output-format json` in place of the Agent-tool spawn. The chain runner walks the fallback chain configured at `~/.claude/claude-chain.json` (typically `claude` then `claude-ev`), so a usage-limited primary account still gets served. Write the charter or the consult brief to a temporary file under the job's own temporary directory (or the OS temp directory when no job directory exists) and pipe it in, rather than passing either as an inline argument, and drop that file once the consult completes.

Read the `session_id` out of the first call's JSON response and pass it to `-p --resume <session_id> --output-format json` on every later consult — `-p` stays on the resume call too, since it is still a non-interactive invocation. A usage-limit failover to the next binary in the chain does not carry the `session_id` forward: a session store belongs to the binary and account that minted it, so a `--resume` against the new binary can fail. Treat that failure as starting over, not as an error to retry — resend the charter plus a compact recap of the consults since the last one, capture the new `session_id` the fresh call returns, and continue the fallback path from there.

## Mechanism, not a measured saving

One warm agent, addressed by name, whose transcript accumulates across consults — each consult sends only the delta since the last one. Whether this yields a measured token or cost saving over repeated cold spawns has not been directly verified from inside a session; state the mechanism, not a caching claim, in any consuming skill's own text.
