# .claude-plugin

Claude plugin manifest directory. These two JSON files register this repo as a Claude plugin in the Claude marketplace and describe its metadata.

## Key files

| File | Purpose |
|------|---------|
| `plugin.json` | Core plugin descriptor — name (`claude-code-config`), description, author (`jl-cmd`), version, and license |
| `marketplace.json` | Marketplace listing — owner, human-readable metadata, and the plugin entry with category (`development`) and tags (`code-standards`, `hooks`, `agents`, `tdd`, `quality`) |

## Conventions

- `plugin.json` is the minimal identity file; `marketplace.json` carries the richer listing data the marketplace UI displays.
- Both files must stay in sync when the package version or description changes.
- These files are not processed by `packages/claude-dev-env/bin/install.mjs` and are not copied to `~/.claude/` on install.
