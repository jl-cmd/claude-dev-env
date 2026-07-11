# Obsidian Vault Context

An Obsidian vault stores session reports (`sessions/`), decisions (`decisions/`), and research (`Research/`) across projects. Resolve its location via the obsidian MCP tools — `mcp__obsidian__search_notes` (supports `searchFrontmatter: true`), `mcp__obsidian__read_note`, `mcp__obsidian__read_multiple_notes` — never assume an OS path.

IMPORTANT: Before substantive project work, search the vault for prior sessions and decisions for the current project — by `project` frontmatter first, then keywords ("blocked", "superseded", "decision", "gotcha"). Also search when touching a component with known history or when a task might repeat or reverse a prior decision.

Session logging runs through `/session-log` (same full flow for short and long sessions); offer it at the end of substantive sessions. Reports include `vault_context_retrieved: true|false` and `session_id` (from `CLAUDE_CODE_SESSION_ID`; literal `unknown` when unset) in frontmatter, and every session log ends with a `/rename [Project] - [Primary Outcome]` command — mandatory output, never optional.
