---
name: everything-search
description: Fast file search on Windows using Everything (voidtools) es.exe command-line tool. Use when searching for files by extension, name, date modified, size, or path. Triggers on "find files", "search for files", "locate files", or when user asks to use Everything.
---

# Everything Search

## Overview

Search files instantly on Windows using the Everything command-line interface (es.exe).

**Announce at start:** "I'm using the everything-search skill to find files."

## Hard limits

Every search carries a scope: a project path or registry token, an `ext:` filter, a `dm:` date filter, a `size:` filter, or a name pattern. A bare whole-drive scan or a network-share sweep is out of bounds — narrow the search to what you need.

When `es.exe` fails or returns nothing, self-heal first: fall back to the `Glob` tool (name and path patterns) or `Grep` (file contents), and report the outage so the reader knows the index was unavailable. When self-healing also fails, ask the user through `AskUserQuestion` with a short analysis and next-step options.

## Registry tokens

The `es_exe_path_rewriter` hook resolves scope tokens before the command runs. A `{project-name}` placeholder or a bare registry key from `~/.claude/project-paths.json` becomes its quoted absolute path in the command. The hook allows and rewrites — it never blocks — so a search scoped to a registered project names the project token and lets the hook fill in the path.

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

- Everything must be running (system tray) for es.exe to work
- Run one extension per search for cleaner results
- Use `dm:` for recent file searches instead of manual date filtering
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
