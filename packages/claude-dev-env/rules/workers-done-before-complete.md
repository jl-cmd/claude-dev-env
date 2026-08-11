# Workers Done Before Complete

Before marking a task `completed` that spawned workers — subagents, workflow agents, or background shells — confirm both: every worker has finished, and each worker's result is merged into run state (`state.json`, `pr-converge-state.json`, the task list, or whatever record the task keeps). A worker still running, or one whose output never landed in run state, keeps the task `in_progress`: list the live workers, report any dead or hung one as a finding rather than dropping it in silence, and schedule a wakeup so the run picks the workers back up before the task closes.

This rule gates a task's status, not your own work. It never says wait before acting: keep working while a worker runs, and hold only the `completed` mark until the worker's result has landed.

Verify every sub-agent file list, count, description, and finding against the repository and the diff before you merge it into run state or repeat it to the user.

Checklist, examples, and run-state detail: `@~/.claude/docs/worker-completion-gate.md`.
