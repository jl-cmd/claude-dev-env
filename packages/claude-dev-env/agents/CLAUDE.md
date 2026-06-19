# agents

Agent definition files installed into `~/.claude/agents/` by `bin/install.mjs`. Each `.md` file defines a named subagent: its description (shown in the Claude Code UI), allowed tools, and behavioral instructions.

## Agent files

| File | Agent name | Role |
|---|---|---|
| `caveman.md` | Caveman Agent | Terse voice and smallest-possible artifacts; questions premise before building |
| `clasp-deployment-orchestrator.md` | Clasp Deployment Orchestrator | Creates and deploys Google Apps Script projects with multiple files |
| `clean-coder.md` | Clean Coder | Primary code-writing agent; internalizes CODE_RULES.md and targets zero `/check` findings |
| `code-advisor.md` | Code Advisor | Mid-run advisor for executor agents; returns plans or stop signals — no tools, no edits |
| `code-quality-agent.md` | Code Quality Agent | Multi-file code quality review across an entire diff or set of files |
| `code-verifier.md` | Code Verifier | Post-hoc verification after coder agents finish; read-only, fresh context, ends with a fenced verdict |
| `deep-research.md` | Deep Research | Citation-grounded research with web search |
| `docs-agent.md` | Docs Agent | Documentation authoring and maintenance |
| `git-commit-crafter.md` | Git Commit Crafter | Stages changes, writes conventional commit messages, creates commits |
| `plan-packet-validator.md` | Plan Packet Validator | Fresh-context validator for workflow-generated plan packets under `docs/plans/` |
| `pr-description-writer.md` | PR Description Writer | Authors PR descriptions in Anthropic-style shapes; required by the `pr_description_enforcer` hook |

## Format

Each file uses YAML frontmatter (`name`, `description`, `tools`, optional `color`) followed by a Markdown body with the agent's behavioral instructions. The `description` field appears in the Claude Code agent picker.

## Adding an agent

1. Create a new `.md` file in this directory with valid frontmatter.
2. Run `bin/install.mjs` to copy it to `~/.claude/agents/`.
3. Restart Claude Code to pick up the new agent.
