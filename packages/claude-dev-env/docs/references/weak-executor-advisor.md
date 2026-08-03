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

The advisor rules sit at the top of the spawn prompt, ahead of every other
sentence that mentions the advisor — the spawn prompt is the one steering
surface with measured effect on Sonnet.

## Context packaging

Everything the advisor learns arrives inside the consult. Each consult
carries its own packet:

- **First consult** — a complete, self-contained packet: the task, the
  actions taken in order, real output, the live decision, and the
  load-bearing excerpts the decision rests on.
- **Later consults** — the delta since the last consult.
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
becomes the task list.

## Consult budget

Two to three consults per task. Every material fork consults the advisor.
Of the two or three, the third is reserved for recovery or reconciliation.

## Advice weight

Advice is binding absent empirical contradiction. A conflict between the
executor's own evidence and the advisor's guidance goes back to the advisor
as a reconcile consult. See `advisor-tool.md` §How to treat advice for the
full weighing rule.

## Long-run reminder

On a run past roughly 20 advisor-free turns, the executor re-reads its
advisor rules before the next substantive step — the re-read keeps the
advisor visible across a long horizon.

## Failure branches

- **Transient advisor failure** — retry once, then carry on with the
  evidence in hand and record the gap in the result.
- **Advisor unreachable** — report upward and hold the decision for the
  owning session; re-binding belongs to that session alone.

## Pairing invariant

The advisor binds at or above the strongest consumer's tier. The floor
holds at that tier whichever executor joins the pairing.

## Related

| Doc | Holds |
|---|---|
| `advisor-tool.md` | Canonical consult cadence, hard rule, brevity cue |
| `~/.claude/_shared/advisor/advisor-protocol.md` | Host bind, model floor, and the Advisor block parts — transport preambles, shared core, weak-executor add-on |
| `skills/team-advisor/reference/advisor-docs-review.md` | Distilled source facts behind each section above |
