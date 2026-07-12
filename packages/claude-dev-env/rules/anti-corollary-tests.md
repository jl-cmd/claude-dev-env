---
paths:
  - "**/test_*.py"
  - "**/*_test.py"
  - "**/*.test.*"
  - "**/*.spec.*"
  - "**/conftest.py"
  - "**/tests/**"
---

# Anti-Corollary Tests

**When this applies:** Any Write or Edit that adds or changes tests.

## Rule

A large green suite can prove almost nothing. Before you keep a case, answer three questions. If any answer fails, cut the case or replace it with one that carries information.

## The three questions

### 1. Is this a corollary?

When the code reduces each input to a canonical form and then compares the forms, every pairwise combination of input spellings follows once the reduction is proven canonical. Walking the full N×N matrix restates that fact. It adds cases and runtime, and it buries the few cases that carry information.

**Do this:** test the reduction once. Test the comparison with a few discriminating cases. Do not walk the cross product of spellings.

### 2. Could this test pass if the mechanism were dead?

Name the degenerate value a dead implementation would return — empty string, `None`, `False`, a blanket refusal, an empty collection. When the test's expected value equals that default, the test passes whether the mechanism works or not. On its own it proves nothing.

**Do this:** keep at least one case that expects the **non-default** answer, and drive the real code path — not a mock that only records that a call happened.

### 3. What single change to the code would make this test fail?

When the honest answer is "none," or "only a change that also breaks everything else," the test is decoration. Drop it or rewrite it so one named mutation kills it.

## What a mechanism with a degenerate failure mode needs

1. **At least one non-default case** that exercises the live path and expects the non-default answer.
2. **A stated mutation (audit lane):** name one specific change to the code and record how many tests it kills. A mutation that kills zero tests means the suite proves nothing. A reviewer or an audit skill checks this; a hook does not compute it.
3. **A few discriminating cases** in place of a large matrix.

## Worked shape (sanitized)

A write guard decides whether a write is about to hit a production database. It reduces each database URL to a canonical endpoint identity, then compares identities.

Two independent mutations show the two halves of a useful suite:

- Gut the reduction so it always returns the empty string: the guard fails **closed** and refuses everything. Only the *allow*-expecting cases die.
- Abandon the reduction and compare raw hostnames: the guard fails **open** and allows a production write. Only the *refuse*-expecting cases die.

Opposite breaks kill opposite halves. A suite with only one half cannot see one of those breaks. Build both halves; skip the spelling matrix once the reduction is covered.

## What this is not

A structural hook is the wrong tool here. "Is this a corollary?" and "would this pass against a dead implementation?" need the intent of the code under test. A hook that pattern-matches `parametrize` breadth or counts assertions fires on correct suites and trains people to ignore it. A false-positive gate on a judgment call is worse than no gate. This rule stays judgment-only, with the stated-mutation check in the audit lane — the same pattern as other judgment rules in this package that have no Write/Edit blocker.

## Sibling rules

| Rule | Role |
|---|---|
| `tdd.md` | Write a failing test before production code |
| `testing.md` | Mocks and test infrastructure standards |
| `paired-test-coverage.md` | Every public function in an established suite gets a behavioral test |
| `anti-corollary-tests.md` | Each test carries information; no corollary matrices; no suite that only matches the dead default |

## Enforcement

The AI review lane and audit skills carry this rule: an agent applies it to the test lines a PR changes. No blocking hook backs it, because corollary and dead-default judgments need meaning a regex cannot read.
