---
paths:
  - "**/*.md"
  - "**/*.py"
  - "**/*.mjs"
  - "**/*.js"
  - "**/*.ts"
  - "**/*.ps1"
  - "**/*.sh"
---

# Documentation Inventory Integrity

A doc that inventories code is a contract: a reader trusts the listing to map the directory, trusts a shown command to run, and trusts a table row to name the file that reads the variable. Three repository checks hold the three inventory shapes in step with the code. No write-time hook runs them. Run `python packages/claude-dev-env/scripts/repository_policy.py` before you commit, and CI runs the same command.

## 1. A per-directory `CLAUDE.md` names files that exist

Every bare filename a per-directory `CLAUDE.md` names points at a file in the subtree that `CLAUDE.md` describes — both the filenames its table cells list and the scripts its fenced run commands invoke (`python script.py`). Add the row and the run command in the change that adds the file; drop both in the change that removes it.

`repository_checks/claude_md.py` scans every tracked `CLAUDE.md` in the committed tree and reports each orphan it holds, loading its detection logic from `claude_md_orphan_file_blocker.py`. It reads committed files rather than a pending write, so it reports a pre-existing orphan alongside a new one.

It collects two kinds of reference:

- **Table cells** — the first column of each markdown table row **outside** a fenced code block, keeping cells that name a bare filename in backticks, with no path separator, not a slash-command, ending in a known extension (`.py`, `.md`, `.json`, `.mjs`, `.js`, `.ts`, `.ps1`, `.cmd`, `.ahk`, `.yml`, `.yaml`, `.sh`, `.txt`, `.cfg`, `.toml`, `.ini`).
- **Run commands** — each line **inside** a fenced code block that invokes an interpreter (`python`, `python.exe`, `python3`, `node`, `pwsh`, `powershell`, `bash`, `sh`, `ruby`, `perl`) on a script, taking that script's basename when it ends in `.py`, `.mjs`, `.js`, `.ts`, `.ps1`, `.sh`, `.rb`, or `.pl`.

A fenced *table row* is an example and contributes nothing; a fenced *run command* is a contract the reader runs and is checked. The write is blocked when a collected filename exists nowhere under the scan root — the `CLAUDE.md` directory's parent, covering the directory, its subdirectories, and its siblings. A filesystem error that halts the subtree walk fails open.

The check stays quiet for a target that is not a `CLAUDE.md`, for a cell holding a path, a subdirectory ending in `/`, or a slash-command, for a table row inside a fence, for an inline `python x.py` mention outside a fence, and for a table naming an explicit relative-path source (a `../` token), which documents files outside the subtree by design.

## 2. A package inventory names each new production file

A package directory that documents its own files in a `README.md` Layout table, a `CLAUDE.md` "Key files" list, or a skill `SKILL.md` Layout table keeps that inventory in step with the directory. A new production file in such a directory gets its entry — a table row or a list bullet naming the file in backticks and saying what it does — in the same change.

`repository_checks/package_inventory.py` scans the committed tree and reports a production file whose basename appears in no present inventory, loading its detection logic from `package_inventory_stale_blocker.py`. It names the fix. A skill `SKILL.md` Layout table that maps `scripts/` counts as the inventory for files in that subdirectory.

Two free-prose slices stay with judgment and belong in the same change:

1. **Purpose / scope sentence.** When the new module adds a responsibility the package `## Purpose` (or the parent inventory's one-line summary of the subdirectory) omits, broaden that sentence to name it. A hook cannot derive a module's responsibility from its filename.
2. **Per-file description clause.** When a file gains a responsibility the inventory's em-dash description omits — a new public function, a new module-level constant — broaden the clause to name it. The gate checks only that the basename appears once and never reads the description. Constants modules (`*_constants.py`, or any `.py` directly inside `config/`) are the common shape: the clause that lands in the module docstring lands in the inventory description in the same change. The gate fires on Write of a new file and skips files directly inside `config/`, so an Edit adding a constant to an existing config module matches neither path.

This is the `category-o-docstring-vs-impl-drift` (O8) orphaned-doc-claim shape applied to a package inventory.

## 3. An env-var table row names a file that reads the variable

Every row in an env-var summary table pairs an UPPER_SNAKE variable with a code-file path that reads it — written as `` | `GOOGLE_APPLICATION_CREDENTIALS` | `auth/google_auth.py` | … | ``. When a code change removes the last read of a variable from a file, the same change drops or corrects the row naming that file.

`repository_checks/env_var_documentation.py` scans tracked `.md` files and reports a row whose named code file exists yet never references the variable, loading its detection logic from `env_var_table_code_drift_blocker.py`. It names the fix. A row whose code file resolves nowhere stays quiet, since the check cannot prove the drift.
