# Failure Blast Radius

**When this applies:** Any code that processes a batch — assets, rows, accounts, messages, files — where one member can fail while the others are fine.

## Rule

A check that raises decides two things at once: that something is wrong, and what stops because of it. Name the second one.

An exception type ending in `RunFatal` says the whole run stops. An exception type ending in `ItemBlocked` says this one member stops and the batch carries on. Every raise reached through per-member work uses one or the other.

`RunFatal` must not inherit from any type the per-member boundary catches, so an escalation passes straight through a boundary meant for member failures.

## What earns RunFatal

Three kinds of failure, and they share one property: continuing produces work nobody can trust.

- The source bytes changed under the run.
- A provenance or digest comparison failed.
- Authentication is required.

Everything else is a member failure. A wrong size, an absent optional input, a path that does not resolve, a manifest field that is missing — each stops one member and leaves the rest of the batch untouched.

## The boundary

Put the `try`/`except` inside the loop body, around the per-member work:

```python
for each_member in all_members:
    try:
        remaster(each_member)
    except AssetRunFatal:
        raise
    except AssetItemBlocked as failure:
        park(each_member, failure)
```

The re-raise comes first so an escalation is never parked.

**The boundary catches named types only.** An unforeseen crash inside member work — a `TypeError`, an `AttributeError` — ends the run, because a crash nobody declared means the code is wrong rather than the member. `except Exception` stays banned (`CODE_RULES.md` §31).

## Repair, park, and the deliverable

An agent that hits a member failure keeps working the problem. Three things bound how:

- **Repair in place, never by restart.** Re-running the batch discards every member that already succeeded, which costs more than the defect.
- **Bound each member, then park it.** Give one failing member a small number of real attempts. If it still fails, park it with its reason and move to the next. Parked is not abandoned — it returns after the batch.
- **The batch always reaches a deliverable.** Complete every member that can complete, produce the packaged artifact, then work the parked list. A run ending with 34 of 37 members and 3 parked beats a run ending on member 3.

## Three alike means one cause

When three or more members park with the same failure signature — same exception type, same `file:line` — that is one shared defect wearing three costumes. Stop repairing members and fix the shared cause.

The run report groups parked members by that signature and names any group of three or more as a suspected shared cause. Grouping on the raise site rather than the message text needs no normalization to be reliable.

## Enforcement

`code_rules_blast_radius.py` (PreToolUse on Write and Edit, hosted by `code_rules_enforcer.py`) flags a raise written inside a loop body whose type names no blast radius. It reads the loop body it is written in, not a call graph, so a raise in a helper the loop calls sits outside its reach — a helper reachable from both per-member and run-level callers cannot be classified from its own text.

Findings baseline against the prior content, so a raise already on disk never blocks an edit. Only a newly written one does.

## Excerpt for a session that loads no rules directory

A Codex session reads its repository `AGENTS.md`, not `~/.claude/rules/`. Paste this into such a session; it stands alone.

```
Failure handling for this run — from rules/failure-blast-radius.md.

Keep solving problems. You own the fix. What changes is where the repair
happens and what it is allowed to hold up.

Repair in place, never by restart. A restart discards every asset that
already succeeded.

Bound each failing asset to a few real attempts, then park it with its
reason and continue. Parked is not abandoned; return to it after the batch.

The batch always reaches a deliverable. Finish every asset you can, produce
the packaged artifact, then work the parked list.

If three or more assets fail the same way, that is one shared defect, not
three. Stop the per-asset repairs and fix the shared cause.

Only three things end a run outright: the source bytes changed, a provenance
or digest mismatch, or authentication is required. Everything else is yours
to work.

When you add a check that raises, name what it stops. End the type in
RunFatal when the whole run stops, or ItemBlocked when only that one asset
stops. If it stops only that asset, put the handling inside the loop body.

Report as: N of M complete, K parked, and what you are working now.
```

## Sibling rules

| Rule | Role |
|---|---|
| [`code-standards.md`](code-standards.md) | `CODE_RULES.md` §9.7 names the boundary that makes a recorded per-member failure something other than swallowing |
| [`confirm-implementation-forks.md`](confirm-implementation-forks.md) | Silently correcting a defect rather than parking it is a fork to surface, not a default |
| [`long-horizon-autonomy.md`](long-horizon-autonomy.md) | A parked member is reported, never dropped in silence |
