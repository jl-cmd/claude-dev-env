# Agent Spawn Guidance

Before any Agent or Task tool spawn, check context sufficiency: you can name the files involved, the constraints, and what success looks like, and the task is unambiguous. When you cannot, investigate or ask the user first — a spawn with incomplete context returns work you throw away.

Ask each research subagent for precise file-and-line answers. A finding that names a path and a line number is one a reader can check.

`/prompt-generator` is recommended for a complex spawn, or one whose output the user reads directly: feed it the goal, the target files, the constraints, the output format, and the acceptance criteria, then use its output as the agent's `prompt`. Inside a scoped autonomous run, an inline structured prompt you write yourself is fine.

Full step detail and the relationship to other rules: `@~/.claude/docs/agent-spawn-protocol.md`.
