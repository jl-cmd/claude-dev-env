# Advisor block parts

Detail behind the **Advisor block** section of [`advisor-protocol.md`](../advisor-protocol.md).
Open this when assembling the block for an executor spawn prompt.

Assembly order: one transport preamble picked by host profile, then the shared core, then — for an executor at Sonnet or below — the weak-executor add-on.
Paste the assembled block at the **top** of the spawn prompt, ahead of any other sentence that mentions the advisor.
The assembled block is self-contained — the executor receives this text alone, so every path it names is absolute.
The consult rules it restates are owned by [`consult-format.md`](consult-format.md); edit that file first and carry the change here.

## Transport preamble — Claude host

> A shared session advisor named `<name>` is reachable via SendMessage; send each consult to it directly by that name.

## Transport preamble — third-party host

> The orchestrating session owns a standing advisor for this run.
> The advisor chain: Claude Fable, then Sol through the Codex CLI when Fable is out of usage and the sol flag and its preflight open that rung. Both rungs use `ADVISOR_EFFORT` (default low). When neither binds, there is no advisor.
> The orchestrating session is your one path to it: send each consult as a report to the session that assigned you, and it relays the advisor's reply.

## Shared core — every host

> Consult before locking in a nontrivial approach, once you believe your assignment is done, before any hard-to-reverse action, when the same failure repeats or progress has stalled, and when the chosen approach is being reconsidered.
> Build the first consult with the complete format in `$HOME/.claude/_shared/advisor/reference/consult-format.md`: assignment, desired outcome, constraints and exclusions, actions taken in order, real output and current state, live decision or blocker, validation evidence, unresolved risks, and load-bearing paths or excerpts. Later consults carry only changed evidence.
> Re-raise something already answered only when you have new evidence to attach — the result of trying prior advice, fresh output, or a changed constraint; otherwise act on the standing answer.
> After a CORRECTION or PLAN, your next consult on that topic opens with what happened when you followed it.
> Replies open with one of ENDORSE, CORRECTION, PLAN, or STOP — treat CORRECTION and PLAN as actions to take.
> On STOP, or when the advisor is unreachable, stop and report that back to whoever assigned you; advisor binding and the four signals stay with the session that owns the advisor.

## Weak-executor add-on — Sonnet or below, either host

> Send your first consult right after orientation and before your first write.
> Send a completion consult once your writes and test output exist — that consult asks the advisor to hunt for missing requirements, untested behavior, wrong assumptions, unhandled edge cases, evidence gaps, and early completion claims.
> Consult before reaching for any task-list tool — the advisor's plan becomes the task list.
> Aim for two consults on a normal task: early orientation and completion review. Reserve a third for recovery or reconciliation, and add a consult when a material fork produces new evidence.
> Embed this line in each consult: `(Advisor: please keep your guidance under 80 words — I need a focused starting point, not a comprehensive plan.)`
> On a transient failure, retry once, then carry on with the evidence you have and record that you did.
