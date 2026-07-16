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
| `show-state` | Echo state; rehydrate `commands` when next=`run_code_review` |

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
