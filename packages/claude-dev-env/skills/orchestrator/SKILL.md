---
name: orchestrator
description: >-
  Advisor-orchestrator mode: plan and delegate while workflow-backed agents
  execute; a shared session-advisor answers hard decisions with endorse,
  correction, plan, or stop. Triggers: '/orchestrator', 'orchestrator
  strategy', 'run with an orchestrator', 'executor-advisor mode',
  'orchestrator enforcement', 'agent routing', 'orchestrate'.
---

# Orchestrator Strategy

## Principle

A frontier model plans and synthesizes while cheap workers do the
token-heavy reading and doing — Anthropic's coordinator pattern, source:
https://github.com/anthropics/claude-cookbooks/blob/main/managed_agents/CMA_plan_big_execute_small.ipynb
("Coordinator pattern: big models for planning, small models for
execution"). On the cookbook's own measured run, a coordinator
delegating to Sonnet-5 workers came out cheaper and faster
than a solo frontier agent held to the same verification rigor, with
84-98% of the team's input tokens billed at the worker rate.

Claude Code has no `multiagent` coordinator field or Managed-Agents-style
`create_agent`/`send_to_agent` primitives; this skill reaches the same
shape with the tools Claude Code already has. Under this skill the session
is the advisor-orchestrator. In Claude Code the user always talks to the session and never to a
subagent, so the session is the user's sole interface: all user-facing
communication flows through it. It spawns and resumes executor subagents
— `clean-coder` and the like — and those executors do every bit of the
execution: the code edits, the build runs, the test runs. The orchestrating
session drives the plan and routes hard decisions to the shared session-advisor.

## Gotchas

- **Double invocation duplicates the reminder loop.** A second `/orchestrator`
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
- **Only the orchestrating session owns the shared advisor's lifecycle.** An
  executor that finds the advisor unreachable reports that upward; it never
  spawns a replacement itself.


## Process

1. **Check whether the refresh loop is already running this
   session. If it is, skip straight to orchestration — do not schedule a
   second loop.

2. **Register the discipline reminder.** By default, schedule it with
   `ScheduleWakeup` at `delaySeconds: 1200`, prompt `/orchestrator-refresh`,
   where each refresh re-schedules the next one — a 1200-second wakeup costs
   one prompt-cache miss per firing and nothing more (see Gotchas). The loop
   mechanism (`/loop 20m /orchestrator-refresh`) is the escape hatch when
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
| Verification passes | `code-verifier` | `sonnet` |
| Script runs, GitHub posting, and backfill driving | `general-purpose` runner | `sonnet` |
| PR descriptions | `pr-description-writer` | `sonnet`, with file-list grounding check |
| Fan-out searches and checklist verification reads | `Explore` | `haiku`; use `sonnet` when judgment-heavy |

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

## Shared advisor

Spawn one shared `session-advisor` agent per orchestrated session, following
the Warm-up procedure in
[`_shared/advisor/advisor-protocol.md`](../../_shared/advisor/advisor-protocol.md).
Compute the model floor as the max of the orchestrating session's own tier and
the highest tier named in the Workflow Agent Routing table above (today:
max(sonnet, opus) = opus).

Paste the Advisor block from that same doc, with the resolved agent name filled
in, into every executor's spawn prompt — every row in the routing table above
is a consumer of the shared advisor, not just this session. The orchestrating
session's own hard decisions (see Process step 4 below) go to this same shared
advisor via SendMessage.

The orchestrating session owns the shared advisor's lifecycle end to end
(spawn, drift-respawn per the shared doc, shutdown at task end); executors only
ever send it messages.

4. **Executors consult at a hard decision.** Each executor's spawn prompt tells
   it to stop and consult the shared advisor (see Shared advisor section above)
   — with the task, what it tried, and the exact blocker (plus any short code
   excerpt that helps) — when one of these holds:
   - It has tried the same problem twice or more and it still fails.
   - A decision changes the deliverable's scope or a contract that is hard to
     reverse.
   - Two constraints conflict and it cannot satisfy both.
   - It is unsure whether to stop or keep going.

5. **The shared advisor answers.** Every consult — from an executor or from
   this session's own hard decisions — goes to the shared advisor and gets back
   one of its four signals. See `agents/session-advisor.md` for what each signal
   means and
   [`_shared/advisor/advisor-protocol.md`](../../_shared/advisor/advisor-protocol.md)
   for the consult format.

## Agent reuse (non-negotiable)

- **Resume before you spawn, always.** A warm agent carries its context and
  cached tokens; a fresh spawn starts cold and pays to rebuild both.
  Resume the existing workflow agent by name or `agentId` when it holds
  relevant context. Prefer that path every time an existing workflow agent
  matches the routing table.
- **Spawn a fresh agent only when** no existing agent holds relevant context,
  or a genuine task switch needs a clean context.
- **Name the agent to resume.** When a PLAN fits a warm agent, name which
  agent to resume and where.

## Constraints

- One `/orchestrator` per session; the invocation guard blocks a second
  reminder loop.
- The advisor orchestrates and advises but never edits code or runs a build or
  test itself — executors do that.
- Delegated execution uses workflow-backed agent invocations and follows the
  Workflow Agent Routing table exactly.
- One shared session-advisor per orchestrated session, owned by the
  orchestrating session (see
  [`_shared/advisor/advisor-protocol.md`](../../_shared/advisor/advisor-protocol.md))
  — executors consult it, they never spawn or respawn it.
- Reuse a warm agent over a cold spawn whenever one holds relevant context.

## File Index

| File | Purpose |
|---|---|
| `SKILL.md` | Advisor strategy, workflow routing contract, consultation protocol, reuse rules, and constraints. |

## Folder Map

- `SKILL.md` — complete advisor workflow instructions.
