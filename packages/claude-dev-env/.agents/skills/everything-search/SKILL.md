---
name: everything-search
description: Fast file search on Windows using Everything (voidtools) es.exe command-line tool. Use when searching for files by extension, name, date modified, size, or path. Triggers on "find files", "search for files", "locate files", or when user asks to use Everything.
---

# Everything Search

## Overview

Search files instantly on Windows using the Everything command-line interface (es.exe).

**Announce at start:** "I'm using the everything-search skill to find files."

## Hard limits

Every search carries a scope: a project path or registry token, an `ext:` filter, a `dm:` date filter, a `size:` filter, or a name pattern. A bare whole-drive scan or a network-share sweep is out of bounds. Narrow the search to what you need.

When `es.exe` returns Error 8, the Everything IPC client window is missing. Retry the same search twice with a short pause. Do not report that Everything is not running, not loaded, or that the index is unavailable from that first miss. After those retries fail, report that the Everything IPC client did not answer and that the service state was not probed, then fall back to the `Glob` tool (name and path patterns) or `Grep` (file contents) with the same scope.

When `es.exe` is missing, or a later search returns no hits, fall back to `Glob` or `Grep`. A failed search is not proof the index is down. When those fallbacks also fail, ask the user through `AskUserQuestion` with a short analysis and next-step options.

Direct `es.exe` calls use the same Error 8 retry. The wrapper in `scripts/everything_search.py` already retries Error 8 twice.

## Registry tokens

Run project-name searches through this command:

```text
python "${CLAUDE_SKILL_DIR}/scripts/everything_search.py" <project-name> <search arguments>
```

The command reads `~/.claude/project-paths.json`. An exact project name or `{project-name}` argument becomes one absolute path. Unknown names, absolute paths, flags, and spaces stay as they are. The command then starts `es.exe` without a shell.

Put the search scope first. The first argument names a project, path, file, extension, date, or size. An options-only request exits before `es.exe` starts. Use `-version` alone to read the installed Everything version.

Path and operator searches run when the registry file is missing. Malformed registry content, an empty search, a missing `es.exe`, or a process start failure returns a nonzero exit. After a successful start, the command returns the `es.exe` exit status.

## Instructions

### Command Syntax

**Path (WSL):** `/mnt/c/Program\ Files/Everything/es.exe`
**Path (Windows):** `"C:/Program Files/Everything/es.exe"`

**CRITICAL:**
- Search terms are SPACE-SEPARATED, not quoted together
- When searching a path, use backslashes inside quotes: `"Y:\\path\\to\\folder"`

```bash
# CORRECT - WSL format with path search
/mnt/c/Program\ Files/Everything/es.exe "Y:\\path\\to\\folder" searchterm

# CORRECT - space-separated terms
/mnt/c/Program\ Files/Everything/es.exe ext:mp4 dm:last3months

# WRONG - quoted with semicolons (breaks parsing)
/mnt/c/Program\ Files/Everything/es.exe "ext:mp4;mov;avi dm:last3months"
```

### Search Operators

**By Extension:**
```bash
ext:mp4                    # Single extension
ext:mp4 | ext:mov | ext:avi  # Multiple extensions (OR)
```

**By Date Modified:**
```bash
dm:last3months            # Modified in last 3 months
dm:lastweek               # Modified in last week
dm:today                  # Modified today
dm:>=2024-01-01           # Modified on or after date
```

**By Path:**
```bash
/mnt/c/Program\ Files/Everything/es.exe "D:\\Projects\\My App\\assets" ext:mp4
/mnt/c/Program\ Files/Everything/es.exe "D:\\Projects" ext:prproj
```

**By Size:**
```bash
size:>100mb               # Larger than 100MB
size:<1gb                 # Smaller than 1GB
```

**By Name:**
```bash
*.prproj                  # Wildcard match
"exact filename.txt"      # Exact match (quote the filename)
```

### Combining Multiple Extensions

Run separate searches for each extension type:
```bash
/mnt/c/Program\ Files/Everything/es.exe ext:mp4 dm:last3months
/mnt/c/Program\ Files/Everything/es.exe ext:mov dm:last3months
/mnt/c/Program\ Files/Everything/es.exe ext:prproj dm:last3months
```

### Output Options

```bash
# Sort by date modified (descending)
/mnt/c/Program\ Files/Everything/es.exe ext:mp4 dm:last3months -sort dm -sort-descending

# Limit results
/mnt/c/Program\ Files/Everything/es.exe ext:mp4 -n 50

# Show size
/mnt/c/Program\ Files/Everything/es.exe ext:mp4 -size
```

## Examples

### Video files (last 90 days)
```bash
/mnt/c/Program\ Files/Everything/es.exe ext:mp4 dm:last3months
/mnt/c/Program\ Files/Everything/es.exe ext:mov dm:last3months
/mnt/c/Program\ Files/Everything/es.exe ext:avi dm:last3months
/mnt/c/Program\ Files/Everything/es.exe ext:mkv dm:last3months
```

### Premiere projects
```bash
/mnt/c/Program\ Files/Everything/es.exe ext:prproj
/mnt/c/Program\ Files/Everything/es.exe ext:prproj dm:lastmonth
```

### Large files
```bash
/mnt/c/Program\ Files/Everything/es.exe size:>1gb
/mnt/c/Program\ Files/Everything/es.exe ext:mp4 size:>500mb
```

### Config files in a project
```bash
/mnt/c/Program\ Files/Everything/es.exe "Y:\\path\\to\\project" config.py
/mnt/c/Program\ Files/Everything/es.exe "Y:\\path\\to\\project" constants.py
```

## Best Practices

- `es.exe` talks to the Everything tray client IPC window. The Everything service can be running while Error 8 still fires.
- On Error 8, retry the same search twice before treating the search as failed.
- Run one extension per search for cleaner results
- Use `dm:` to filter recent files by the index timestamp
- Combine with path to narrow scope
- Results return instantly regardless of drive size

### Junctions, Symlinks & Drive Mapping

Everything indexes REAL paths only, not junctions or mapped drives.

| Drive | Type | Indexed? | Action |
|-------|------|----------|--------|
| Y:\ | Real NTFS | Yes | Use this path |
| Z:\ | Junction to Y: | No | Use Y:\ instead |

**If search returns empty:**
1. Check if the path is a junction/symlink
2. Find the real path and search that instead
3. Or use Glob tool as fallback (works on any path)

**Common drive mappings:**
- `Z:\Projects\` -> `Y:\Work\Projects\`
- When in Z:\, translate to Y:\ equivalent for Everything searches

## Files

- `scripts/everything_search.py` runs one Everything search without a shell, retries Error 8 twice, and reports that the IPC client did not answer and that the service state was not probed when those retries fail.
- `scripts/test_everything_search.py` verifies registry expansion, command failures, Error 8 retry, and the IPC-client miss message.
