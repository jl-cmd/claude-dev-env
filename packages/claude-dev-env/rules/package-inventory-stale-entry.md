# New Production File Absent From Its Package Inventory

**When this applies:** Any Write that creates a new production code file (`.py`, `.mjs`, `.js`, `.ts`, `.ps1`, `.sh`) in a directory whose sibling `README.md` or `CLAUDE.md` already names two or more of the directory's files in backticks, or in a skill's `scripts/` subdirectory whose parent `SKILL.md` Layout table already names two or more of those scripts.

## Rule

A package directory that documents its own files in a `README.md` Layout table or a `CLAUDE.md` "Key files" list keeps that inventory in step with the directory. A skill package does the same in its `SKILL.md` Layout table, which sits at the skill root and maps the `scripts/` subdirectory by naming each script with its `scripts/<name>` path. A new production file the inventory does not name leaves the inventory and the directory disagreeing on the package's file set: a reader who trusts the inventory to map the directory misses the new file.

When you create a new production file in such a directory, add an entry naming it — a row in the `README.md` or `SKILL.md` table, a bullet in the `CLAUDE.md` list — in the same change. The entry names the file in backticks and says what it does.

## Companion: keep the Purpose/scope sentence in step with the new responsibility

The file-list entry is the deterministic slice the gate enforces. A package inventory also carries a free-prose scope sentence — a `## Purpose` paragraph in a `CLAUDE.md`, a one-line summary the parent directory's inventory gives each subdirectory — that names the responsibilities the package's modules cover. When the new module adds a responsibility the scope sentence omits, the same change broadens that sentence to name it, and updates the parent inventory's one-line summary of this subdirectory to match.

Take a `files/` package whose `Purpose` reads "Holds helpers for downloading files over HTTP and extracting zip archives" and whose parent summary reads "file download, extraction, and path config helpers". Once a `force_remove.py` module that removes a directory tree sits beside the download helpers, both sentences name a narrower responsibility set than the directory holds. The required file-list bullet alone leaves that gap open. Broaden the `Purpose` sentence to name directory removal, and broaden the parent summary to match, in the same change that adds the module and its bullet.

This scope-sentence slice is free prose: a hook cannot derive a module's responsibility from its filename, so the gate leaves it to judgment. It is the judgment companion to the file-list entry the gate enforces, and it belongs in the same change. This is the `category-o-docstring-vs-impl-drift` (O8) orphaned-doc-claim shape applied to a package inventory: a behavior change orphans a scope claim the prose still makes.

## Companion: keep a per-file description in step with the file it describes

The per-file entry a `CLAUDE.md` "Key files" list or a `README.md` Layout table gives each file carries more than the backticked filename the gate checks for. The clause after the file name — the em-dash description — is itself a free-prose scope claim about what the file holds. When the file gains a responsibility the description omits — a new public function, a new constant — the same change broadens the description clause to name it. The gate's file-list check passes the moment the file name appears once; it never reads the description clause, so a stale description beside a present file name stays invisible to the gate.

A constants module is the common shape of this drift. A file whose name ends `_constants.py`, or any `.py` directly inside a `config/` directory, holds a set of module-level constants, and a sibling inventory describes that file by listing the set — `` `stp_constants.py` — the STP archive member constants: the Properties.xml member name, the workspace prefix every asset reference carries, and the source-form nine-patch filename suffix ``. When the file gains a module-level constant the list omits, three claims drift together: the list itself, the scope label that heads it (`the STP archive member constants`), and the package `## Purpose` sentence when that sentence describes the file's contents. The constant's other home — the module docstring of the constants file — and the sibling inventory's description of that file cover the same set, so the clause that lands in the docstring lands in the inventory description in the same change.

This slice sits outside the gate. The gate fires on a Write that creates a new file, and it skips a file directly inside a `config/` directory, so an Edit that adds a constant to an existing `config/` constants module matches neither path. Like the Purpose/scope companion above, it is free prose a hook cannot derive from a file name, so it stays judgment here and a Category O8 finding at audit: a behavior change orphans a description claim the inventory still makes.

## What the gate checks

The `package_inventory_stale_blocker.py` hook runs on every Write whose target is a new file (a path not yet on disk). It:

1. Skips a target that is not a production code file (`.py`, `.mjs`, `.js`, `.ts`, `.ps1`, `.sh`), an exempt basename (`__init__.py`, `conftest.py`, `setup.py`, `_path_setup.py`), a test file (`test_*.py`, `*_test.py`, `*.spec.*`, `*.test.*`), or a file directly inside a `config/` or `tests/` directory.
2. Reads each `README.md`, `CLAUDE.md`, and `SKILL.md` present in the target's own directory and, when the target sits in a `scripts/` subdirectory, the parent directory's `SKILL.md`, and collects every bare filename they name in backticks. A backticked token holding a path contributes its final segment, so `pipeline/seam_continuity.py` in an inventory counts as naming `seam_continuity.py` and `scripts/stp_selection.py` in a parent `SKILL.md` Layout table counts as naming `stp_selection.py`. A multi-word command-example span — one carrying whitespace or shell punctuation (`:`, `$`, `<`, `>`), such as `parent:node_modules package.json` or `python <file>.py` — names no literal file and is dropped.
3. Filters the named basenames to those that exist as a file in the target's own directory — the inventory's own sibling files — and treats the directory as carrying a maintained inventory only when two or more such sibling files are named. A directory with no inventory, one whose `README.md` mentions a single file in passing, or one whose inventory prose names only files living in other directories (so no named basename is an on-disk sibling) is out of scope.
4. Blocks the write when the new file's basename appears in no present inventory. An unreadable or oversized inventory document is skipped, so a missing inventory never blocks a write.

The check fires on Write only — editing an existing file adds no new inventory entry — and stays quiet for a directory with no inventory document, an inventory naming too few siblings to be a maintained list, an exempt or test file, and a file the inventory already names.

## Why this is a hook, not a lint pass

A package inventory that omits a file reads as a complete map of the directory while leaving one file off it. A reader trusting the inventory to list the package misses the new file, and the gap survives review because the inventory still looks complete. Catching it as the new file is written keeps the inventory and the directory in step. This is the counterpart to `claude-md-orphan-file.md`, which catches the reverse drift: an inventory entry naming a file the directory does not hold.
