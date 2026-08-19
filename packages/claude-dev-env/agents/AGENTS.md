# agents

Agent definition files installed into `~/.claude/agents/` by `bin/install.mjs`. Each `.md` file defines a named subagent: its description (shown in the Claude Code UI), allowed tools, and behavioral instructions.

## Agent files

| File | Agent name | Role |
|---|---|---|
| `clean-coder.md` | Clean Coder | Primary code-writing agent; links the review contract, CODE_RULES, and enforcer; task-local discovery and gate-clean first writes |
| `code-quality-agent.md` | Code Quality Agent | Multi-file code quality review across an entire diff or set of files |
| `git-commit-crafter.md` | Git Commit Crafter | Stages changes, writes conventional commit messages, creates commits |
| `issue-tracker.md` | Issue Tracker | Primary handler for one GitHub issue action per spawn; loads the issue-tracker skill (plain-brief); returns issue numbers and URLs |
| `plan-packet-validator.md` | Plan Packet Validator | Fresh-context validator for workflow-generated plan packets under `docs/plans/` |
| `pr-description-writer.md` | PR Description Writer | Drafts PR descriptions and comments from the current diff using the canonical description and comment guides |
| `session-advisor.md` | Session Advisor | Standing multi-consumer reviewer; SendMessage only; returns endorse/correction/plan/stop |
| `skill-writer-agent.md` | Skill Writer Agent | Authors SKILL.md and companion files to skill-builder conventions; caller-agnostic authoring specialist |

## Format

Each file uses YAML frontmatter (`name`, `description`, `tools`, optional `color`) followed by a Markdown body with the agent's behavioral instructions. The `description` field appears in the Claude Code agent picker. An agent definition carries no `model` key — the caller supplies the model on each spawn.

## Adding an agent

1. Create a new `.md` file in this directory with valid frontmatter.
2. Run `bin/install.mjs` to copy it to `~/.claude/agents/`.
3. Restart Claude Code to pick up the new agent.
