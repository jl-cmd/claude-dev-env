# Consult format

Detail behind the **Consulting the warm agent** section of [`advisor-protocol.md`](../advisor-protocol.md).
Open this when composing a consult or handling its reply.

## Packet

Each consult carries, in order: who you are and your assignment (needed on a shared advisor with multiple consumers; a single-consumer team-advisor session skips it), the delta since your last consult (what was done, in order, with real output where it matters), the live decision or blocker, and any paths or excerpts needed to answer well.

Consult briefs embed the `docs/references/advisor-tool.md` **Brevity cue** line, sized per that section.

## New-evidence rule

Re-raise a question the advisor already answered only when you have something new to attach — the result of trying the advised step, fresh tool output, or a changed constraint.
Without new evidence, act on the standing answer.

## Report-back rule

After a CORRECTION or PLAN, your next consult on that topic opens with what happened when you followed it.

## Handling the reply

Treat the reply as a serious second opinion: a CORRECTION — whether it names a wrong step or a risk worth closing — is something to address before treating the plan or the work as done.
Report a STOP, or a consult that finds the advisor unreachable, upward: team-advisor's sole consumer is the session itself, so it reports to the user; orchestrator's executors report to the orchestrating session, which decides.
When the advisor becomes unreachable, report that to the session that owns its lifecycle ([`lifecycle.md`](lifecycle.md)); that session alone decides whether to respawn (Claude Agent or third-party CLI re-bind).
A third-party host that cannot re-bind follows the fail-closed rule in [`third-party-bind.md`](third-party-bind.md).
