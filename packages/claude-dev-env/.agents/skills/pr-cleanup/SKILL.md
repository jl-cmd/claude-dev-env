---
name: pr-cleanup
disable-model-invocation: true
description: >-
  Refine pull requests through parallel placement and capability-name audits,
  focused delivery sizing, and a final simplify and code-review loop. Triggers:
  /pr-cleanup, run PR cleanup, full PR cleanup, extraction audit, capability
  naming audit, simplify and review a PR, and split a cleaned PR.
---

# PR cleanup

## Contents

- [Principle](#principle)
- [When this applies](#when-this-applies)
- [Composition](#composition)
- [Task seeding](#task-seeding)
- [Process](#process)
- [Promotion gates](#promotion-gates)
- [Finish report](#finish-report)
- [File index](#file-index)

## Principle

One coding agent owns the cleanup outcome. `pr-refinement` coordinates parallel
preflight audits and produces findings, tested proposals, a combined change map,
and a delivery decision for the cleanup owner. Parent-to-child promotion uses
exact commit ancestry and fresh child-head checks.

## When this applies

Use this skill for a pull request that needs placement review, capability
naming, cleanup convergence, and a focused delivery boundary.

Required input: a pull request URL, number, or branch. If the target is missing,
respond exactly: `Give a GitHub PR number, URL, or branch for pr-cleanup.`

Use the repository that owns the target pull request. Keep every pull request in
draft state until its applicable Ready gate is complete. Keep merge authority
with the user.

## Composition

| Skill | Role | Evidence |
|---|---|---|
| `pr-refinement` | Run the parallel audits, combine findings, and coordinate implementation shape | Change map and delivery decision |
| `pr-shared-extraction` | Find reusable behavior that belongs in `shared_utils` | Placement findings and tested proposal |
| `pr-name-by-capability` | Find driver or motive words on reusable capability surfaces | Naming findings and rename directions |
| `pr-small-cl` | Choose one coherent pull request or an ordered replacement stack | Focused boundary and dependencies |
| `source-command-sr-loop` | Run `e-simplify`, then `e-code-review low --fix` until clean | Review passes, fixes, and validation |
| `pr-summarizer` (repo-local) | When the repository under cleanup ships `.claude/skills/pr-summarizer/`, run it after Ready and post the secret-gist preview comment | Preview URL and comment confirmation |

## Task seeding

At skill start, register every item in `reference/task-seeds.md` as a session
task through `TaskCreate`, `TodoWrite`, or the host task equivalent. Work from
that task list. Mark each task complete with `PASS`, `FAIL` plus file and line
evidence, or `N/A` plus the reason.

## Process

### 1. Resolve the target

Resolve the pull request, repository, parent head SHA, and intended child
boundary. Record the immutable parent preflight SHA before creating worktrees.

### 2. Run `pr-refinement`

Run [pr-refinement](../pr-refinement/SKILL.md). Record its combined change map,
audit findings, locations, priorities, destinations or rename directions,
validation evidence, and worker worktrees.

### 3. Choose the delivery shape

Use [pr-small-cl](../pr-small-cl/SKILL.md) after the audit findings are
combined. Record the first pull request boundary, dependencies, tests, and
follow-up work.

### 4. Implement the selected shape

Apply every actionable finding in dependency order. Keep preflight parent scope
read-only until the cleanup owner selects and reapplies tested proposals.
Validate each changed surface with its production-path tests. Commit each
validated concern and keep the resulting pull request in draft state.

### 5. Run `source-command-sr-loop`

Run [source-command-sr-loop](../source-command-sr-loop/SKILL.md). Record the
review passes, fixes, skips, tests, and commit SHAs.

### 6. Promote and report

After the applicable gate passes, when the repository under cleanup includes
`.claude/skills/pr-summarizer/SKILL.md`, load and run that skill for each pull
request promoted to Ready in this cleanup run. Post the secret gist preview as a
pull request comment before completing the [Finish report](#finish-report).

When the skill is absent, record `N/A` for the summary step and continue.

## Promotion gates

Run preflight work in isolated worktrees from the recorded parent SHA. Apply
selected changes in the parent cleanup worktree after the owner selects the
tested proposals.

Promote the parent only after every actionable finding has an applied fix or an
exact disposition. Record the remote parent Ready state and exact
`parent_ready_sha`.

Create the child from its intended pre-parent base and merge the exact
`parent_ready_sha`. Prove that SHA is an ancestor of the child head with
`git merge-base --is-ancestor <parent_ready_sha> <child_head>` and record exit
code `0`.

Reapply every relevant fix to the child. Rerun child tests, `e-simplify`, and
`e-code-review` after the merge. Record the new child head and every validation
result before promoting the child to Ready.

When the repository ships `pr-summarizer`, run it on the child after child Ready
promotion if the child is in scope for this cleanup run.

Use `reference/task-seeds.md` and `reference/process-inventory.md` to record promotion evidence.

## Finish report

- Pull request or stack URLs.
- `pr-refinement` outcome.
- `source-command-sr-loop` passes, commits, and validation results.
- Parent-ready and child-ready SHAs when a child is promoted.
- `pr-summarizer` preview URLs and comment confirmation for each Ready pull request, or `N/A` when the repo does not ship the skill.
- Remaining hard block, or `null`.

## File index

| Path | Purpose |
|---|---|
| `SKILL.md` | Hub for refinement, cleanup convergence, promotion gates, and reporting |
| `reference/task-seeds.md` | Ordered session tasks for audits, delivery, validation, promotion, and summary |
| `reference/process-inventory.md` | Process classes, evidence homes, and paired task checks |
