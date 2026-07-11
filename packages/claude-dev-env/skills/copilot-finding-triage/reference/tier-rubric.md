# Tier Rubric

Every Copilot finding on the round's HEAD sorts into one of two tiers. The tier
decides who acts: the run fixes a self-healing finding on its own, and the run
pages the user for a code concern.

## The two tiers

| Tier | Who acts | Page the user | Counts toward convergence |
|------|----------|---------------|---------------------------|
| SELF-HEALING | The run auto-fixes | No | Yes |
| CODE CONCERN | The user decides | Yes | Held until the user answers or the deadline passes |

## The test that splits them

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

## When a finding sits on the line

A finding that touches both tiers sorts to CODE CONCERN. Any doubt about whether
a fix stays behavior-safe routes the finding to the user gate. The safe default
pages a person; it never auto-fixes a finding that might change runtime behavior.
