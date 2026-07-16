---
name: orchestrator
description: >-
  Orchestrator mode: plan and delegate while workflow-backed agents
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

Under this skill the session is the orchestrator. It spawns and resumes
executor subagents — `clean-coder` and the like — and those executors do
every bit of the execution: the code edits, the build runs, the test
runs. The orchestrating session drives the plan, keeps the run artifacts
and the ledger current, and routes hard decisions to the shared advisor.
The moment it edits a file or runs a test itself, the pairing breaks —
its own tool use stays orchestration, run-artifact writes, and light
verification reads.

## Design rule — thin prompts, thick artifacts, thin skill

Three faces of one rule (reading pinned by the audit spec on
jl-cmd/claude-dev-env#174: thin means high-signal, not short; thick
context lives outside the window, reachable by pointers):

- **Thin prompts.** A spawn prompt is a dispatch ticket: one task,
  pointers to the artifacts that hold the context, one done-check, a thin
  return contract. The prompt can be thin because the context is thick
  elsewhere.
- **Thick artifacts.** Durable run state lives in files — the run
  charter, one assignment file per task, result records — written once,
  read by every agent that needs them, and still there when any one
  agent's context is gone.
- **Thin skill.** This file holds only what changes decisions at
  orchestration time. Standing policy lives where it loads once:
  [`_shared/advisor/advisor-protocol.md`](../../_shared/advisor/advisor-protocol.md)
  for everything advisor, the agent definitions for executor discipline.

## Process

1. **Invocation guard.** One `/orchestrator` per session. When the
   refresh loop is already running, do not schedule a second one; reuse
   the live advisor bind and go to step 4.
2. **Register the discipline reminder.** Schedule it with
   `ScheduleWakeup` at `delaySeconds: 1800`, prompt
   `/orchestrator-refresh`, where each refresh re-schedules the next one.
3. **Bind the shared advisor before any executor.** Follow
   [`_shared/advisor/advisor-protocol.md`](../../_shared/advisor/advisor-protocol.md)
   end to end: detect the host profile, compute the floor from the
   orchestrator consumer set — this session plus every tier in the
   routing table (its Model floor section) — walk the ladder top-down,
   and fail closed when nothing binds. This session owns the advisor's
   whole lifecycle (its Lifecycle ownership section); executors only ever
   message the warm agent or report here, and an executor that finds the
   advisor unreachable reports that upward — it never spawns a
   replacement itself.
4. **Write the run artifacts** (next section) before the first spawn.
5. **Orchestrate.** Hold the plan and the user conversation. Spawn each
   task with a ticket (Spawn ticket section), keep driving while
   executors work, and keep the ledger reconciled (Task ledger
   discipline).
6. **Consult the advisor at hard decisions.** The trigger list, consult
   format, and reply handling live in the protocol's "Consulting the
   warm agent" section; both this session and every executor are
   consumers. Replies open with one of ENDORSE, CORRECTION, PLAN, or
   STOP — `agents/session-advisor.md` defines each signal.

## Run state lives in artifacts

Write these before the first spawn, default home `docs/plans/<run-slug>/`
in the repo the run works on (working files, not committed):

- **Run charter** — the goal, the repo root, the advisor name and host
  profile. One file every ticket points at.
- **One assignment file per task** — scope, file list, constraints, the
  acceptance check, baseline command output. The thick context goes
  here. `/prompt-generator` authors the assignment once at plan time,
  and every ticket for that task reuses it — that reuse is what
  satisfies the agent-spawn-protocol context check at each spawn.
- **Results merge into run state.** An executor's product is its
  artifact — the branch diff, the test output, the report its agent type
  may write — and its reply is thin: status, artifact paths, blockers.
  The orchestrating session records each result into the run's result
  files as it reconciles the ledger.

Correctness never rides on any agent's private context: when an executor
dies or hangs, point a fresh spawn at the same assignment file plus its
partial results and the run continues.

## Spawn ticket — the whole prompt

Every executor spawn prompt is this shape:

```
Task: <one sentence, one deliverable>
Read first: <assignment file path>; <run charter path>
Touch only: <files or globs>
Done when: <one mechanical check — a command, a test, a diff scope>
Return: status, artifact paths, blockers — nothing else.

<host-matched Advisor block from advisor-protocol.md, advisor name filled in>
```

- **Size the task by its done-check.** The right task is the largest
  unit that fits one sentence plus pointers, has one mechanical
  done-check, and needs no mid-run clarification. A task that does not
  fit gets split in the plan — never padded into a longer prompt.
  Explore fan-outs run tiny; a `clean-coder` assignment can carry a
  whole scoped feature.
