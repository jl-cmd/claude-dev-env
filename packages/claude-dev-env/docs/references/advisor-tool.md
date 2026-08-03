# Advisor Tool

Canonical consult timing and weight for any stronger-reviewer path: the native `advisor()` tool, `/team-advisor`, and the shared warm advisor.

Source bones: [Anthropic Advisor tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool) (Suggested system prompt for coding tasks). API shape, model pairs, cost, and caching live there. This file carries only the call rules a session needs every time.

## What it is

`advisor()` is a no-parameter review call. The platform forwards the full conversation (task, tool calls, results) to a stronger model. The executor continues with that guidance.

When `advisor()` is absent, use `/team-advisor` (see `team-advisor-skill.md`).

## When to call

Call **before substantive work** — before writing, before locking an interpretation, before building on an assumption.

If the task needs orientation first (find files, fetch a source, see what exists), do that, then call. Orientation is not substantive work. Writing, editing, and declaring an answer are.

Also call:

- **When you believe the task is complete.** Before this call, make the deliverable durable: write the file, save the result, commit the change. The call takes time; if the session ends during it, a durable result survives and an unwritten one does not.
- **When stuck** — errors recur, approach does not converge, results do not fit.
- **When considering a change of approach.**

On tasks longer than a few steps, call at least once before committing to an approach and once before declaring done. On short reactive tasks where the next action is dictated by tool output you just read, you do not need repeated calls — most value is on the first call, before the approach hardens.

Call for design, architecture, and risk questions where you will not touch a file. If the response would be analysis or a recommendation with no other tool calls, call first. That judgment is where a second opinion is highest value. Simple factual lookups and arithmetic do not need a call.

## Hard rule

Your first write, edit, or state-changing shell call on a task must be preceded by an advisor call in the same or an earlier turn. Read-only orientation (`ls`, `cat`, `grep`, `find`, and harness equivalents) is not state-changing. This is a checkpoint, not a difficulty judgment. It applies to one-line edits too.

## How to treat advice

Give the advice serious weight. If a step fails empirically, or primary-source evidence contradicts a claim (the file says X, the paper states Y), adapt. A passing self-test is not evidence the advice is wrong — it is evidence the test does not check what the advice is checking.

If your data points one way and the advisor points another: do not silently switch. Surface the conflict in one more call — "I found X, you suggest Y, which constraint breaks the tie?" A reconcile call is cheaper than the wrong branch.

## Brevity cue

When the consult path supports a free-text brief, append:

`(Advisor: please keep your guidance under 80 words — I need a focused starting point, not a comprehensive plan.)`

## Related

| Doc | Holds |
|---|---|
| [Anthropic Advisor tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool) | API shape, model pairs, cost, caching, full best practices |
| `team-advisor-skill.md` | Standing warm advisor when `advisor()` is missing |
| `~/.claude/_shared/advisor/advisor-protocol.md` | Host bind, floor walk, lifecycle, executor paste blocks |
| `weak-executor-advisor.md` | Consult deltas for an executor spawned below the advisor's own tier |
