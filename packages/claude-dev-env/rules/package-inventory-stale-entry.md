---
paths:
  - "**/*.py"
  - "**/*.mjs"
  - "**/*.js"
  - "**/*.ts"
  - "**/*.ps1"
  - "**/*.sh"
---

# New Production File Absent From Its Package Inventory

A package directory that documents its own files in a `README.md` Layout table, a `CLAUDE.md` "Key files" list, or a skill `SKILL.md` Layout table keeps that inventory in step with the directory. When you create a new production file in such a directory, add an entry naming it — a row in the table or a bullet in the list — in the same change. The entry names the file in backticks and says what it does.

`package_inventory_stale_blocker.py` (PreToolUse on Write) blocks a new production file whose basename appears in no present inventory and names the fix. A skill `SKILL.md` Layout table that maps `scripts/` counts as the inventory for files in that subdirectory.

## Judgment the gate cannot derive

The file-list entry is the slice the gate checks by name. Two free-prose slices stay with judgment and belong in the same change:

1. **Purpose / scope sentence.** When the new module adds a responsibility the package `## Purpose` (or the parent inventory's one-line summary of this subdirectory) omits, broaden that sentence to name it. A hook cannot derive a module's responsibility from its filename.

2. **Per-file description clause.** When a file gains a responsibility the inventory's em-dash description omits — a new public function, a new module-level constant — broaden the description clause to name it. The gate only checks that the basename appears once; it never reads the description. Constants modules (`*_constants.py`, or any `.py` directly inside `config/`) are the common shape: the constant's other home is the module docstring, so the clause that lands in the docstring lands in the inventory description in the same change. The gate fires on Write of a new file and skips files directly inside `config/`, so an Edit that adds a constant to an existing config module matches neither path.

This is the `category-o-docstring-vs-impl-drift` (O8) orphaned-doc-claim shape applied to a package inventory.
