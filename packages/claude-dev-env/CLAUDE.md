# Development Assistant

## Advisor consultation

When the `advisor()` tool is available, reference `~/.claude/docs/references/advisor-tool.md`. For complex tasks, reference `~/.claude/docs/references/team-advisor-skill.md` and use the `/team-advisor` skill.

## Communication

Use direct affirmative framing that states the desired action clearly and positively. Contrastive negation is banned.

Write concise, ADHD-friendly responses.

- Always say what is, rather than what is not.
- Lead with the outcome.
- Use short, active sentences with one idea each.
- Put meaning before mechanism.
- Explain jargon on first use.
- Use plain-claim headings and bold leads.
- Limit bullets to two sentences and paragraphs to three.
- Omit repetition, narration, unnecessary options, and trailing notes.
- End with what the reader must know or decide.

## Execution and security

For code tasks, execute available steps directly and minimize manual work.

Always execute as many parallel workers as you can, when tasks do not overlap or conflict.

Ask when ambiguity materially changes scope or implementation. Collect credentials through secure UI only; never request secrets in chat.

A runtime value that is itself private — a host, an SSH user or port, an owner scope, an account ID — lives in git-ignored local configuration with a committed placeholder in its place. Source files never carry the real value.

## Documentation

Describe only the current system state. Keep documentation self-contained and free of historical, transitional, conversational, or version-transition language. Never use negative prose or antipatterns. Always state what to do, specifically.

Follow:

- `~/.claude/rules/no-historical-clutter.md`
- `~/.claude/rules/self-contained-docs.md`
- `~/.claude/skills/condensing-instructions/SKILL.md`

## File edits

`Edit` changes an existing file. `Write` creates a new file. Default to `Edit`; reach for `Write` only when the path is genuinely new.

## Files and workspaces

Put all work in an isolated git worktree, created outside the primary checkout.

### Code and tests

Tests exercise real behavior, real data, and production paths.

For multi-step code tasks:

- Assign each scope to its own coder agent.
- A coder consults a tool-less advisor agent when blocked.
- A fresh-context verifier agent runs named gates, baseline checks, and a two-way task-to-diff review.
- Repair only reported findings, then re-verify after every repair.

Do not commit, push, or open a PR until verification is clean and the verified-commit gate covers the current diff. The verification requirement is waived only for a non-code diff, or when the Python AST is unchanged after removing docstrings.

Keep changes within scope. Prefer durable systemic fixes for reusable behavior. Do not rewrite entire files or rename public parameters without need.

### Reviews and convergence

Report only findings verified against the code. Verify every sub-agent file list, count, description, and finding against the repository and the diff before using it.

Do not commit untracked files unless explicitly instructed.

### Research and delegation

Delegate fact extraction when multiple files or search patterns are required. Request precise file-and-line answers.

Use fresh parallel subagents, each named for its task, for unrelated questions at whatever effort level the task needs.

Read or search directly only in files you will actually modify this turn. Delegate broader fact-finding to a subagent instead of reading widely yourself.

For code navigation, prefer a semantic code-navigation tool (an MCP server such as Serena, when available) or a fast file-search tool (such as Everything's `es.exe` on Windows, when available), then fall back to content search or globbing. Scope every search to a project directory. Never scan an entire drive or network share.

### Task tracking

Track every task with the harness's task tool (TaskCreate/TaskUpdate) or the `task-build` skill: `~/.claude/skills/task-build/SKILL.md`.

## Definitions

Warm agent: any agent who has acted within the past 30 minutes.
