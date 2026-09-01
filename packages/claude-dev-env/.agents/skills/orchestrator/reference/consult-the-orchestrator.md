# Consult the orchestrator

The orchestrating session is the advisor. The human operating that session is the next hop when the orchestrator cannot decide.

## When an executor consults

An executor sends a consult to the orchestrating session:

- after orientation and before the first write
- before locking a plan or interpretation
- before a hard-to-reverse action
- when the same failure repeats or progress has stalled
- when the chosen approach is being reconsidered
- once writes and test output exist and the executor believes the
  assignment is done

## First-consult packet

The first consult is complete. It carries:

- Assignment and desired outcome
- Constraints and exclusions
- Actions taken in order
- Real output and current state
- Live decision or blocker
- Validation evidence
- Unresolved risks
- Load-bearing paths or excerpts
- Who is asking and which assignment

Later consults carry only changed evidence.

Re-raise something already answered only when new evidence is attached.
After a CORRECTION or PLAN, the next consult on that topic opens with
what happened when the executor followed it.

Embed: `(Advisor: please keep your guidance under 80 words — I need a
focused starting point, not a comprehensive plan.)`

## How the executor sends it

On a Claude host, send the consult with `SendMessage` to the
orchestrating session by the name the ticket gives.

On a Codex host, send the consult in-session to that same session name.

On a third-party host, send the consult as a report to the session that
assigned the ticket.

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
