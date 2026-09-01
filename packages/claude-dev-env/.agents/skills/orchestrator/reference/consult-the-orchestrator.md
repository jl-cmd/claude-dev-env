# Consult the orchestrator

Consumer consult contract for executors this skill spawns. The
orchestrating session is the advisor. The human operating that session
is the next hop when the orchestrator cannot decide.

Do not open `_shared/advisor/advisor-protocol.md`. Do not spawn
`session-advisor`. Do not walk a Fable or Sol advisor ladder.

Packet shape, later-consult deltas, the new-evidence rule, and the
report-back rule live in
[`consult-format.md`](../../../../_shared/advisor/reference/consult-format.md).
Call timing and the brevity cue live in
[`advisor-tool.md`](../../../../docs/references/advisor-tool.md)
**When to call**, **Hard rule**, and **Brevity cue**.

## When an executor consults

An executor sends a consult to the orchestrating session:

- after orientation and before the first write
- before locking a plan or interpretation
- before a hard-to-reverse action
- when the same failure repeats or progress has stalled
- when the chosen approach is being reconsidered
- once writes and test output exist and the executor believes the
  assignment is done

## How the executor sends it

On a Claude host, send the consult with `SendMessage` to the
orchestrating session by the name the ticket gives.

On a Codex host, send the consult in-session to that same session name.

On a third-party host, send the consult as a report to the session that
assigned the ticket.

Use the first-consult packet in `consult-format.md`. Later consults
carry only changed evidence. Embed the brevity cue from
`advisor-tool.md`.

## How the orchestrator replies

The first line is one of:

- **ENDORSE** — the plan or the finished work holds. A clean yes.
- **CORRECTION** — a wrong step or a risk to close. Name the problem and
  the fix.
- **PLAN** — the approach must change. Give ordered steps the executor
  can run.
- **STOP** — no path satisfies the assignment. Say why, with proof.

The executor treats CORRECTION and PLAN as actions to take. On STOP, or
when the orchestrator is unreachable, the executor stops and reports to
the session that assigned the ticket.

## How the orchestrator uses the human

The orchestrator answers from the run charter, the assignment, and the
consult packet. When the question is ambiguous, changes scope, or needs
a choice the charter does not settle, the orchestrator asks the human,
then returns one of the four signals to the executor.
