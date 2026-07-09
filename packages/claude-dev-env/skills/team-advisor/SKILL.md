---
name: team-advisor
description: >-
  Spawns one background agent at the highest model tier available to the
  session (Fable, then Opus, then Sonnet, then Haiku — never below the
  calling session's own tier) and keeps it warm for the rest of the session.
  Whenever the session needs a second opinion — before locking in a
  nontrivial plan, once it believes the work is done, before a commit or
  other hard-to-reverse action runs, when the same failure repeats, or when
  reconsidering the chosen approach — it sends the warm agent a short brief
  of what changed and what is in question, and relays the reply. Falls back
  to `claude -p` through the repo's claude/claude-ev
  fallback chain when a background agent cannot be spawned or resumed.
  Triggers: '/team-advisor', 'keep an advisor warm', 'warm consult agent',
  'spawn a standing reviewer', 'consult a warm agent'.
---

# Team Advisor

## Principle

One warm, addressable agent beats a fresh spawn on every question: a fresh
spawn starts cold and has to be told everything again, while a warm agent's
transcript already carries the earlier consultations. This skill spawns
that agent once, at the strongest model tier the session can reach, and
sends it a short brief each time a decision is worth a second opinion — cheap
enough to call before committing to a plan, at completion, when stuck, or
when reconsidering the approach.

## Model tier

The ladder, strongest first: **Fable, Opus, Sonnet, Haiku**.

1. Read your own tier from your system context (the line stating which
   model powers you). That tier is the floor — never spawn or fall back to
   anything weaker than it.
2. Build the candidate list: every ladder tier from Fable down through your
   own tier, inclusive. A session running Opus tries `[Fable, Opus]`; a
   session running Sonnet tries `[Fable, Opus, Sonnet]`.
3. Try the warm-agent spawn (see below) at the first candidate. If the
   spawn errors or the harness reports that tier is unavailable, retry at
   the next candidate. Stop at your own tier — if that try also fails,
   move to the CLI fallback below; do not spawn at any tier below your own.

## Warm-up (once per session)

Before the first consult, spawn one named background agent:

- `subagent_type: session-advisor` (zero tools, ENDORSE/CORRECTION/PLAN/STOP
  contract — a plain PLAN/CORRECTION/STOP signal set has no clean way to say
  "this holds, nothing to flag," which two of the triggers below need; a
  named risk is never folded into that clean pass — it routes through
  CORRECTION instead).
- `model`: the resolved tier from above.
- `name`: `team-advisor-agent`. A fixed name lets the rest of the session
  reach it by name and stops a second `/team-advisor` invocation from
  spawning a duplicate — check whether `team-advisor-agent` is already
  warm before spawning again.
- `run_in_background: true`.

The spawn prompt is a standing charter, not a task: the agent's role
(reviewing consultant for this session — it never edits files or runs
commands, it only answers), the repo path, and the session's current goal
in two or three sentences. Tell it every consult that follows will carry
what changed since the last one, the live question, and any load-bearing
file paths or excerpts — and that its replies should stay short and
concrete. The agent finishes its first turn standing by; nothing further is
needed to keep it warm. `SendMessage` alone is what resumes it — no
polling loop, no `ScheduleWakeup` keep-alive.

## Consulting the warm agent

Send a consult whenever one of these holds:

- A nontrivial plan is about to be locked in and acted on.
- The session believes the assigned work is finished.
- A commit, push, or other hard-to-reverse action is about to run.
- The same failure has come back more than once, or progress has stalled.
- The chosen approach is being reconsidered.

Each consult is a `SendMessage` to `team-advisor-agent` carrying three
things, in order: the delta since the last consult (what was done, in
order, with real command output where it matters — not a re-summary of
everything so far), the live decision or blocker, and any file paths or
short excerpts the agent needs to answer well. Sending deltas, never full
recaps, keeps the warm agent's context from growing without bound.

Treat the reply as a serious second opinion, not a rubber stamp: a
CORRECTION — whether it names a wrong step or a risk worth closing — is
something to address before treating the plan or the work as done, not a
footnote to note and move past. When a step taken on its advice fails in
practice, or a fact already verified contradicts what it assumed, say so
back to it rather than silently overriding either side.

**Re-spawn on drift.** If a reply shows the agent working from a stale
picture, or the session pivots to an unrelated task, end that agent and
spawn a fresh one with a new charter rather than forcing the old context to
stretch across two different jobs.

## Fallback: the CLI chain

Fall back to the CLI when any of these holds, rather than on judgment call:

- The Agent-tool spawn errors at every candidate tier down to your own —
  the tool itself, not just the top tier, is unavailable.
- `SendMessage` to `team-advisor-agent` errors, or draws no reply within a
  bounded wait, and a re-spawn also fails.
- The running session is itself a subagent barred from spawning further
  agents.

Map the resolved ladder tier to its exact current model ID before the first
call — the CLI's `--model` flag takes a real model identifier, not the
ladder's tier name. Use `python "$HOME/.claude/scripts/claude_chain_runner.py"
-- -p --model <model ID> --output-format json` in place of the Agent-tool
spawn. The chain runner walks the fallback chain configured at
`~/.claude/claude-chain.json` (typically `claude` then `claude-ev`), so a
usage-limited primary account still gets served. Write the charter or the
consult brief to a temporary file under the job's own temporary directory
(or the OS temp directory when no job directory exists) and pipe it in,
rather than passing either as an inline argument — the same shape used
elsewhere in this repo for multi-line prompt content — and drop that file
once the consult completes.

Read the `session_id` out of the first call's JSON response and pass it to
`-p --resume <session_id> --output-format json` on every later consult —
`-p` stays on the resume call too, since it is still a non-interactive
invocation. A usage-limit failover to the next binary in the chain does not
carry the `session_id` forward: a session store belongs to the binary and
account that minted it, so a `--resume` against the new binary can fail.
Treat that failure as starting over, not as an error to retry — resend the
charter plus a compact recap of the consults since the last one, capture
the new `session_id` the fresh call returns, and continue the fallback path
from there.

## Constraints

- One `team-advisor-agent` per session. Reuse it; do not spawn a second one
  while the first is still warm and on-topic.
- Never spawn the warm agent, or its CLI fallback, at a tier below the
  calling session's own tier. If a per-call model override goes unhonored
  and the agent inherits the caller's own tier instead, the floor still
  holds — that outcome needs no separate fallback trigger.
- The warm agent (or its CLI equivalent) only answers. It never edits a
  file, never runs a build or test, and never posts anything on the
  session's behalf.

## File Index

| File | Purpose |
|---|---|
| `SKILL.md` | Model-tier choice, warm-agent spawn and consult protocol, drift handling, and the CLI fallback. |

## Folder Map

- `SKILL.md` — complete team-advisor workflow instructions.
