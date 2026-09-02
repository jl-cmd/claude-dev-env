# Tier Rubric

Every Copilot finding on the round's HEAD passes through two stages: tiering,
then — for a code concern — an executed-check verification stage that decides who
acts. Tiering sorts a finding into one of two tiers. The run fixes a self-healing
finding on its own; a code concern goes to a verifier agent, and only a finding
the verifier leaves inconclusive pages the user.

## The two tiers

| Tier | Next step | Page the user | Counts toward convergence |
|------|-----------|---------------|---------------------------|
| SELF-HEALING | The run auto-fixes | No | Yes |
| CODE CONCERN | An executed-check verifier decides | Only when the verifier's verdict is inconclusive | Confirmed and refuted count; inconclusive holds until the user answers or the deadline passes |

## The test that splits the tiers

A finding is SELF-HEALING when its fix cannot change what a production caller
observes at runtime. A finding is a CODE CONCERN when its fix changes runtime
behavior for a production caller or asks for a product decision.

## SELF-HEALING findings

The fix is safe because it leaves runtime behavior the same for every production
caller.

- Pure style: formatting, blank lines, naming.
- Type hints.
- Misplaced or unused imports.
- Magic-value extraction to a named constant.
- Test-only changes: a redundant or tautological test, a test reshape.
- A description or doc that reads differently from the code it describes.
- De-duplicating code that already runs the same way.

## CODE CONCERN findings

The fix changes what a production caller sees, or the call needs a person to
weigh a tradeoff.

- Logic or correctness defects.
- Security issues.
- Data-handling changes.
- Error-handling semantics.
- Concurrency.
- Anything whose fix changes observable production behavior.

A finding that touches both tiers sorts to CODE CONCERN. Any doubt about the tier
sorts the finding to CODE CONCERN.

## The verification stage

Every code-concern finding goes to its own verifier agent, all in parallel,
inside the run. The verifier decides one of three verdicts by executing a check
against the flagged HEAD.

**The governing rule: a verdict is conclusive only if an actual check was
executed.** Reading the source and reasoning about it, however sound, never
produces a conclusive verdict. A check is a concrete command the verifier runs
against the flagged HEAD — executing the flagged code path with crafted inputs,
forcing the claimed error condition, or running a purpose-built test — whose
captured output demonstrates the behavior in question. Source inspection points
the check at the right place; it is never itself grounds for a conclusive verdict.

Each verdict carries `{verdict, checkCommand, checkOutput, evidence}`. A
conclusive verdict whose `checkCommand` or `checkOutput` is empty carries no
executed check, so the run downgrades it to inconclusive.

| Verdict | What the executed check shows | Who acts | Page the user |
|---------|-------------------------------|----------|---------------|
| CONFIRMED | The check tangibly reproduces the defect | The run auto-fixes | No |
| REFUTED | The check tangibly shows the code already behaves correctly in the exact scenario the finding claims is broken | The run replies and resolves | No |
| INCONCLUSIVE | Everything else | The user decides | Yes |

### CONFIRMED

The executed check reproduces the defect; the evidence carries the exact
command(s) and the captured output. Only a confirmed verdict makes a
code-concern finding self-healing. The finding joins the round's fix list
carrying its repro, and the fix:

1. Re-runs the same repro check and shows it passes.
2. Adds the repro to the repo's test suite as a regression test where the suite
   covers that surface.
3. Lands in one commit and pushes.
4. Replies to the thread with the fix SHA plus the before/after check output,
   then resolves the thread.

The loop resumes on its own. No page.

### REFUTED

The executed check demonstrates the code already behaves correctly in the exact
scenario the finding claims is broken. The run replies to the thread with the
command(s) and captured output, resolves the thread, and counts the finding
clean. No page.

### INCONCLUSIVE

Everything else: no runnable check exists, the check is infeasible in this
environment, the results are ambiguous, or the fix needs a product decision
between defensible behaviors. A finding that is not tangibly reproducible is not
self-healing. These findings, and only these, flow into the user gate.

## The default is inconclusive

The verifier defaults to inconclusive. Any doubt sorts to inconclusive, and an
inconclusive finding pages the user. The safe default pages a person; it never
auto-fixes a finding whose behavior an executed check did not pin down.
