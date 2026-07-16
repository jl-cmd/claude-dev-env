# Workers Done Before Complete

Before marking a task `completed` that spawned workers — subagents, workflow agents, or background shells — confirm both: every worker has finished, and each worker's result is merged into run state (`state.json`, `pr-converge-state.json`, the task list, or whatever record the task keeps). A worker still running, or one whose output never landed in run state, keeps the task `in_progress`: list the live workers, report any dead or hung one as a finding rather than dropping it in silence, and schedule a wakeup so the run picks the workers back up before the task closes.

Checklist, examples, and run-state detail: `@~/.claude/docs/worker-completion-gate.md`.
