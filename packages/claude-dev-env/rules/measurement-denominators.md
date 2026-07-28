# Measurement Denominators

**When this applies:** Any count, rate, or coverage figure you report — in a chat reply, a PR body, a review comment, a docstring, or a `.md` file.

## Rule

Every count names what it scanned. "Read 10 of 10 changed files" states the scan and the whole set it was drawn from. "Swept the files" states neither, and a reader takes it as full coverage of a scan that touched a fraction.

Three parts travel with each figure. The report author writes part 1 for every figure and part 2 when the figure is a rate; the consumer runs part 3:

1. **A count carries its denominator.** Name both numbers: files read of files changed, rounds fired of rounds available, tests reached of tests collected, entries compared of entries present.
2. **A rate needs two runs and a stated denominator.** One run yields a count. Written down as a rate — "fires 40% of the time" — it claims a spread across runs that one run cannot back. Report the count and the run that produced it until a second run exists.
3. **The consumer cross-checks the count against the scope its denominator names.** A sweep reporting 3 files read of 10 changed fails arithmetic; a sweep reporting 3 of 3 security-sensitive files states its own scope and passes. That arithmetic settles the sweep before anyone reads its result.

A number written into a docstring or a doc carries its denominator beside it. A number written there as a rate carries its run count too.

## Shapes

| Bare figure | With its denominator |
|---|---|
| swept the files | read 10 of 10 changed files |
| all tests pass | 412 of 412 collected tests pass, 0 skipped |
| the hook catches this | the hook denies 6 of 6 recorded shapes |
| fails about 40% of the time | failed twice across 5 runs on this branch |
| most entries match | 88 of 90 entries match |

## Cross-check at the consumer

A sweep reports "read 3 files". The change under review touches 10 files. The arithmetic reads: the sweep covered 3 of 10, so its clean verdict covers 3 of 10. The gap is the finding — send the sweep back for the other 7, and hold the verdict until the two numbers meet.

## Sibling rules

| Rule | Role |
|---|---|
| `falsify-before-green.md` | A check's green counts once the check was shown red |
| `anti-corollary-tests.md` | Each test carries information; no corollary matrices; no suite that only matches the dead default |
| `docstring-prose-matches-implementation.md` | A docstring enumeration covers every behavior the body applies |
| `measurement-denominators.md` | Every count names what it scanned; a rate needs two runs |

## Enforcement

This rule binds as prose discipline: a reviewer applies it to the counts a PR's prose and docstrings state, and to the counts a report claims. No hook backs it, because weighing a figure's denominator against the scope it covers needs meaning a regex cannot read.
