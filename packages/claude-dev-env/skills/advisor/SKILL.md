---
name: advisor
description: >-
  Turns the session into the advisor-orchestrator — the user's sole interface,
  which spawns and resumes executor subagents (clean-coder and the like) to do
  all the code editing and every build or test run. When an executor hits a
  blocker it consults the advisor, which replies with one of three brief
  signals — a plan, a correction, or a stop. The advisor orchestrates and
  advises but never edits code or runs tests itself. Caps consultations per
  task (default 5), reuses warm agents before spawning new ones, and
  re-asserts the discipline every 20 minutes through the /advisor-refresh
  loop. Adapts Anthropic's advisor strategy to Claude Code. Triggers:
  '/advisor', 'advisor strategy', 'run with an advisor', 'executor-advisor
  mode'.
---

# Advisor Strategy

## Principle

A cost-effective executor runs the primary work — it calls tools, reads
results, and iterates — while a stronger model advises only at the hard
decisions. Source: Anthropic's advisor strategy,
https://claude.com/blog/the-advisor-strategy.

Under this skill the session is the advisor-orchestrator. In Claude Code the
user always talks to the session and never to a subagent, so the session is
the user's sole interface: all user-facing communication flows through it. It
spawns and resumes executor subagents — `clean-coder` and the like — and those
executors do every bit of the execution: the code edits, the build runs, the
test runs. The advisor drives the plan and answers the executors when they get
stuck.

This is the advisor-lite shape: the blog's pure pairing keeps the advisor
tool-less and hidden from the user, but Claude Code routes every user message
through the session, so the advisor here stays the user's interface while
keeping execution out of its own hands. Consultations are capped (default 5
per task) — the same guard the API's `max_uses` gives a tool.

## Gotchas

- **Double invocation duplicates the reminder loop.** A second `/advisor` in
  the same session schedules a second refresh loop. Check whether the loop is
  already running before you schedule one (see the invocation guard in
  Process step 1).
- **The advisor never executes.** The moment it edits a file or runs the tests
  itself, the pairing breaks and the executor's warm context is wasted. Hand
  every code edit and every build or test run to an executor; keep the
  advisor's own tool use to orchestration and light verification reads.
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
executor-advisor mode: `/advisor`. The session then operates as the
advisor-orchestrator described above for the rest of that task. The
`/advisor-refresh` sub-skill fires on the loop this skill starts and restates
the discipline mid-run; a person never invokes `/advisor-refresh` by hand.

## Process

1. **Invocation guard (once per session).** Before scheduling anything, check
   whether the refresh loop is already running this session. If it is, skip
   straight to orchestration — do not schedule a second loop.

2. **Register the discipline reminder.** By default, schedule it with
   `ScheduleWakeup` at `delaySeconds: 1200`, prompt `/advisor-refresh`, where
   each refresh re-schedules the next one — a 1200-second wakeup costs one
   prompt-cache miss per firing and nothing more (see Gotchas). The loop
   mechanism (`/loop 20m /advisor-refresh`) is the escape hatch when
   `ScheduleWakeup` is not available. Either way the reminder is the
   enforcement surface: each firing re-asserts the discipline while the run is
   in flight.

3. **Orchestrate the task.** Hold the plan and the user conversation. Spawn or
   resume executor subagents (for example `clean-coder`) to do every code edit
   and every build or test run, and keep driving while they work. Your own
   tool use stays orchestration and light verification reads.

4. **Executors consult at a hard decision.** Each executor's spawn prompt tells
   it to stop and message you — with the task, what it tried, and the exact
   blocker (plus any short code excerpt that helps) — when one of these holds:
   - It has tried the same problem twice or more and it still fails.
   - A decision changes the deliverable's scope or a contract that is hard to
     reverse.
   - Two constraints conflict and it cannot satisfy both.
   - It is unsure whether to stop or keep going.

5. **Answer with one signal.** On a consultation, reply with exactly one
   signal, brief (about 400 to 700 tokens):
   - **PLAN** — a different approach, as concrete ordered steps the executor
     can run. When a warm agent fits the plan, name which one to resume.
   - **CORRECTION** — the executor's approach is right, one thing is wrong;
     name the wrong step and the fix.
   - **STOP** — no path satisfies the task as assigned; say why so it can be
     reported upward.
   The executor resumes the moment your reply lands.

   A worked consultation:

   ```
   Executor → advisor
   Task: add a retry to the upload client.
   Tried: wrapped upload() in a three-attempt loop; the second attempt
   double-posts.
   Blocker: the server takes no idempotency key, so a retry after a timeout
   creates a duplicate record.

   Advisor → executor
   CORRECTION — the retry loop is right; the missing piece is a stable request
   id. Generate one client-side on the first attempt and send the same id on
   every retry, so the server treats the retries as one request.
   ```

   For a decision the advisor itself cannot settle, it may spawn the tool-less
   `code-advisor` agent for a second opinion — an optional escalation, not a
   required step.

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
- **Name the agent to resume.** When you answer with a PLAN and a warm agent
  fits, say which agent to resume and where.

## Constraints

- One `/advisor` per session; the invocation guard blocks a second reminder
  loop.
- The advisor orchestrates and advises but never edits code or runs a build or
  test itself — executors do that.
- Consultations are capped at five per task by default. At the cap, re-scope
  or hand off; do not keep answering.
- Reuse a warm agent over a cold spawn whenever one holds relevant context.
