# Weak-Executor Advisor Profile

Consult profile for an executor spawned below the advisor's own tier — a
Sonnet or Haiku model carrying an advisor bind. `advisor-tool.md` sets the
canonical cadence for every consumer; this file adds the deltas a below-tier
executor needs on top of it.

Source: [Anthropic Advisor tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool)
(Suggested system prompt for coding tasks). The distilled facts behind each
section live in
`skills/team-advisor/reference/advisor-docs-review.md`.

## Scope

Applies to any executor running below the advisor's tier. A same-tier or
stronger executor follows `advisor-tool.md` alone.

## Steering lives in the spawn prompt

A runtime nudge carries no measured effect on Sonnet. The advisor rules sit
at the top of the spawn prompt, ahead of every other sentence that mentions
the advisor.

## Context packaging

The advisor never sees the executor's own transcript. Each consult carries
its own packet:

- **First consult** — a complete, self-contained packet: the task, the
  actions taken in order, real output, the live decision, and the
  load-bearing excerpts the decision rests on.
- **Later consults** — the delta only, not a restatement of the first
  packet.
- **Ordering** — stable role and charter text first, volatile detail last.

## Two-timing rule

Two consult moments carry the measured gain:

1. **Early** — after a few exploratory reads land in the transcript, before
   the first write. This is the hard rule `advisor-tool.md` §Hard rule
   states for every consumer.
2. **Final** — after file writes and test output exist to forward. Make the
   deliverable durable first (write the file, save the result, commit the
   change), then consult.

## Planner funnel

Consult the advisor before any task-list or planner tool. The advisor's plan
becomes the task list, not the other way around.

## Consult budget

Two to three consults per task. Every material fork consults the advisor
rather than the executor judging alone.

## Advice weight

Advice is binding absent empirical contradiction. A conflict between the
executor's own evidence and the advisor's guidance goes back to the advisor
as a reconcile consult — never a silent switch. See `advisor-tool.md` §How
to treat advice for the full weighing rule.

## Long-run reminder

On a run past roughly 20 advisor-free turns, the executor re-reads its
advisor rules before the next substantive step. A long-horizon executor does
not reliably recall the advisor exists on its own.

## Failure branches

- **Transient advisor failure** — retry once, then carry on without advice
  and record that gap in the result.
- **Advisor unreachable** — report upward. Never self-endorse a decision in
  the advisor's place, and never bind a replacement advisor without
  instruction.

## Pairing invariant

The advisor binds at or above the strongest consumer's tier. A weak
executor joining the pairing never lowers that floor.

## Related

| Doc | Holds |
|---|---|
| `advisor-tool.md` | Canonical consult cadence, hard rule, brevity cue |
| `~/.claude/_shared/advisor/advisor-protocol.md` | Host bind, model floor, "Claude host, Sonnet-or-below executor" section, executor paste blocks |
| `skills/team-advisor/reference/advisor-docs-review.md` | Distilled source facts behind each section above |
