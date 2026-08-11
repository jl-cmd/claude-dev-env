# .github/scripts

Python helper scripts called by GitHub Actions workflows in `.github/workflows/`.

## Files

| File | Purpose |
|------|---------|
| `plugin_channel_inventory.mjs` | Pure parse and classify helpers for the plugin-channel consumer inventory: plugin and marketplace manifests, README entry detection, selected-profile registration probes, collision boolean, and journal schema validation. |
| `plugin_channel_inventory.test.mjs` | `node:test` suite for the inventory helpers and the committed `docs/references/plugin-channel-inventory.json` journal. |

## Conventions

- `__pycache__/` is gitignored; the `.pyc` file next to this script is a local artifact.
- Run the plugin-channel inventory suite with `node --test .github/scripts/plugin_channel_inventory.test.mjs` from the repository root.
