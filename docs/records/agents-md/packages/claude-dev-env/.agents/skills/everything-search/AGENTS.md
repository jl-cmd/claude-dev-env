# everything-search

Fast file search on Windows using the Everything (voidtools) `es.exe` command-line tool. Triggered by `find files`, `search for files`, `locate files`, or any request to use Everything.

## Purpose

Searches files by extension, name, date modified, size, or path against Everything's real-time index. Returns results instantly regardless of drive size. The skill covers the correct `es.exe` path, search operator syntax, multi-extension patterns, output options, and the junction/symlink note (Everything indexes real NTFS paths only — not junctions or mapped drives).

## Key file

| File | Purpose |
|---|---|
| `SKILL.md` | Command syntax for WSL and Windows paths, all search operators (`ext:`, `dm:`, `size:`, wildcards, OR/AND/NOT), output flags (`-sort`, `-n`, `-size`), worked examples, and a junction/drive-mapping lookup table. |

## When to use

Use for file-system searches by name, extension, size, or date. For content searches use Grep. If a path is a junction or mapped drive and Everything returns nothing, translate to the real NTFS path or fall back to the Glob tool.
