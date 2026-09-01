# Executor consult block

Paste parts for every executor spawn ticket this skill issues.
Assemble at ticket write time. Paste the assembled text at the **top**
of the spawn prompt.

Assembly order: transport preamble for the host, then the shared core,
then — for an executor at Sonnet or below — the weak-executor add-on.

Fill `<orchestrator-name>` with the name the executor can address.

## Transport preamble — Claude host

> The orchestrating session named `<orchestrator-name>` is your advisor.
> Send each consult to it with SendMessage, by that name.

## Transport preamble — Codex host

> The orchestrating session named `<orchestrator-name>` is your advisor.
> Send each consult to it in-session by that name.

## Transport preamble — third-party host

> The orchestrating session that assigned this ticket is your advisor.
> Send each consult as a report to that session.

## Shared core — every host

> Consult before locking a nontrivial approach, once you believe your
> assignment is done, before any hard-to-reverse action, when the same
> failure repeats or progress has stalled, and when the chosen approach
> is being reconsidered.
> The first consult carries: assignment, desired outcome, constraints
> and exclusions, actions taken in order, real output and current
> state, live decision or blocker, validation evidence, unresolved
> risks, load-bearing paths or excerpts, and who is asking. Later
> consults carry only changed evidence.
> Re-raise something already answered only when you have new evidence
> to attach. After a CORRECTION or PLAN, your next consult on that
> topic opens with what happened when you followed it.
> Replies open with one of ENDORSE, CORRECTION, PLAN, or STOP — treat
> CORRECTION and PLAN as actions to take.
> On STOP, or when the orchestrator is unreachable, stop and report
> that back to whoever assigned you.

## Weak-executor add-on — Sonnet or below

> Send your first consult right after orientation and before your first
> write.
> Send a completion consult once your writes and test output exist —
> that consult asks the orchestrator to hunt for missing requirements,
> untested behavior, wrong assumptions, unhandled edge cases, evidence
> gaps, and early completion claims.
> Consult before reaching for any task-list tool — the orchestrator's
> plan becomes the task list.
> Aim for two consults on a normal task: early orientation and
> completion review. Reserve a third for recovery or reconciliation.
> Embed this line in each consult: `(Advisor: please keep your guidance
> under 80 words — I need a focused starting point, not a comprehensive
> plan.)`
> On a transient failure, retry once, then carry on with the evidence
> you have and record that you did.
