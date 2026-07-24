# Development Assistant

## Advisor consultation

When the `advisor()` tool is available, reference `docs/references/advisor-tool.md`. For complex tasks, always reference `docs/references/team-advisor-skill.md` and use the `/team-advisor` skill.

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

## Documentation

Describe only the current system state. Keep documentation self-contained and free of historical, transitional, conversational, or version-transition language. Never use negative prose or antipatterns. Always state what to do, specifically.

Follow:

- `~/.codex/rules/no-historical-clutter.md`
- `~/.codex/rules/self-contained-docs.md`
- `~/.agents/skills/condensing-instructions/SKILL.md`

## Files and workspaces

Put all work in a new isolated worktree:  `C:/dev/.codex/worktrees/`.

Code and tests

Tests must exercise real behavior, real data, and production paths.

For multi-step code tasks:

Assign each scope to a Luna coder.
Coders consult a warm & reusable tool-less code-advisor when blocked (Sol xHigh).
A warm & reusable code-verifier runs named gates, baseline checks, and a two-way task-to-diff review.
Repair only reported findings.
Re-verify after every repair.

Do not commit, push, or open a PR until verification is clean and verified_commit_gate covers the current diff.
The verification requirement is waived only for a non-code diff or when the Python AST is unchanged after removing docstrings.
Keep changes within scope. Prefer durable systemic fixes for reusable behavior. Do not rewrite entire files or rename public parameters without need.

Reviews and convergence
Report only findings verified against the code.
Verify every sub-agent file list, count, description, and finding against the repository and diff.

Do not commit untracked files unless explicitly instructed.

Research and delegation
Delegate fact extraction when multiple files or search patterns are required. Request precise file-and-line answers.

Use warm & reusable parallel luna (you decide effort level per task) fast subagents for unrelated questions; threaded & named appropriately.

Read or search directly only in files you will modify via es.exe.

For code navigation, prefer Serena and es.exe, then content search or globbing.

Scope every es.exe search.

Never scan an entire drive or network share.

Task tracking
Track every task using using `update_plan` ; "C:/Users/example/.agents/skills/task-build/SKILL.md".

Repository rule
Before changing skill, rule, or hook installation in claude-code-config, read:
docs/references/skill-install-system.md

## Definitions
Warm agent: Any agent who has acted within the past 30 minutes.
