# Consult format

Detail behind the **Consulting the warm agent** section of [`advisor-protocol.md`](../advisor-protocol.md).
Open this when composing a consult or handling its reply.

## Packet

The first consult is complete and self-contained. It carries:

- Assignment and desired outcome
- Constraints and exclusions
- Actions taken in order
- Real output and current state
- Live decision or blocker
- Validation evidence
- Unresolved risks
- Load-bearing paths or excerpts

On a shared advisor with multiple consumers, open with who is asking and the assignment. A single-consumer team-advisor session may omit the identity opener while keeping the assignment.

Later consults carry only the delta: changed actions, new output, changed decisions, new validation, and newly discovered risks.

The completion consult carries the durable deliverable, test output, unresolved risks, evidence gaps, and any claim that the task is ready to close.

Consult briefs embed the [`docs/references/advisor-tool.md`](../../../docs/references/advisor-tool.md) **Brevity cue** line, sized per that section.

## New-evidence rule

Re-raise a question the advisor already answered only when you have something new to attach — the result of trying the advised step, fresh tool output, or a changed constraint.
Without new evidence, act on the standing answer.

## Report-back rule

After a CORRECTION or PLAN, your next consult on that topic opens with what happened when you followed it.

## Handling the reply

Address a CORRECTION before treating the plan or the work as done, whether it names a wrong step or a risk worth closing.
Report a STOP, or a consult that finds the advisor unreachable, upward: team-advisor's sole consumer is the session itself, so it reports to the user; orchestrator's executors report to the orchestrating session, which decides.
When the advisor becomes unreachable, report that to the session that owns its lifecycle ([`lifecycle.md`](lifecycle.md)); that session alone decides whether to respawn (Claude Agent or third-party CLI re-bind).
A third-party host that cannot re-bind follows the fail-closed rule in [`third-party-bind.md`](third-party-bind.md).
