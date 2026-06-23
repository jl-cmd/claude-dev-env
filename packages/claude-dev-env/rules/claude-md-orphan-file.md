# Orphan File Reference in a Per-Directory CLAUDE.md

**When this applies:** Any Write, Edit, or MultiEdit to a file named `CLAUDE.md` that lists files in a markdown table whose first column names each file in backticks, or that shows run commands invoking those files inside fenced code blocks.

## Rule

Every bare filename a per-directory `CLAUDE.md` names points at a file that exists in the directory subtree the `CLAUDE.md` describes — both the filenames its table cells list and the scripts its fenced run commands invoke (`python script.py`). A table cell or a run command naming a file that exists nowhere in that subtree points a reader at something that is not there: the doc claims a file the directory does not hold.

When you add a table row or a run command, the file it names already exists in this directory or a subdirectory of it. When you remove a file, drop the row and the run command that named it.

## What the gate checks

The `claude_md_orphan_file_blocker.py` hook runs on every Write, Edit, and MultiEdit whose target basename is `CLAUDE.md`. It:

1. Reads the content the tool would leave on disk. For a Write that is the full `content`. For an Edit or MultiEdit it reconstructs the post-edit file — the existing on-disk file with the replacements applied — and also notes which orphans the file already held before the edit, so a pre-existing orphan on an untouched line is excluded and only an orphan the edit introduces is reported; when the existing file cannot be read, it scans the raw `new_string` fragment(s) instead.
2. Collects two kinds of referenced filename. Table cells: the first column of each markdown table row **outside** a fenced code block, keeping cells that name a bare filename wrapped in backticks, no path separator, not a slash-command, ending in a known file extension (`.py`, `.md`, `.json`, `.mjs`, `.js`, `.ts`, `.ps1`, `.cmd`, `.ahk`, `.yml`, `.yaml`, `.sh`, `.txt`, `.cfg`, `.toml`, `.ini`). Run commands: each line **inside** a fenced code block (between a ``` or `~~~` fence pair) that invokes an interpreter (`python`, `python.exe`, `python3`, `node`, `pwsh`, `powershell`, `bash`, `sh`, `ruby`, `perl`) on a script, taking that script's basename when it ends in `.py`, `.mjs`, `.js`, `.ts`, `.ps1`, `.sh`, `.rb`, or `.pl`. A fenced *table row* is an example, not a live listing, so it contributes no table-cell filename; a fenced *run command* is the contract a reader runs, so its script filename is checked.
3. Blocks the write when a referenced filename — from a table cell or a fenced run command — exists nowhere under the scan root — the `CLAUDE.md` directory's parent, which covers the directory, its subdirectories, and its siblings. A filesystem error that halts the whole subtree walk fails open (the write proceeds), so an unreadable tree never blocks a write.

The check stays quiet for a target that is not a `CLAUDE.md`, for a table cell that holds a path, a subdirectory ending in `/`, or a slash-command, for a table row inside a fenced code block, for an inline `python x.py` mention outside a fence (prose, not a runnable contract), and for a table whose content names an explicit relative-path source (a `../` token), since that table documents files that sit outside the subtree by design.

## Why this is a hook, not a lint pass

A table row or a run command that names an absent file reads as a contract: a reader trusts the listing to map the directory and trusts the shown command to run. A wrong row sends the reader looking for a file that is not there; a stale run command fails the moment the reader runs it. Both erode trust in every other entry. Catching them as each line is written keeps the doc and the directory in step.
