# Portable converge driver

**Rule: deterministic control is script-only.** Phase transitions, wait delays,
clean stamps, ready decisions, task lists, and “what next” never live as prose
for the agent to invent. The agent runs scripts, reads JSON, and only performs
judgment steps the JSON names.

## Step 1 — task list (every autoconverge / portable run)

```
python "$HOME/.claude/skills/_shared/pr-loop/scripts/build_converge_task_list.py" \
  [--bugbot-down 0|1] [--copilot-down 0|1] \
  [--codex-down 0|1] [--codex-required 0|1]
```

Register every `tasks[]` entry on the session task list. **Final task id is
always** `all_runnable_reviews_clean_same_head`. The run is complete only when
that final task is completed: every runnable code review is CLEAN on one
shared HEAD. Do not invent tasks in prose.

`open-run` embeds the same list (`tasks`, `runnable_review_ids`,
`final_task_id`, `done_when`).

## Pacer selection

```
python "$HOME/.claude/skills/_shared/pr-loop/scripts/select_converge_pacer.py" \
  --skill <pr-converge|autoconverge> \
  --has-workflow <0|1> \
  --has-schedule-wakeup <0|1>
```

When `pacer` is not `portable`, use the skill’s native Workflow or
ScheduleWakeup path. When `pacer=portable`, use the control script below.

## Isolation and worktree

1. When the tool list includes `EnterWorktree`, call it (same contract as the
   Claude-host skills).
2. When `EnterWorktree` is absent, isolate with git worktree machinery:
   - Prefer an existing worktree already on the PR head ref under
     `.claude/worktrees/` (or another dedicated worktree path).
   - Otherwise `git fetch origin <headRefName>` and
     `git worktree add <path> <headRefName>` (or `gh pr checkout <N>` into a
     dedicated directory), then `cd` into that checkout.
3. Confirm the working directory is the PR’s own repo on the PR head SHA:
   `python "$HOME/.claude/skills/_shared/pr-loop/scripts/preflight_worktree.py" --owner <O> --repo <R> --mode strict`.
   Non-zero exit → report the `ABORT` line and stop.
4. Cross-repo routing follows pr-converge Step 1.5: every local review and edit
   runs with cwd set to the **PR worktree**.

`open-run` runs the same strict preflight before seeding state.

## Control script

```
python "$HOME/.claude/skills/_shared/pr-loop/scripts/portable_converge_driver.py" <command> ...
```

Stdout JSON: `status`, `next`, `phase`, `state_file`, optional `commands`,
`wait_seconds`, `blocker`, and on `open-run` the task-list fields. Exit `0` =
ok; `1` = contract failure; `2` = usage error.

| Command | Deterministic effect |
|---|---|
| `open-run` | Require `portable`; preflight; seed state + task list; next=`run_code_review` |
| `after-code-review` | From returncode / dirty_tree / served_command |
| `after-bugteam` | From pushed / converged |
| `after-bugbot` | From classification / inline lag |
| `after-codex` | From classification clean / dirty / down |
| `after-copilot-wait` | From review surfaced / wait cap |
| `after-ready-check` | From check_convergence exit |
| `show-state` | Echo state; rehydrate `commands` / `wait_seconds` for pending next |

## Continuous tick loop

After transport check, PR scope, isolation, permission grant, and the once-per-run
Copilot quota pre-check:

1. Seed or restore state via `open-run` or `show-state` (and handoff
   `state-copy.json` when resuming).
2. Run the driver command for the current step; read JSON `next` / `commands` /
   `wait_seconds`.
3. On non-terminal `next`:
   - Write state and handoff when the after-* payload says so.
   - If `next` is `poll_wait`, sleep `wait_seconds` only, then re-poll and call
     the matching after-*.
   - If `next` is immediate work, continue in the same turn without sleeping.
4. On `mark_ready` / `stop_blocked` / named stop: run lifecycle Close, print the
   entry skill’s exit block, omit further pacing.
5. External reviewers remain skippable the same way as Claude-host runs when
   opted out or down. Push and head-change reset push-invalidated markers
   (`*_clean_at`, `merge_state_status`, `bugbot_down`, `codex_down`).

## Agent loop (judgment only)

1. Run the driver command for the current step.
2. If JSON `commands` is non-empty, run that argv (scripted helper).
3. Map JSON `next` to the single judgment action; report back via the matching
   `after-*` command.
4. Mark session tasks complete only when the scripted stamps say so; complete
   the final task only when every runnable review is clean on the same HEAD.

| `next` | Agent does | Report with |
|---|---|---|
| `run_code_review` | Run `commands` | `after-code-review` |
| `apply_fixes_and_push` | Fix protocol; commit; push | re-review then `after-code-review` |
| `run_bugteam` | resolve_worker_spawn / bugteam body | `after-bugteam` |
| `run_bugbot_gate` | Bugbot helper scripts | `after-bugbot` |
| `run_codex_review` | Run Codex review step | `after-codex` |
| `request_copilot_review` | Request Copilot | `after-copilot-wait` |
| `poll_wait` | Sleep `wait_seconds` only | re-poll then after-* |
| `check_ready` | Run `commands` (check_convergence) | `after-ready-check` |
| `mark_ready` | Run `commands` (`gh pr ready`) | teardown |
| `stop_blocked` | Teardown; print blocker | stop |

## Autoconverge entry on portable pacer

When `/autoconverge` selects `pacer=portable`:

- Complete autoconverge pre-flight (scope, draft ownership, strict worktree,
  grant, Copilot quota).
- Drive the continuous tick loop above (scripted phase machine) until ready
  or a documented blocker.
- Skip `Workflow({ scriptPath: converge.mjs })` — that path requires the
  Workflow tool.
- Teardown uses the lifecycle Close path; the Workflow-only closing HTML
  journal report is optional and skipped when no workflow run id exists.
- Resume command on handoff: `/autoconverge <PR URL>`.

When `/autoconverge` selects `pacer=workflow`, follow the skill’s Workflow
sections unchanged.

## Helpers (scripted)

| Concern | Script |
|---|---|
| Task list | `build_converge_task_list.py` |
| Pacer | `select_converge_pacer.py` |
| Worktree | `preflight_worktree.py` |
| Code review | `$HOME/.claude/scripts/invoke_code_review.py` |
| Workers | `$HOME/.claude/scripts/resolve_worker_spawn.py` |
| Ready | `pr-converge/scripts/check_convergence.py` |
| Handoff | `write_handoff.py` |

## Fail closed

Never abort solely because Workflow or ScheduleWakeup is missing once
pacer=`portable`. Fail closed on contract failures only: auth, worktree,
unresolvable gates, and wait caps.
