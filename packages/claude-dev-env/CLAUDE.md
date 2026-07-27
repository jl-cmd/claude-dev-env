# Development Assistant

## Communication

Reply shape and length: follow `~/.claude/rules/eli11-replies.md`. Word choice: follow `~/.claude/rules/plain-language.md`. State claims affirmatively.

## Security

Collect credentials through secure UI only; never request secrets in chat.

A runtime value that is itself private — a host, an SSH user or port, an owner scope, an account ID — lives in git-ignored local configuration with a committed placeholder in its place. Source files never carry the real value.

## Advisors

When the `advisor()` tool is available, read `~/.claude/docs/references/advisor-tool.md`. For complex tasks use the `/team-advisor` skill.

## Files and workspaces

Put all work in an isolated worktree under the repo's `.claude/worktrees/`.

## Code and tests

Tests must exercise real behavior, real data, and production paths.

Keep changes within scope. Prefer durable systemic fixes for reusable behavior.

Do not rewrite entire files or rename public parameters without need.

## Reviews

Verify every sub-agent file list, count, description, and finding against the repository and diff.

Do not commit untracked files unless explicitly instructed.

## Delegation

Request precise file-and-line answers from research subagents.

## Task tracking

Track multi-step work with the `task-build` skill.

## Repository rule

Before changing skill, rule, or hook installation in the claude-dev-env repo, read `docs/references/skill-install-system.md`.

## Definitions

Warm agent: active within the past 59 minutes.
