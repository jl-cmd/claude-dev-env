# Portable converge driver

Shared pacer path for `/pr-converge` and `/autoconverge` when the host has no
Claude-native pacer. One converge product: same phase machine, same helpers,
same `check_convergence.py` ready definition. The host only changes **how**
the loop advances, not **whether** it may run.

## Pacer selection

Before pre-flight, scan the tool list and select a pacer. The helper makes the
rule mechanical:

```
python "$HOME/.claude/skills/_shared/pr-loop/scripts/select_converge_pacer.py" \
  --skill <pr-converge|autoconverge> \
  --has-workflow <0|1> \
  --has-schedule-wakeup <0|1>
```

Stdout is one JSON object with `pacer` one of:

| `pacer` | When | How the loop advances |
|---|---|---|
| `workflow` | `autoconverge` and tool list includes `Workflow` | `workflow/converge.mjs` via the Workflow tool |
| `schedule_wakeup` | `pr-converge` and tool list includes `ScheduleWakeup` | One tick per invocation; next tick via `ScheduleWakeup` |
| `portable` | Native pacer for that skill is absent | This document: continuous in-session ticks |

Fail closed only when the PR or repo contract cannot be met (auth, wrong
worktree, unresolvable gates). **Never** abort solely because `Workflow` or
`ScheduleWakeup` is missing.

Both entry skills remain valid on a portable host: `/autoconverge` and
`/pr-converge` each complete when invoked. On `pacer=portable`, both drive the
same continuous tick loop below. Autoconverge's Claude-host Workflow path and
its parallel-lens round shape stay available when `Workflow` is present.

## What the portable path reuses

| Concern | Source of truth |
|---|---|
| Phase machine (CODE_REVIEW → BUGTEAM → BUGBOT → gates → ready) | `pr-converge/SKILL.md` progress checklist + `pr-converge/reference/per-tick.md` |
| Code-review lens | `python "$HOME/.claude/scripts/invoke_code_review.py" --cwd <PR-worktree> --session-model <alias>` (ThirdParty → Claude chain) |
| Bugteam audit / fix workers | `bugteam` skill; workers via `resolve_worker_spawn.py` (Grok headless, then Claude headless on third-party) |
| Fix commit, push, reply, resolve | `_shared/pr-loop/fix-protocol.md` + skill deltas |
| External gate opt-out / down | `CLAUDE_REVIEWS_DISABLED`, `--bugbot-down`, `--copilot-down`, `--codex-down`, `reviewer-gates` |
| Ready definition | `pr-converge/scripts/check_convergence.py` exit 0, then mark ready. That script shells out to `gh`; it needs a working `gh` in the session. On a cloud host without `gh`, either build a fixture snapshot from MCP reads and pass `--fixture`, or apply the `pr-loop-cloud-transport` readiness equivalent before mark-ready. |
| Open / close | `pr-loop-lifecycle` |
| Durable resume | `write_handoff.py` under `~/.claude/runtime/pr-loop/` |

Do not invent ad-hoc review or fix spawns when these helpers exist.

## Session bound (honest limit)

A portable run lives inside **one agent session**. There is no durable
host-level wake outside that session. Budget and context therefore bound how
many ticks complete before a handoff.

- Drive ticks continuously while budget covers a full clean tick (same rule as
  pr-converge budget-aware boundaries).
- When budget does not cover another full tick, **stop at a tick boundary**:
  write `pr-converge-state.json`, write the durable handoff, print the resume
  command (`/pr-converge <PR URL>` or `/autoconverge <PR URL>`), and end.
- `check_convergence.py` re-derives readiness from live PR state. A fresh
  session that resumes from handoff does not trust a prior "clean" claim
  without re-running the gate on the live HEAD.
- Wait phases (Bugbot CI, Copilot review surface) use **in-session poll** at the
  same delays the ScheduleWakeup path uses (`360` seconds default; `90` seconds
  on the Bugbot inline-lag branch). When the session cannot hold a long poll,
  write handoff and stop rather than skipping the wait and inventing a clean.

## Isolation and worktree

1. When the tool list includes `EnterWorktree`, call it (same contract as the
   Claude-host skills).
2. When `EnterWorktree` is absent, isolate with git worktree machinery:
   - Prefer an existing worktree already on the PR head ref under
     `.claude/worktrees/` (or another dedicated worktree path).
   - Otherwise `git fetch origin <headRefName>` and
     `git worktree add <path> <headRefName>` (or `gh pr checkout <N>` into a
     dedicated directory), then `cd` into that checkout.
3. Confirm the working directory is the PR's own repo on the PR head SHA:
   `python "$HOME/.claude/skills/_shared/pr-loop/scripts/preflight_worktree.py" --owner <O> --repo <R> --mode strict`.
   Non-zero exit → report the `ABORT` line and stop.
4. Cross-repo routing follows pr-converge Step 1.5: every local review and edit
   runs with cwd set to the **PR worktree**.

## Continuous tick loop

After transport check, PR scope, isolation, permission grant, and the once-per-run
Copilot quota pre-check:

1. Seed or restore state (`pr-converge-state.json` and/or handoff `state-copy.json`).
2. Run **one full tick** from the pr-converge progress checklist for the current
   `phase` (CODE_REVIEW entry each new HEAD after a fix push).
3. On tick exit that needs another tick (non-terminal):
   - Write state and handoff.
   - If the next step is a **wait** (Bugbot queued, COPILOT_WAIT with no review
     yet), poll in-session for the configured delay, then continue at the same
     step; honor the same hard caps (`copilot_wait_count >= 3`, Bugbot down
     detection, etc.).
   - If the next step is **immediate work**, continue in the same turn without
     sleeping.
4. On convergence (`check_convergence.py` exit 0 + mark ready) or a named
   stop condition: run `pr-loop-lifecycle` Close, print the entry skill's exit
   block, omit further pacing.
5. External reviewers remain skippable the same way as Claude-host runs when
   opted out or down.

## Autoconverge entry on portable pacer

When `/autoconverge` selects `pacer=portable`:

- Complete autoconverge pre-flight (scope, draft ownership, strict worktree,
  grant, Copilot quota).
- Drive the continuous tick loop above (pr-converge phase machine) until ready
  or a documented blocker.
- Skip `Workflow({ scriptPath: converge.mjs })` — that path requires the
  Workflow tool.
- Teardown uses the lifecycle Close path; the Workflow-only closing HTML
  journal report is optional and skipped when no workflow run id exists.
- Resume command on handoff: `/autoconverge <PR URL>`.

When `/autoconverge` selects `pacer=workflow`, follow the skill's Workflow
sections unchanged.

## Exit shapes

Portable runs print the entry skill's final report block:

```
/pr-converge exit: converged|blocked
Loops: <N>
Final commit: <SHA>
```

or

```
/autoconverge exit: converged|blocked
Rounds: <N>
Final commit: <finalSha>
Blocker: <blocker>   # only when blocked
```

A blocked exit names a contract or gate blocker (auth, worktree, hard
mergeability, wait cap, budget handoff) — never "tool missing."
