# Handoff prompt template

The closing session prints this prompt in chat. The user pastes it into a cloud session that opens PRs for the filed issues and drives them to convergence. The prompt is computed from the filed set — the safety lines, base branch, verification commands, and dependency order are read at runtime, not guessed.

## Contents

- [Shape](#shape)
- [How to compute each block](#how-to-compute-each-block)
- [Worked example](#worked-example)

## Shape

```markdown
# Cloud handoff — <parent issue owner/repo#N>

## Task
Open a PR per filed issue below and drive each to convergence.

## Safety — never do these
- Never run, merge, deploy, or sync the <working repo> pipeline. It is live in production.
- Never run the host repo's automations.
- <any repo-specific never line read from the target CLAUDE.md>

## Base branch and verification
- Base branch: <base>
- Per-package verification commands:
  - <package A>: <command>
  - <package B>: <command>

## Issues, in dependency order
1. owner/repo#<N> — <title>. <cloud-doable? yes / no + why>.
2. owner/repo#<N> — <title>. Depends on #<N> landing first.
3. owner/repo#<N> — <title>. Touches the same files as #<N>; stack on one branch, do not run in parallel.

## Cannot be done from a cloud session
- owner/repo#<N> — needs <local environment / physical device / private network>. Scope the cloud work to <what a cloud session can reach>.
```

## How to compute each block

- **Safety lines** — read the working repo's CLAUDE.md and docs for the pipeline, deploy, and sync commands the cloud session must never run. Name each one.
- **Base branch** — read it live from the target repo (its default branch), not from memory.
- **Verification commands** — read the per-package test and check commands from the target repo's CLAUDE.md or docs. List one line per package a filed issue touches.
- **Dependency order** — for each pair of issues, decide: does one need the other's change to land first? Do they touch the same files? Same-file issues stack on one branch; independent issues run in parallel.
- **Cloud reachability** — for each issue, decide whether a cloud session can do the work. An issue needing a local environment, physical devices, or a private network is marked, and the cloud work is scoped to the reachable part.

## Worked example

```markdown
# Cloud handoff — jl-cmd/claude-dev-env#100

## Task
Open a PR per filed issue below and drive each to convergence.

## Safety — never do these
- Never run, merge, deploy, or sync the claude-dev-env publish pipeline. It is live in production (publishes to npm).
- Never run the host repo's automations.
- Never hand-edit .cursor/BUGBOT.md; it is generated from AGENTS.md.

## Base branch and verification
- Base branch: main
- Per-package verification commands:
  - claude-dev-env (JS): cd packages/claude-dev-env && npm test
  - claude-dev-env (Python): python -m pytest packages/claude-dev-env

## Issues, in dependency order
1. jl-cmd/claude-dev-env#101 — inline-collection gate fires in exempt test files. Cloud-doable: yes.
2. jl-cmd/claude-dev-env#102 — boolean-naming gate flags a fixture variable. Touches the same file as #101 (code_rules_enforcer.py); stack on one branch with #101, do not run in parallel.

## Cannot be done from a cloud session
- None. Both issues are pure hook-logic changes with local pytest coverage a cloud session can run.
```
