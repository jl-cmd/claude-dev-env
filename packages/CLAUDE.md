# packages

This directory holds the npm packages that ship the Claude Code configuration to users.

## Contents

| Entry | Description |
|---|---|
| `claude-dev-env/` | The sole package — installs rules, hooks, agents, commands, scripts, and skills into `~/.claude/` |

## Role in the monorepo

`packages/claude-dev-env` is the install target users reach via `npx claude-dev-env`. The monorepo root hosts shared config (`config/`, `AGENTS.md`) that is not installed into `~/.claude/`.
