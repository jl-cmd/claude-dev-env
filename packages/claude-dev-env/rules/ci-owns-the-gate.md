# CI Owns the Gate

**When this applies:** Before pushing a branch, and any time a repository's full
check suite or policy gate is about to run on your own machine.

## Rule

The gate runs once, and it runs on CI. Push the branch, read the verdict, act on
what it says.

The inner development loop stays yours. Run the single test you are writing, as
often as it helps. That is how the change gets built. This rule governs the
second full pass, the one whose only product is a prediction of CI's answer.
Push instead, and spend the wait on the next piece of work.

## Why

**A pinned gate answers only from its pinned revision.** The workflow names an
exact revision of the policy package, and that revision decides which rules run.
The copy under your home directory is a separate artifact at its own revision. A
run against the home copy reports on those rules, which are a different question
from the one CI asks. Treat its exit code as information about the home copy
alone.

**Self-hosted runners often share your machine.** Where the runners execute on
the same host as your shell, a local suite run draws its processor time from the
runners, and it does so while they work on the branch you just pushed. Read
where the runners live, and count a local run against the same budget.

**One authoritative answer beats two.** Where both runs agree, the second one
restated the first. Where they differ, the environments differ, and CI is the
environment that decides.

## Running a gate locally

Clone the revision the workflow pins, then point the gate at that clone. That
run asks CI's question and its answer carries. Report a local result by naming
the revision it used, so a reader can tell which question it answered.

## The verdict belongs to CI

CI decides whether a change passed, from evidence CI gathered. Keep that loop
closed. A flag, trailer, receipt, or environment variable through which the
change under test announces its own result hands the verdict to the subject.
Where the runner and the agent share one host, a signature names the same party
twice, so it carries the claim no further.

A cache stays available on one condition. CI derives the key itself from the
tree it is about to test, looks for a previous run under that key, and
republishes that result. CI computes, CI verifies, CI decides.

## Sibling rules

| Rule | Role |
|---|---|
| [`git-workflow.md`](git-workflow.md) | Confirm each required context fired after the push |
| [`verify-runtime-state.md`](verify-runtime-state.md) | A status field is a report; read the thing the work was meant to make |
| [`falsify-before-green.md`](falsify-before-green.md) | A green counts as evidence once the check has run red on a deliberate break |
