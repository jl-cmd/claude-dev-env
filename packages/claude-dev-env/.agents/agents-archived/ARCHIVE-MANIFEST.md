# Archived agent definitions

These definitions are archived outside the package's active agent tree. Restore
one with the `git mv` command in its row, then restore the named caller and test edits.

| File | Reason | Restore |
|---|---|---|
| `clean-coder.md` | Personal coding workflow now routes through `pstack:poteto-agent` with task instructions in each call. | `git mv packages/claude-dev-env/.agents/agents-archived/clean-coder.md packages/claude-dev-env/.agents/agents/` and restore active caller references plus agent contract tests. |
| `code-quality-agent.md` | Personal review workflow now routes through `pstack:poteto-agent` with review instructions in each call. | `git mv packages/claude-dev-env/.agents/agents-archived/code-quality-agent.md packages/claude-dev-env/.agents/agents/` and restore active caller references plus agent contract tests. |
| `git-commit-crafter.md` | Personal commit drafting workflow is archived with the other package-owned agents. | `git mv packages/claude-dev-env/.agents/agents-archived/git-commit-crafter.md packages/claude-dev-env/.agents/agents/` and restore the model policy entry. |
| `issue-tracker.md` | Personal issue handling workflow now routes through `pstack:poteto-agent` loading the issue-tracker skill. | `git mv packages/claude-dev-env/.agents/agents-archived/issue-tracker.md packages/claude-dev-env/.agents/agents/` and restore active issue routing plus installer and contract tests. |
| `plan-packet-validator.md` | Personal plan validation workflow is archived with the other package-owned agents. | `git mv packages/claude-dev-env/.agents/agents-archived/plan-packet-validator.md packages/claude-dev-env/.agents/agents/` and restore the model policy entry. |
| `pr-description-writer.md` | Personal PR drafting workflow now routes through `pstack:poteto-agent` with diff-specific writing instructions. | `git mv packages/claude-dev-env/.agents/agents-archived/pr-description-writer.md packages/claude-dev-env/.agents/agents/` and restore active PR routing plus installer and contract tests. |
| `session-advisor.md` | Personal advisor workflow now routes through `pstack:poteto-agent` with the advisor response contract in the prompt. | `git mv packages/claude-dev-env/.agents/agents-archived/session-advisor.md packages/claude-dev-env/.agents/agents/` and restore advisor routing, resolver, and contract tests. |
| `skill-writer-agent.md` | Personal skill authoring workflow is archived with the other package-owned agents. | `git mv packages/claude-dev-env/.agents/agents-archived/skill-writer-agent.md packages/claude-dev-env/.agents/agents/` and restore the model policy entry. |
