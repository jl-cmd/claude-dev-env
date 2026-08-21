# Failure Blast Radius

**When this applies:** Batch code that processes assets, rows, accounts, messages, or files where one member can fail while the others are fine.

## Rule

A check that raises decides two things at once: that a condition requires action, and what stops because of it. Name the second one.

An exception type ending in `RunFatal` says the whole run stops. An exception type ending in `ItemBlocked` says this one member stops and the batch carries on. Every raise reached through per-member work uses one or the other.

Define `RunFatal` outside the `ItemBlocked` inheritance branch. The per-member boundary routes `ItemBlocked` to parking, while a `RunFatal` escalation passes straight through to the run-level branch.

## What ends a run

Four failures end a run, and they share one property: continuing compromises delivery integrity.

Three of them are declared, and carry a `RunFatal` type:

- The source bytes changed under the run.
- A provenance or digest comparison failed.
- Authentication is required.

The fourth is a runtime crash, such as `TypeError` or `AttributeError`. Its runtime type reaches run-level handling because the per-member boundary recognizes the contract's named types.

All remaining failures are member failures. A size mismatch, an optional input error, a path resolution error, or a manifest-field error each stops one member while the batch continues with its other members.

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

The re-raise comes first, sending an escalation directly through the boundary.

**The boundary recognizes declared types.** A runtime crash inside member work — a `TypeError`, an `AttributeError` — ends the run because its type identifies a code defect. `except Exception` triggers the rule (`CODE_RULES.md` §31).

## Repair, park, and the deliverable

An agent that hits a member failure keeps working the problem. Three things bound how:

- **Repair in place.** The current run preserves every completed member.
- **Three real attempts, then park.** An attempt is a theory of the cause, acted on. Re-running the same code on the same input counts as one attempt. Three theories cover the obvious cause, the second guess, and the cause revealed by the first two attempts. Judgment selects each theory; the third attempt sets the stopping point. After the third theory fails, park the member with its reason and move to the next. Parked members return after the batch.
- **The batch always reaches a deliverable.** Complete every member that can complete, produce the packaged artifact, then work the parked list. A run with 34 of 37 members complete and 3 parked records progress and continues to delivery.

## Three alike means one cause

When three or more members park with the same failure signature — same exception type, same `file:line` — one shared defect affects all three members. Route repair to the shared cause.

The run report groups parked members by that signature and names every group of three or more as a suspected shared cause. The raise site provides a reliable grouping key and removes message-text normalization.

## Close the run with every outcome

Every issue the run hit gets one line in the closing report: what failed, and how it ended — repaired, worked around, or parked. Members that finished after a repair belong in that list beside the parked ones. A workaround patched past mid-run is the likeliest real defect in the batch, because the closing report becomes its durable record.

The report then presents each candidate to the owner for a durable-fix decision, names the fixes the run recommends, and waits for the answer. The next run builds the selected fix; the current run completes its deliverable first.

## Enforcement

`code_rules_blast_radius.py` (PreToolUse on Write and Edit, hosted by `code_rules_enforcer.py`) requires each raised type written directly inside a loop body to end in `RunFatal` or `ItemBlocked`. The lexical check covers raises written directly in loop bodies. Shared helpers carry multiple caller contexts, so their callers classify the boundary.

Findings use baseline content for each edit. A raise present on disk remains accepted during the edit; the gate evaluates newly written raises.

## Excerpt for repository-instruction sessions

Codex reads its repository `AGENTS.md`; this excerpt supplies the standalone failure-handling contract.

```
Failure handling for this run — from rules/failure-blast-radius.md.

Keep solving problems. You own the fix. Each blast radius sets the repair
scope, and the deliverable remains the run priority.

Repair in place and preserve every completed asset in the current run.

Three real attempts, then park. An attempt is a theory of the cause, acted
on. Repeated execution of one theory remains one attempt.
Three theories cover the obvious cause, the second guess, and the cause
revealed by the first two attempts. Use your judgment to select each theory;
the third attempt sets the stopping point. After the third theory fails, park
the asset with its reason and continue. Parked assets return after the batch.

The batch always reaches a deliverable. Finish every asset you can, produce
the packaged artifact, then work the parked list.

When three or more assets fail the same way, one shared defect affects all
three assets. Route repair to the shared cause.

Four things end a run outright: the source bytes changed, a provenance or
digest mismatch, authentication is required, or the code crashed with a
runtime failure that requires run-level handling. Work every other failure. The
named-type boundary defines the accepted exception handling; broad `except`
handling triggers the rule.

When you add a check that raises, name what it stops. End the type in
RunFatal when the whole run stops, or ItemBlocked when a single asset
stops. For an asset-level stop, put the handling inside the loop body.

Close the run by reporting what broke and what you did about it. Every issue
gets one line: what failed, and how it ended — repaired, worked around, or
parked. Include the ones you solved; a workaround you patched past in attempt
two is the likeliest real defect in the list, because the closing report becomes
its durable record.
Present each candidate for the owner's durable-fix decision, state which fixes
you recommend and why, and wait for the answer. The next run builds the
selected durable fix after this run completes its deliverable.

Report as: N of M complete, K parked, and what you are working now.
Close with: what broke, how each one ended, and which of them deserve a
durable fix.
```

## Sibling rules

| Rule | Role |
|---|---|
| [`code-standards.md`](code-standards.md) | `CODE_RULES.md` §9.7 names the boundary that turns a recorded per-member failure into an explicit outcome |
| [`confirm-implementation-forks.md`](confirm-implementation-forks.md) | A defect correction creates an implementation fork when it routes around parking; surface and decide that fork |
| [`long-horizon-autonomy.md`](long-horizon-autonomy.md) | A parked member receives an explicit report entry and follow-up |
