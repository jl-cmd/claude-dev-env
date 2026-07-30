# .github/scripts

Python helper scripts called by GitHub Actions workflows in `.github/workflows/`.

## Files

| File | Purpose |
|------|---------|
| `sync_ai_rules.py` | Syncs `AGENTS.md` from this repo into target repos. Fetches the source content, prepends a sync header (source commit, timestamp, SHA256 trailer), and commits to the target's default branch. Called by `sync-ai-rules.yml` (target-side listener). |
| `plugin_channel_inventory.mjs` | Pure parse and classify helpers for the plugin-channel consumer inventory: plugin and marketplace manifests, README entry detection, selected-profile registration probes, collision boolean, and journal schema validation. |
| `plugin_channel_inventory.test.mjs` | `node:test` suite for the inventory helpers and the committed `docs/references/plugin-channel-inventory.json` journal. |

## How `sync_ai_rules.py` works

1. Reads source paths from `config/sync_ai_rules_paths.py` (`SOURCE_FILE_PATH`, `DESTINATION_PATHS`, `BUGBOT_ONLY_DESTINATION_PATHS`).
2. Fetches the canonical `AGENTS.md` content from GitHub raw or from a `RAW_URL` env var supplied by the dispatcher.
3. Checks for an opt-out sentinel file (`.github/sync-ai-rules.optout`) in the target repo — skips if present.
4. Prepends a `<!-- SYNC-HEADER-START/END -->` block with metadata, then commits to the target.
5. Exits non-zero on fetch failure or commit conflict so the workflow surfaces the error.

## Conventions

- Do not call `sync_ai_rules.py` directly during development; drive it through `python -m pytest tests/test_sync_ai_rules.py` to run against fixtures.
- The script imports from `config/sync_ai_rules_paths.py` via a guarded `sys.path.insert`; the repo root must be on the path, which `pytest.ini` handles via `pythonpath = .`.
- `__pycache__/` is gitignored; the `.pyc` file next to this script is a local artifact.
- Run the plugin-channel inventory suite with `node --test .github/scripts/plugin_channel_inventory.test.mjs` from the repository root.
