---
name: team-advisor
description: >-
  Turns the session into the advisor-orchestrator — the user's sole interface,
  running on Fable 5 (`claude-fable-5`), the coordinator-tier model, to plan
  and delegate while workflow-backed agent spawns do the token-heavy
  execution with the required agent type and model for each work category.
  Executors do the code editing, verification, script driving, PR
  descriptions, and searches; the advisor answers blockers with one of three
  brief signals — a plan, a correction, or a stop. The advisor never edits
  code or runs tests itself. Caps consultations per task (default 5), reuses
  warm workflow agents before spawning new ones, and re-asserts the
  discipline every 20 minutes through the /team-advisor-refresh loop. Adapts
  Anthropic's coordinator pattern (plan big, execute small) to Claude Code.
  Triggers: '/team-advisor', 'team advisor strategy', 'run with a team
  advisor', 'executor-advisor mode', 'team advisor enforcement', 'agent
  routing', 'fable orchestrator'.
---

# Team Advisor Strategy

## Principle

A frontier model plans and synthesizes while cheap workers do the
token-heavy reading and doing — Anthropic's coordinator pattern, source:
https://github.com/anthropics/claude-cookbooks/blob/main/managed_agents/CMA_plan_big_execute_small.ipynb
("Coordinator pattern: big models for planning, small models for
execution"). On the cookbook's own measured run, a Fable-5 coordinator
delegating to Sonnet-5 workers came out roughly 2.5x cheaper and 3x faster
than a solo frontier agent held to the same verification rigor, with
84-98% of the team's input tokens billed at the worker rate.

Claude Code has no `multiagent` coordinator field or Managed-Agents-style
`create_agent`/`send_to_agent` primitives; this skill reaches the same
shape with the tools Claude Code already has. Under this skill the session
is the advisor-orchestrator, and it runs on **Fable 5** (`claude-fable-5`)
— switch to it with `/model claude-fable-5` (or the `/model` picker)
before you start orchestrating if the session opened on a different
model. In Claude Code the user always talks to the session and never to a
subagent, so the session is the user's sole interface: all user-facing
communication flows through it. It spawns and resumes executor subagents
— `clean-coder` and the like — and those executors do every bit of the
execution: the code edits, the build runs, the test runs. The advisor
drives the plan and answers the executors when they get stuck.

This is the advisor-lite shape: the cookbook's pure coordinator keeps
itself tool-less and hidden from the user, but Claude Code routes every
user message through the session, so the advisor here stays the user's
interface while keeping execution out of its own hands. Consultations are
capped (default 5 per task) — the same guard the API's `max_uses` gives a
tool.

## Gotchas

- **Double invocation duplicates the reminder loop.** A second `/team-advisor`
  in the same session schedules a second refresh loop. Check whether the loop
  is already running before you schedule one (see the invocation guard in
  Process step 1).
- **The advisor never executes.** The moment it edits a file or runs the tests
  itself, the pairing breaks and the executor's warm context is wasted. Hand
  every code edit and every build or test run to an executor; keep the
  advisor's own tool use to orchestration and light verification reads.
- **Flat ad hoc spawns bypass routing.** Every execution task goes through a
  workflow-backed spawn or workflow resume so the required agent type, model,
  prompt packet, and sidecar metadata stay attached to the work.
- **Wrong agent or model is an enforcement failure.** If a task category maps
  to `clean-coder` on `opus`, a `general-purpose` Sonnet spawn is not a cost
  optimization; it is the wrong executor for the contract.
- **Resuming an unnamed background agent needs its agentId.** A background
  spawn returns an `agentId` (format `a...-...`); keep it so `SendMessage` can
  reach that agent later. A named agent is reachable by name.
- **Consultations past the cap signal a scoping problem.** When five
  consultations do not clear the blocker, the task needs re-scoping or a
  hand-off to the user — not a sixth round of advice.
- **Fable 5 unavailable.** If the session can't switch to `claude-fable-5`
  (older Claude Code build, no access), fall back to Opus for the
  orchestrator role and say so — do not silently orchestrate on a lesser
  model without noting the substitution.


## Process

1. **Model check, then invocation guard (once per session).** Confirm the
   session is running Fable 5 (`claude-fable-5`); if not, switch with
   `/model claude-fable-5` before anything else (see Gotchas for the
   fallback). Then check whether the refresh loop is already running this
   session. If it is, skip straight to orchestration — do not schedule a
   second loop.

2. **Register the discipline reminder.** By default, schedule it with
   `ScheduleWakeup` at `delaySeconds: 1200`, prompt `/team-advisor-refresh`,
   where each refresh re-schedules the next one — a 1200-second wakeup costs
   one prompt-cache miss per firing and nothing more (see Gotchas). The loop
   mechanism (`/loop 20m /team-advisor-refresh`) is the escape hatch when
   `ScheduleWakeup` is not available. Either way the reminder is the
   enforcement surface: each firing re-asserts the discipline while the run is
   in flight.

3. **Orchestrate the task.** Hold the plan and the user conversation. Execute
   workflow-backed spawns or resumes using the routing table below, and keep
   driving while they work. Your own tool use stays orchestration and light
   verification reads. Keep your task list updated religiously.

## Workflow Agent Routing

Every delegated task runs through a workflow-backed agent invocation. Do not
spawn a flat subagent directly when a workflow invocation or workflow resume is
available.

| Work | Agent type | Model |
|---|---|---|
| Feature, bug, and refactor coding | `clean-coder` | `opus` |
| Verification passes | `code-verifier` | `opus` |
| Script runs, GitHub posting, and backfill driving | `general-purpose` runner | `sonnet` |
| PR descriptions | `pr-description-writer` | `sonnet`, with file-list grounding check |
| Fan-out searches and checklist verification reads | `Explore` | `haiku`; use `sonnet` when judgment-heavy |
| Escalated blockers needing a second opinion beyond the orchestrator's own judgment | `code-advisor` | Fable preferred (matches the orchestrating session); opus if Fable is unavailable. |

Routing rules:

- Use a workflow invocation or resume for each row above. The workflow prompt
  must name the selected agent type, model, work category, task scope, and
  expected output.
- Resume a warm workflow agent before creating a new workflow run when the warm
  agent holds the relevant context.
- `clean-coder` owns code edits. `code-verifier` owns verification. The same
  workflow agent never grades work it wrote.
- PR-description workflows include the actual changed-file list in the prompt
  and verify the final body against that file list before posting or returning
  it.
- Exploration workflows return file paths, line numbers, and direct evidence;
  they do not write code or mutate repo state.

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

   For a decision the advisor itself cannot settle, it may use a workflow
   escalation to the tool-less `code-advisor` agent for a second opinion — an
   optional escalation, not a required step.

## Agent reuse (non-negotiable)

- **Resume before you spawn, always.** A warm agent carries its context and
  cached tokens; a fresh spawn starts cold and pays to rebuild both.
  Resume the existing workflow agent by name or `agentId` when it holds
  relevant context. Prefer that path every time an existing workflow agent
  matches the routing table.
- **Spawn a fresh agent only when** no existing agent holds relevant context,
  or a genuine task switch needs a clean context.
- **Name the agent to resume.** When you answer with a PLAN and a warm agent
  fits, say which agent to resume and where.

## Constraints

- One `/team-advisor` per session; the invocation guard blocks a second
  reminder loop.
- The orchestrator runs on Fable 5; check and switch at the start of every invocation per Process step 1.
- The advisor orchestrates and advises but never edits code or runs a build or
  test itself — executors do that.
- Delegated execution uses workflow-backed agent invocations and follows the
  Workflow Agent Routing table exactly.
- Consultations are capped at five per task by default. At the cap, re-scope
  or hand off; do not keep answering.
- Reuse a warm agent over a cold spawn whenever one holds relevant context.

## File Index

| File | Purpose |
|---|---|
| `SKILL.md` | Advisor strategy, workflow routing contract, consultation protocol, reuse rules, and constraints. |

## Folder Map

- `SKILL.md` — complete advisor workflow instructions.