- **Do not restate what the agent definition carries.** The routing
  table picks the definition, and `clean-coder` already holds the code
  discipline. The ticket adds the task, the pointers, and the Advisor
  block only.
- **The Advisor block is the one pasted paragraph.** It is host-matched
  at bind time and written to be self-contained (the protocol's Advisor
  block section) — paste it; do not point at it.

## Workflow Agent Routing

Every delegated task runs through a workflow-backed agent invocation. Do
not spawn a flat subagent directly when a workflow invocation or
workflow resume is available.

| Work | Agent type | Model |
|---|---|---|
| Feature, bug, and refactor coding | `clean-coder` | `opus` |
| Verification passes | `code-verifier` | `sonnet` |
| Script runs, GitHub posting, and backfill driving | `general-purpose` runner | `sonnet` |
| PR descriptions | `pr-description-writer` | `haiku`, with file-list grounding check |
| Fan-out searches and checklist verification reads | `Explore` | `haiku`; use `sonnet` when judgment-heavy |

Routing rules:

- Each row spawns workflow-backed with a ticket; the routing row and the
  ticket together carry the agent type, model, task, and return
  contract. A task category that maps to `clean-coder` on `opus` is not
  served by a `general-purpose` Sonnet spawn — the table is the
  contract, not a cost suggestion.
- Resume a warm workflow agent before creating a new workflow run when
  the warm agent holds the relevant context.
- `clean-coder` owns code edits. `code-verifier` owns verification. The
  same workflow agent never grades work it wrote.
- PR-description workflows include the actual changed-file list in the
  prompt and verify the final body against that file list before posting
  or returning it.
- Exploration workflows return file paths, line numbers, and direct
  evidence; they do not write code or mutate repo state.
- Fan-out worker fleets use the **grok-spawn** skill when that skill is
  installed and grok is usable (`grok_worker_preflight.py` soft gate).
  The Claude Code Agent tool remains the Claude-host alternative for
  in-process workers.

## Agent reuse

- **Resume before you spawn.** A warm agent (active within the past 59
  minutes) carries its context and cached tokens; a fresh spawn pays to
  rebuild both. Resume by name, or by `agentId` for an unnamed
  background spawn — keep the `agentId` (format `a...-...`) from the
  spawn result so `SendMessage` can reach that agent later.
- **Spawn a fresh agent only when** no existing agent holds relevant
  context, or a genuine task switch needs a clean context.
- **Reuse is a cost rule, not a correctness dependency.** The run
  artifacts keep every executor replaceable (Run state section).
- **Name the agent to resume.** When a PLAN from the shared advisor fits
  a warm agent, name which agent to resume and where.

## Task ledger discipline

The task list is the run's ledger, and it must be reconcilable against
the live agents at any moment. Four invariants hold at all times:

1. **No untracked work.** Every unit of delegated work has a task BEFORE
   its executor spawns — TaskCreate first, then Agent.
2. **Ownership is live.** At spawn, set the task `in_progress` with
   `owner` = the executor's agent name. One task, one owner.
3. **Completion follows evidence.** A task turns `completed` only when
   the executor's result is back AND merged into run state — the run's
   result files and the task record — never on dispatch, never on a
   self-report alone (see `workers-done-before-complete`).
4. **Dependencies mirror the plan.** Phase order is encoded as
   `blockedBy` links, updated the moment the plan changes.

Reconcile on every state change (spawn, completion notification, plan
change) and on every `/orchestrator-refresh` firing.

## Constraints

- One `/orchestrator` per session; the invocation guard blocks a second
  reminder loop.
- The orchestrating session never edits code or runs a build or test
  itself — executors do that. Its own tool use stays orchestration,
  run-artifact writes, and light verification reads.
- Every delegated task carries a ledger entry, an assignment artifact,
  and a workflow-backed spawn with a ticket, routed by the table.
- One shared advisor per orchestrated session, owned by this session per
  the protocol; executors never spawn, respawn, or shut it down.

## File Index

| File | Purpose |
|---|---|
| `SKILL.md` | Orchestrator strategy: design rule, process, run artifacts, spawn ticket, routing table, reuse rules, ledger invariants, constraints. |

## Folder Map

- `SKILL.md` — complete orchestrator workflow instructions. Advisor
  policy lives in
  [`_shared/advisor/advisor-protocol.md`](../../_shared/advisor/advisor-protocol.md).
