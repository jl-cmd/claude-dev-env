---
name: advisor
description: >-
  Turns the session into a lean executor-orchestrator that runs a task end to
  end and consults a tool-less advisor agent (code-advisor) when it hits a
  decision it cannot reasonably solve. The advisor returns one of three
  signals — a plan, a correction, or a stop — and never runs tools or writes
  user-facing text. Caps advisor consultations per task (default 5), reuses
  warm agents before spawning new ones, and re-asserts the discipline every
  20 minutes through the /advisor-refresh loop. Applies Anthropic's advisor
  strategy. Triggers: '/advisor', 'advisor strategy', 'run with an advisor',
  'executor-advisor mode'.
---

# Advisor Strategy

## Principle

A cost-effective executor runs the primary work — it calls tools, reads
results, and iterates — while a stronger model advises only at the hard
decisions. Source: Anthropic's advisor strategy,
https://claude.com/blog/the-advisor-strategy.

Under this skill the session is the executor-orchestrator. It drives the task
from start to finish and reaches for the advisor only when it hits a decision
it cannot reasonably resolve on its own. The advisor is the `code-advisor`
agent: it holds zero tools, sees only the consultation message, and replies
with one of three signals. The executor decides when to consult, and
consultations are capped (default 5 per task) — the same guard the API's
`max_uses` gives a tool.

## Gotchas

- **Double invocation duplicates the reminder loop.** A second `/advisor` in
  the same session schedules a second refresh loop. Check whether the loop is
  already running before you schedule one (see the invocation guard in
  Process step 1).
- **The advisor gets no tools and writes no user-facing text.** Its reply
  goes to the executor only. Handing it tools or asking it for output the user
  reads breaks the pairing.
- **Resuming an unnamed background agent needs its agentId.** A background
  spawn returns an `agentId` (format `a...-...`); keep it so `SendMessage` can
  reach that agent later. A named agent is reachable by name.
- **Consultations past the cap signal a scoping problem.** When five
  consultations do not clear the blocker, the task needs re-scoping or a
  hand-off to the user — not a sixth round of advice.
- **A `ScheduleWakeup` delay above 300 seconds costs one prompt-cache miss.**
  1200 seconds (20 minutes) is chosen for that reason: one miss per refresh,
  a deliberate trade for the discipline the loop enforces.
- **No lever compacts or clears a subagent's context.** The tool inventory
  carries no subagent compaction or context-clear tool. Harness-side
  summarization of a long subagent conversation runs on its own and answers to
  no caller. So a task switch that wants a clean context calls for a fresh
  spawn, and "compaction" is not an available move — never tell an agent to
  compact.

## When this applies

Invoke this skill once at the start of a task you want run in
executor-advisor mode: `/advisor`. The session then operates as the lean
executor-orchestrator described above for the rest of that task. The
`/advisor-refresh` sub-skill fires on the loop this skill starts and restates
the discipline mid-run; a person never invokes `/advisor-refresh` by hand.

## Process

1. **Invocation guard (once per session).** Before scheduling anything, check
   whether the refresh loop is already running this session. If it is, skip
   straight to executor work — do not schedule a second loop.

2. **Register the discipline reminder.** By default, schedule it with
   `ScheduleWakeup` at `delaySeconds: 1200`, prompt `/advisor-refresh`, where
   each refresh re-schedules the next one — a 1200-second wakeup costs one
   prompt-cache miss per firing and nothing more (see Gotchas). The loop
   mechanism (`/loop 20m /advisor-refresh`) is the escape hatch when
   `ScheduleWakeup` is not available. Either way the reminder is the
   enforcement surface: each firing re-asserts the discipline while the run is
   in flight.

3. **Run the task end to end.** Drive the work as the orchestrator. Delegate
   the code-writing to worker agents (for example `clean-coder`) and keep
   driving while they run. How you structure the work is yours to decide.

4. **Consult the advisor at a hard decision.** Reach for the advisor when one
   of these holds:
   - You have tried the same problem twice or more and it still fails.
   - A decision changes the deliverable's scope or a contract that is hard to
     reverse.
   - Two constraints conflict and you cannot satisfy both.
   - You are unsure whether to stop or keep going.

5. **Follow the advisor contract.** Spawn or resume `code-advisor` via the
   `Agent` tool. The consultation message carries three things: the task, what
   you tried, and the exact blocker (plus any short code excerpt that helps).
   The advisor replies with exactly one signal:
   - **PLAN** — a different approach, as concrete ordered steps you can run.
     When a warm agent fits the plan, the advisor names which one to resume.
   - **CORRECTION** — your approach is right, one thing is wrong; it names the
     wrong step and the fix.
   - **STOP** — no path satisfies the task as assigned; it says why so you can
     report upward.
   Resume your work the moment the reply lands.

   A worked consultation:

   ```
   Consultation → code-advisor
   Task: add a retry to the upload client.
   Tried: wrapped upload() in a three-attempt loop; the second attempt
   double-posts.
   Blocker: the server takes no idempotency key, so a retry after a timeout
   creates a duplicate record.

   Reply ← code-advisor
   CORRECTION — the retry loop is right; the missing piece is a stable request
   id. Generate one client-side on the first attempt and send the same id on
   every retry, so the server treats the retries as one request.
   ```

## Agent reuse (non-negotiable)

- **Resume before you spawn, always.** A warm agent carries its context and
  cached tokens; a fresh spawn starts cold and pays to rebuild both.
  `SendMessage` with an agent's name or `agentId` resumes a running or a
  completed agent with its context intact — verified live in this environment.
  Prefer that path every time an existing agent holds relevant context.
- **Spawn a fresh agent only when** no existing agent holds relevant context,
  or a genuine task switch needs a clean context.
- **A task switch is the only "clear."** No tool compacts or clears a
  subagent's context on demand. So the way to get a clean context for a new
  task is a fresh spawn; compaction is not a lever you hold — never instruct an
  agent to compact.
- **The advisor names the agent to resume.** When the advisor returns a PLAN
  and a warm agent fits, its plan says which agent to resume and where.

## Constraints

- One `/advisor` per session; the invocation guard blocks a second reminder
  loop.
- The advisor stays tool-less and silent to the user — guidance to the
  executor only.
- Consultations are capped at five per task by default. At the cap, re-scope
  or hand off; do not keep consulting.
- Reuse a warm agent over a cold spawn whenever one holds relevant context.
