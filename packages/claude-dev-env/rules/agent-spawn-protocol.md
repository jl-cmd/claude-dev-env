# Agent Spawn Protocol (Mandatory)

Before any Agent or Task tool spawn (Explore, implementation, research, or team subagents):

1. **Check context sufficiency** — you can name the files involved, the constraints, and what success looks like, and the task is unambiguous. When you cannot, investigate or ask the user first; do not spawn with incomplete context.
2. **Craft the prompt with `/prompt-generator`** — feed it the goal, the target files from step 1, the constraints, the output format, and the acceptance criteria; use its output as the agent's `prompt`.
3. **Spawn** with that structured prompt.

Full step detail, rationale, and relationship to other rules: `@~/.claude/docs/agent-spawn-protocol.md`.
