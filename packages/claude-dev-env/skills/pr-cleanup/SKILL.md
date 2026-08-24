---
name: pr-cleanup
description: >-
  Clean pull requests through isolated preflight, one-agent cleanup, and strict
  parent-to-child promotion. Triggers: /pr-cleanup, run PR cleanup, full PR
  cleanup, extraction audit, capability naming audit, simplify and review a PR,
  split a cleaned PR, parent Ready, child Ready.
---

# PR cleanup

## Contents

- [Principle](#principle)
- [Gotchas](#gotchas)
- [When this applies](#when-this-applies)
- [Composition](#composition)
- [Task seeding](#task-seeding)
- [Process](#process)
- [Finish report](#finish-report)
- [File index](#file-index)
- [Folder map](#folder-map)

## Principle

One coding agent owns the cleanup outcome. Parallel preflight work runs in
isolated worktrees and produces findings, tested proposals, and evidence for
the cleanup owner. Parent-to-child promotion uses exact commit ancestry and
fresh child-head checks.

## Gotchas

- Preflight worker changes stay in isolated worktrees. Keep parent branch
  operations unavailable until the strict promotion gate.
- Parent promotion uses the exact `parent_ready_sha`. Prove that SHA is an
  ancestor of the child head.
- Child promotion carries fresh validation. Reapply the relevant preflight
  fixes and rerun tests, `e-simplify`, and `e-code-review` on the new child
  head.
- Finish reports carry every actionable finding with an applied fix or exact
  disposition before promotion.

## When this applies

Use this skill for a pull request that needs extraction, capability-oriented
naming, cleanup and review convergence, and a focused child increment.

Required input: a PR URL, number, or branch. If the target is missing, respond
exactly: `Give a GitHub PR number or URL for pr-cleanup.`

Use the repository that owns the target PR. Keep the parent and child PRs in
draft state until their applicable Ready gate is complete.

## Composition

The parent session keeps one coding agent as the cleanup owner. It invokes the
named skills below. Preflight workers may run in parallel isolated worktrees;
the cleanup owner selects and reapplies their tested proposals.

| Skill | When | Produces | Missing behavior |
|---|---|---|---|
| `shared-extraction-audit` | Preflight and parent cleanup | Placement findings and tested extraction proposal | Record the unavailable audit and ask for direction before promotion |
| `name-by-capability-audit` | Preflight and parent cleanup | Capability-oriented naming findings and tested rename proposal | Record the unavailable audit and ask for direction before promotion |
| `e-simplify` | Preflight and child confirmation | Cleanup findings and applied or dispositioned fixes | Record the unavailable pass and hold the affected Ready gate |
| `e-code-review` | Preflight and child confirmation | Correctness findings, fixes, and clean review evidence | Record the unavailable review and hold the affected Ready gate |
| `small-cl` | After parent convergence | Focused child boundary or keep decision | Record the unavailable scope decision and ask for direction |

## Task seeding

At skill start, register every item in `reference/task-seeds.md` as a session
task through `TaskCreate`, `TodoWrite`, or the host task equivalent. Work from
that task list. Mark each task complete with `PASS`, `FAIL` plus file and line
evidence, or `N/A` plus the reason.

## Process

### 1. Resolve the target

Resolve the PR, repository, parent head SHA, and intended child boundary. Record
the immutable parent preflight SHA before creating worktrees.

### 2. Run parallel preflight

Create one isolated worktree per preflight stream from the recorded parent SHA.
Run the extraction audit, capability-name audit, `e-simplify`, and
`e-code-review` in parallel when their skills and workers are available.
Proposed fixes may be tested and recorded in those isolated worktrees.

The preflight parent scope is read-only. Parent merge, parent rebase, parent
push, and parent Ready changes are unavailable during this phase. Report the
worker worktree, base SHA, findings, proposed patch SHA or diff, and validation
evidence for every stream.

### 3. Keep one cleanup owner

The parent session's one coding agent reviews the preflight results, applies
the selected extraction, naming, simplify, and review fixes in the parent
cleanup worktree, and validates each changed surface. Use the composed skills by
name. Keep the parent PR draft through this phase.

### 4. Complete the parent Ready gate

Apply or disposition every actionable preflight finding. Run scoped tests and
the required cleanup and review confirmations on the parent head. When the
parent evidence is complete, promote the parent to Ready and record its exact
remote `parent_ready_sha`.

### 5. Promote a child from the exact parent

Create the child from its intended pre-parent base, then merge the exact
`parent_ready_sha`. Before child promotion, run
`git merge-base --is-ancestor <parent_ready_sha> <child_head>` and require exit
code `0`. A different result holds promotion and requires ancestry repair.

Reapply each relevant preflight fix to the child. Run the child tests, then
rerun `e-simplify` and `e-code-review` against the new child head. Record the
new head SHA and every validation result.

Promote the child to Ready only after the ancestry proof, reapplication record,
tests, and fresh simplify/review evidence are complete.

### 6. Report the result

Report the parent and child PRs, each exact head SHA, preflight streams and
worktrees, findings applied or dispositioned, validation commands and outcomes,
Ready states, and any hard block. Keep the report factual and concise.

## Finish report

Include:

- `parent_pr`, `parent_ready_sha`, `child_pr`, and `child_ready_sha`
- preflight streams, isolated worktree paths, findings, and proposal SHAs
- fixes applied or exact dispositions
- ancestry command and exit code
- tests, `e-simplify`, and `e-code-review` results for the parent and child
- `parent_ready`, `child_ready`, and `hard_block`

## File index

| Path | Purpose |
|---|---|
| `SKILL.md` | Hub for one-agent cleanup, isolated preflight, and strict promotion |
| `reference/task-seeds.md` | Ordered session tasks for every cleanup and promotion gate |
| `reference/process-inventory.md` | Process classification, evidence homes, and paired task checks |

## Folder map

- `SKILL.md` — skill hub and routing contract.
- `reference/` — task seeds and process inventory.
