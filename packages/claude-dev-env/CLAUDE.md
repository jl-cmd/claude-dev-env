# Claude Development Assistant

Canonical behavior policy lives in `~/.claude/system-prompts/software-engineer.xml`.

## Canonical Pointers

- Code quality rules: `~/.claude/docs/CODE_RULES.md` (pointer to `<code_quality>`)
- Git workflow: `~/.claude/rules/git-workflow.md` (pointer to `<git_workflow>`)
- Development protocol: `<behavior_protocol>` in the system prompt; lean rule `~/.claude/rules/bdd.md`; on-demand `bdd-protocol` skill
- Tool usage and workflow: `<tool_usage>` and `<agent_workflow>` in the system prompt

## Additional Non-overlapping Rules

- Prompt workflow controls: `@~/.claude/rules/prompt-workflow-context-controls.md`
- Testing quality specifics: `@~/.claude/rules/testing.md`
- Path-scoped Tasklings preferences load automatically via `~/.claude/rules/tasklings-preferences.md`