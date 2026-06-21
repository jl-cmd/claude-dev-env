# New Production File Absent From Its Package Inventory

**When this applies:** Any Write that creates a new production code file (`.py`, `.mjs`, `.js`, `.ts`, `.ps1`, `.sh`) in a directory whose sibling `README.md` or `CLAUDE.md` already names two or more of the directory's files in backticks.

## Rule

A package directory that documents its own files in a `README.md` Layout table or a `CLAUDE.md` "Key files" list keeps that inventory in step with the directory. A new production file the inventory does not name leaves the inventory and the directory disagreeing on the package's file set: a reader who trusts the inventory to map the directory misses the new file.

When you create a new production file in such a directory, add an entry naming it — a row in the `README.md` table, a bullet in the `CLAUDE.md` list — in the same change. The entry names the file in backticks and says what it does.

## What the gate checks

The `package_inventory_stale_blocker.py` hook runs on every Write whose target is a new file (a path not yet on disk). It:

1. Skips a target that is not a production code file (`.py`, `.mjs`, `.js`, `.ts`, `.ps1`, `.sh`), an exempt basename (`__init__.py`, `conftest.py`, `setup.py`, `_path_setup.py`), a test file (`test_*.py`, `*_test.py`, `*.spec.*`, `*.test.*`), or a file directly inside a `config/` or `tests/` directory.
2. Reads each `README.md` and `CLAUDE.md` present in the target's own directory and collects every bare filename they name in backticks. A backticked token holding a path contributes its final segment, so `pipeline/seam_continuity.py` in an inventory counts as naming `seam_continuity.py`.
3. Treats the directory as carrying a maintained inventory only when those documents together name two or more sibling files; a directory with no inventory, or whose `README.md` mentions one file in passing, is out of scope.
4. Blocks the write when the new file's basename appears in no present inventory. An unreadable or oversized inventory document is skipped, so a missing inventory never blocks a write.

The check fires on Write only — editing an existing file adds no new inventory entry — and stays quiet for a directory with no inventory document, an inventory naming too few siblings to be a maintained list, an exempt or test file, and a file the inventory already names.

## Why this is a hook, not a lint pass

A package inventory that omits a file reads as a complete map of the directory while leaving one file off it. A reader trusting the inventory to list the package misses the new file, and the gap survives review because the inventory still looks complete. Catching it as the new file is written keeps the inventory and the directory in step. This is the counterpart to `claude-md-orphan-file.md`, which catches the reverse drift: an inventory entry naming a file the directory does not hold.
