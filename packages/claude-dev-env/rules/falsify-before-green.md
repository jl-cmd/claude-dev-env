# Falsify Before Green

**When this applies:** Any new test, probe, concurrency harness, sweep, mutation check, or measurement script, before its green counts as evidence.

## Rule

A check's green counts as evidence only after that same check ran red on a deliberate break, with a paired control that passes beside it. The break is named: a mutation applied to the code, a stubbed-out target, or a trip input built to fire the check.

A green with no shown red is an unmeasured result, not a pass. Apply the break, watch the check fail, then trust the green. A check that stays green under its own break reads nothing about the code, and its number carries no weight.

## The four shapes this stops

### 1. A probe whose trigger condition never fires

The probe reports zero because it measured zero events, not because the code is clean. Its counter sits at its start value for the whole run.

**Break to apply:** feed it one input that must trip it. A probe still at zero on that input measures nothing.

### 2. A sweep that reads a subset of the files it claims to cover

The sweep compares against the wrong base, walks a slice of the tree, and reports its finding count over the full set.

**Break to apply:** plant one violation in a file the sweep's coverage claim names. A sweep that misses the plant walks a smaller file set than the one it reports.

### 3. A mutation that survives

The test meant to kill the mutation never reaches the mutated code — a mock stands in for the call, a guard returns early, or the test drives a neighboring branch.

**Break to apply:** hold the mutation in place and run the test. A green test names a line nothing covers.

### 4. An assertion that counts an artifact the harness seeded

The harness writes the row, file, or event the assertion counts, so the assertion tracks the harness rather than the code under test.

**Break to apply:** stub the production writer to a no-op. A green assertion counts the seed.

## What a shown-red record holds

| Part | What it names |
|---|---|
| The break | The mutation, stub, or trip input applied, named by file and line or by the exact input text |
| The red | The failing output the check printed under that break |
| The control | The case that passes beside the red, run on the same command |

All three land together. A record carrying the red alone shows a check that fails on everything; a record carrying the control alone shows a check that passes on everything.

## Sibling rules

| Rule | Role |
|---|---|
| `anti-corollary-tests.md` | Each test carries information; the stated mutation names one code change and how many tests it kills |
| `verify-runtime-state.md` | A runtime verdict rests on a live probe from this session |
| `measurement-denominators.md` | Every count names what it scanned; a rate needs two runs |

## Enforcement

This rule binds as prose discipline: a reviewer reads the shown-red record beside each new check a PR adds. No hook backs it, because a green that measured the code and a green that measured nothing look the same to a regex — the difference sits in what the check reached at run time.
