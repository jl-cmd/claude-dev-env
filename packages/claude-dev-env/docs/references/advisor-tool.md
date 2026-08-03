# Advisor Tool

Canonical consult timing and weight for the repository custom advisor path: `/team-advisor` and the shared warm advisor. Native `advisor()` documentation supplies the source guidance for packet shape and review timing.

Source bones: [Anthropic Advisor tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool) (Suggested system prompt for coding tasks). API shape, model pairs, cost, and caching live there. This file carries only the call rules a session needs every time.

## What it is

`advisor()` is the native reference model: the platform forwards the full conversation to a stronger model. This repository uses `/team-advisor` to reproduce that review contract when the native tool is unavailable or outside the selected execution path.

`/team-advisor` carries the full first packet explicitly, sends later deltas, and owns the warm Agent/SendMessage or read-only Sol CLI lifecycle (see `team-advisor-skill.md`).

## When to call

Call **before substantive work** — before writing, before locking an interpretation, before building on an assumption.

If the task needs orientation first (find files, fetch a source, see what exists), do that, then call. Orientation is not substantive work. Writing, editing, and declaring an answer are.

Also call:

- **When you believe the task is complete.** Before this call, make the deliverable durable: write the file, save the result, commit the change. The call takes time; if the session ends during it, a durable result survives and an unwritten one does not. Ask the advisor to hunt for missing requirements, untested behavior, wrong assumptions, unhandled edge cases, evidence gaps, and early completion claims.
- **When stuck** — errors recur, approach does not converge, results do not fit.
- **When considering a change of approach.**

On tasks longer than a few steps, aim for an early approach consult and a completion review. Reserve a third consult for recovery or reconciliation, and add consults when material new evidence or forks arise. This cadence guides planning and leaves the task free to follow its evidence. Short reactive tasks may use the single consult that best fits the live decision.

Call for design, architecture, and risk questions where you will not touch a file. If the response would be analysis or a recommendation with no other tool calls, call first. That judgment is where a second opinion is highest value. Simple factual lookups and arithmetic do not need a call.

## Hard rule

Your first write, edit, or state-changing shell call on a task must be preceded by an advisor call in the same or an earlier turn. Read-only orientation (`ls`, `cat`, `grep`, `find`, and harness equivalents) is not state-changing. This is a checkpoint, not a difficulty judgment. It applies to one-line edits too.

## How to treat advice

Give the advice serious weight. If a step fails empirically, or primary-source evidence contradicts a claim (the file says X, the paper states Y), adapt. A passing self-test is not evidence the advice is wrong — it is evidence the test does not check what the advice is checking.

If your data points one way and the advisor points another: do not silently switch. Surface the conflict in one more call — "I found X, you suggest Y, which constraint breaks the tie?" A reconcile call is cheaper than the wrong branch.

Work a disagreement in this order: keep the observed evidence in the record, name the conflict plainly, ask the advisor which constraint breaks the tie, then act on the reconciled plan.

## Escalation shapes

Four shapes cover how a harder task gets more strength behind it. Route to the one that matches the work, not by default to the advisor.

| Shape | Fits when |
|---|---|
| Advisor | The task needs intermittent strategy and review, and one executor keeps the task from start to finish. |
| Subagent | A piece of the task is a bounded subtask that benefits from its own context and its own loop. |
| Stronger-model planning phase | The plan needs the strong model's judgment; the fast model can carry it out once written. |
| Full model switch | Every step of the task needs the stronger tier, not just the hard decisions. |

Spawn a subagent when the work is a delegable bounded subtask. Switch the whole task to the stronger model when every turn needs that tier.

## Brevity cue

When the consult path supports a free-text brief, append:

`(Advisor: please keep your guidance under 80 words — I need a focused starting point, not a comprehensive plan.)`

Size the ask at roughly 80 percent of the true ceiling; direct address to the advisor lands more reliably than a third-person description.

## Related

| Doc | Holds |
|---|---|
| [Anthropic Advisor tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool) | API shape, model pairs, cost, caching, full best practices |
| `team-advisor-skill.md` | Standing warm advisor when `advisor()` is missing |
| `~/.claude/_shared/advisor/advisor-protocol.md` | Host bind, floor walk, lifecycle — a read map routes each bind or consult moment to its `reference/` detail file |
| `weak-executor-advisor.md` | Consult deltas for an executor spawned below the advisor's own tier |
