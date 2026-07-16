# Worker Completion Gate

Full detail behind the always-on `rules/workers-done-before-complete.md` kernel. It applies before marking any task `completed` when the task spawned workers — subagents, workflow agents, or background shells.

## The gate

A task reaches `completed` only when two things hold: every worker it spawned has finished, and each worker's result is merged into run state — `state.json`, `pr-converge-state.json`, the task list, or whatever record the task keeps. A worker that still runs, or one that finished but whose output never landed in run state, leaves the task open.

List the live workers before you mark the task complete. When a worker is dead or hung, that is a finding to record and report, not a result to drop in silence. A step that waits on workers ends its turn `in_progress` with a wakeup scheduled, so the run picks the workers back up rather than closing the task without them.

## Checklist before marking complete

| Check | Action |
|---|---|
| Are any spawned workers still running? | List them; when yes, stay `in_progress` and schedule a wakeup. |
| Did every finished worker return a result? | Read each result; a dead or hung worker is a finding to report. |
| Is each result merged into run state? | Write it to `state.json` or the task list before closing. |
| Does the task's own goal now hold? | Confirm against the merged state, not a worker's self-report. |

Mark `completed` only when every row passes.

## Examples

**Wrong:** Marking the audit task complete while two bugteam workers still run in the background.
**Right:** List the workers, see two still running, keep the task `in_progress`, and schedule a wakeup to collect them.

**Wrong:** A worker crashes; the task closes as complete because the other workers finished.
**Right:** Record the crashed worker as a finding, report it, and hold the task open until its work is covered.

## Relationship to other rules

- `long-horizon-autonomy` covers acting on what you have and not ending a turn on a promise. This gate names the specific completion condition: workers finished and their results merged.
- `skills/pr-converge/reference/state-schema.md` defines the run-state records a worker's result lands in before the task closes.
