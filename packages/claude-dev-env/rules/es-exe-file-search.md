# File Search Through the es.exe CLI

**When this applies:** Any file-system search on Windows — finding files by name, path, extension, size, or date modified.

## Rule

`es.exe` (the Everything command-line tool) is the file-search tool. Every search carries a scope: a project path or registry token, an `ext:` filter, a `dm:` date filter, a `size:` filter, or a name pattern. A bare whole-drive scan or a network-share sweep is out of bounds — narrow the search to what you need.

Never start, install, or restart the Everything HTTP server. The CLI reads the same index the desktop app keeps; it needs no server.

When `es.exe` fails or returns nothing, fall back to `Glob` (name and path patterns) or `Grep` (file contents), and report the outage so the reader knows the index was unavailable.

## Registry tokens

The `es_exe_path_rewriter` hook resolves scope tokens before the command runs. A `{project-name}` placeholder or a bare registry key from `~/.claude/project-paths.json` becomes its quoted absolute path in the command. The hook allows and rewrites — it never blocks — so a search scoped to a registered project names the project token and lets the hook fill in the path.

## Operator syntax

`skills/everything-search/SKILL.md` holds the full operator reference: `ext:`, `dm:`, `size:`, wildcards, OR/AND/NOT, output flags, and the junction/drive-mapping note.
