# Obsidian Vault Context

An Obsidian vault at `C:\Users\jon\SessionLog\` stores session reports, decisions, and research documents across all projects.

## Available MCP Tools

- `mcp__obsidian__search_notes` -- search by content or frontmatter (`searchFrontmatter: true`)
- `mcp__obsidian__read_note` -- read a single note by path
- `mcp__obsidian__read_multiple_notes` -- read several notes at once

## Vault Structure

- `sessions/` -- session reports with frontmatter: `type: session-report`, `project`, `session`, `date`, `status`, `blocked`, `tags`
- `decisions/` -- decision notes with frontmatter: `type: decision|procedural|fact|gotcha`, `project`, `date`, `status: Active|Superseded`, `tags`
- `Research/` -- deep research documents

## When to Search

IMPORTANT: Before starting substantive project work, search the vault for prior sessions and decisions for the current project. Also search when:
- Encountering a component or system with known history
- A task might repeat or reverse a prior decision
- You need context on why something was built a certain way

Search by `project` frontmatter field first, then by content keywords like "blocked", "superseded", "decision", "gotcha".

## Session Logging

When the user invokes `/session-log`, treat **short and long sessions the same**: run the full logging flow. Session length does not change the requirements below.

At the end of substantive sessions, offer to run `/session-log` if not already invoked.

When running `/session-log`, include `vault_context_retrieved: true|false` in frontmatter based on whether vault MCP tools were used this session.

After writing a session log, ALWAYS output a `/rename` command with a descriptive session name based on the session's primary outcome. Format: `/rename [Project] - [Primary Outcome]`. This is a mandatory output requirement, not optional.
