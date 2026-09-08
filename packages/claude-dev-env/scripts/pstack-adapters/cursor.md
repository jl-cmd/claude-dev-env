# Cursor

Use Cursor's available native skill and delegation tools. The installed component-prefixed names in release.json replace upstream plugin short names. Keep project skills under .claude/skills and use the .agents/skills links for shared discovery. The installer writes no skills under .cursor.

For an upstream custom agent type absent from the live tool inventory, use an available native agent type and include that upstream agent definition, the skill entry, and compatibility files in the child prompt. Use the session's supported model identifiers and delegation fields. Preserve required panel independence and model diversity.

Use Cursor's built-in create-skill when present. Otherwise read cde-create-skill. Keep Cursor-specific preferences separate from Claude and Codex preferences. Resolve transcripts from the current workspace and session context.
