# Orphan File Reference in a Per-Directory CLAUDE.md

**When this applies:** Any Write, Edit, or MultiEdit to a file named `CLAUDE.md` that lists files in a markdown table whose first column names each file in backticks.

## Rule

Every bare filename a per-directory `CLAUDE.md` table names in its first column points at a file that exists in the directory subtree the `CLAUDE.md` describes. A first-column cell naming a file that exists nowhere in that subtree points a reader at something that is not there: the listing claims a file the directory does not hold.

When you add a table row, the file it names already exists in this directory or a subdirectory of it. When you remove a file, drop the row that named it.

## What the gate checks

The `claude_md_orphan_file_blocker.py` hook runs on every Write, Edit, and MultiEdit whose target basename is `CLAUDE.md`. It:

1. Reads the content the tool would leave on disk. For a Write that is the full `content`. For an Edit or MultiEdit it reconstructs the post-edit file — the existing on-disk file with the replacements applied — and also notes which orphans the file already held before the edit, so a pre-existing orphan on an untouched line is excluded and only an orphan the edit introduces is reported; when the existing file cannot be read, it scans the raw `new_string` fragment(s) instead.
2. Skips any line inside a fenced code block (between a ``` or `~~~` fence pair), since an example table there is documentation, not a live listing.
3. Takes the first column of each remaining markdown table row and keeps the cells that name a bare filename: wrapped in backticks, no path separator, not a slash-command, and ending in a known file extension (`.py`, `.md`, `.json`, `.mjs`, `.js`, `.ts`, `.ps1`, `.cmd`, `.ahk`, `.yml`, `.yaml`, `.sh`, `.txt`, `.cfg`, `.toml`, `.ini`).
4. Blocks the write when a named file exists nowhere under the scan root — the `CLAUDE.md` directory's parent, which covers the directory, its subdirectories, and its siblings. A filesystem error that halts the whole subtree walk fails open (the write proceeds), so an unreadable tree never blocks a write.

The check stays quiet for a target that is not a `CLAUDE.md`, for a table cell that holds a path, a subdirectory ending in `/`, or a slash-command, for a table row inside a fenced code block, and for a table whose content names an explicit relative-path source (a `../` token), since that table documents files that sit outside the subtree by design.

## Why this is a hook, not a lint pass

A table row that names an absent file reads as a contract: a reader trusts the listing to map the directory. A wrong row sends the reader looking for a file that is not there and erodes trust in every other row. Catching it as each row is written keeps the table and the directory in step.
