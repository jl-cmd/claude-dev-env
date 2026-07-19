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

## status_gate (deterministic — not optional)

**Prose does not keep the loop alive.** Re-arm and terminate are gated by
`scripts/status_gate.py` (and, on Claude, the PreToolUse hook
`orchestrator_refresh_reschedule_gate`).

```
python scripts/status_gate.py set --status active [--run-slug SLUG] [--status-file PATH]
python scripts/status_gate.py set --status done [--run-slug SLUG] [--status-file PATH]
python scripts/status_gate.py should-reschedule [--run-slug SLUG] [--status-file PATH]
```

| Exit / output | Meaning |
|---|---|
| `set` → 0 | JSON status payload written (`active` or `done`) |
| `should-reschedule` → 0 | Status file exists and `status` is `active` — one-shot re-arm allowed |
| `should-reschedule` → 1 | Stop — missing/invalid/done status (fail closed) |

Default status path: file `.orchestrator-run-status.json` under the
repo's plans directory (runtime-created), or `$ORCHESTRATOR_RUN_STATUS_FILE`.
With `--run-slug SLUG`, the file is under the slug plans subdirectory.
When using a slug, every `ScheduleWakeup` prompt must carry it so the
PreToolUse hook can resolve the scoped file:
`/orchestrator-refresh --run-slug SLUG`.

**Rules:**

- **One-shot only.** `ScheduleWakeup` with prompt
  `/orchestrator-refresh` (plus `--run-slug SLUG` when the run uses a
  slug) and a delay. Never `CronCreate` / never a recurring host schedule
  for this loop (the PreToolUse hook denies CronCreate for this prompt).
- **Activate only with open work.** After the first ledger task exists,
  run `set --status active` (pass the same `--run-slug` for the whole
  run if you use one). Do not activate for advisor-bind alone.
- **Done is a script.** When every ledger task is completed/cancelled and
  no executor is running, run `set --status done` with the same
  `--run-slug` / `--status-file` as activate. Do not re-arm after that.
- **Re-arm only after the gate.** Before any refresh schedule call, run
  `should-reschedule` with the same path args. Exit 1 → cancel any
  existing schedule, report stop, do not call `ScheduleWakeup`. Exit 0 →
  one-shot re-arm only (prompt must include the same `--run-slug`).
- Hosts without the Claude hook (e.g. third-party schedulers) still obey
  the same exit codes; never use `recurring: true` for this loop.

## Process

1. **Invocation guard.** One `/orchestrator` per session. When a refresh
   one-shot is already queued, do not stack a second; reuse the live
   advisor bind and go to step 4.
2. **Bind the shared advisor before any executor.** Follow
   [`_shared/advisor/advisor-protocol.md`](../../_shared/advisor/advisor-protocol.md)
   end to end: detect the host profile, compute the floor from the
   orchestrator consumer set — this session plus every tier in the
   routing table (its Model floor section) — walk the ladder top-down,
   and fail closed when nothing binds. This session owns the advisor's
   whole lifecycle (its Lifecycle ownership section); executors only ever
   message the warm agent or report here, and an executor that finds the
   advisor unreachable reports that upward — it never spawns a
   replacement itself.
3. **Write the run artifacts** (next section) before the first spawn.
4. **Activate status_gate** when the first open ledger task exists:
   `python scripts/status_gate.py set --status active`.
5. **Register one-shot discipline reminder** only while the gate allows it:
   run `should-reschedule`; on exit 0, `ScheduleWakeup` with
   `delaySeconds: 2700`, prompt `/orchestrator-refresh` (and
   `--run-slug SLUG` when the run uses a slug; one-shot, not recurring).
6. **Orchestrate.** Hold the plan and the user conversation. Spawn each
   task with a ticket (Spawn ticket section), keep driving while
   executors work, and keep the ledger reconciled (Task ledger
   discipline).
7. **Consult the advisor at hard decisions.** The trigger list, consult
   format, and reply handling live in the protocol's "Consulting the
   warm agent" section; both this session and every executor are
   consumers. Replies open with one of ENDORSE, CORRECTION, PLAN, or
   STOP — `agents/session-advisor.md` defines each signal.
8. **Terminate when done.** When every ledger task is completed or
   cancelled and no executor is running: run
   `set --status done`, cancel any pending one-shot wakeup if the host
   exposes cancel, report completion, and stop. Do not re-arm.

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
- **Run status file** — written only by `status_gate.py`
  (`active` / `done`). Source of truth for reschedule.

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
change) and on every `/orchestrator-refresh` firing. After reconcile, if
no open work remains, run `set --status done` before any re-arm attempt.

## Constraints

- One `/orchestrator` per session; the invocation guard blocks a second
  stacked one-shot while one is already queued.
- Reschedule is mechanical: `should-reschedule` exit code + status file;
  never a recurring host schedule for this loop.
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
| `SKILL.md` | Orchestrator strategy; pointers to run-control scripts. |
| `scripts/status_gate.py` | Status file + should-reschedule gate (exit codes). |
| `scripts/status_gate_constants/config/constants.py` | Named constants for status_gate. |
| `scripts/test_status_gate.py` | Gate tests. |

## Folder Map

- `SKILL.md` — orchestration process and routing.
- `scripts/` — deterministic status_gate.
- Advisor policy:
  [`_shared/advisor/advisor-protocol.md`](../../_shared/advisor/advisor-protocol.md).
