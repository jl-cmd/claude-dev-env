# sync_to_cursor

Python package that syncs Claude rules and docs to Cursor `.mdc` files. Entry point is `packages/claude-dev-env/scripts/sync_to_cursor.py`; this package holds the implementation modules.

## Modules

| File | Purpose |
|---|---|
| `engine.py` | Main sync logic: loads the manifest, builds rule mappings, hashes sources, writes `.mdc` files, and updates the manifest |
| `rules.py` | Builds `RuleMapping` objects from Claude rule markdown files; applies transforms to fit Cursor's `.mdc` format |
| `canonical_docs.py` | Checks and syncs canonical documentation files (`CODE_RULES.md`, `TEST_QUALITY.md`) to the Cursor rules directory |
| `paths.py` | Resolves the Claude and Cursor layout paths; respects the `LLM_SETTINGS_ROOT` env var for non-home layouts |
| `hashing.py` | SHA-256 helpers that detect whether source files changed since the last sync run |
| `config.py` | Package-level constants: `GENERATOR_VERSION`, `CANONICAL_DOC_FILES`, `MAX_RULE_BODY_LINES` |
| `__init__.py` | Empty package marker |

## Layout resolution

`paths.py` reads `LLM_SETTINGS_ROOT` from the environment. When set, it uses that path as the base for both `.claude/` and `.cursor/`. When unset, it falls back to `Path.home()`.

## Tests

Tests live in `packages/claude-dev-env/scripts/tests/test_sync_to_cursor.py`.
