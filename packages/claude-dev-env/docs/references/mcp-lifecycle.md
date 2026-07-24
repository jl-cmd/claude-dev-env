# MCP lifecycle — lean config and session teardown

Stops per-session mcpvault / playwright MCP / serena **spawn-without-reap** on Windows agent hosts (Claude Code, Claude Desktop, Grok via Claude MCP compat).

## Config paths

| Surface | Path | Role |
|---------|------|------|
| Claude Code user MCP | `~/.claude.json` → `mcpServers` | Primary stdio/HTTP MCP map (also imported by Grok) |
| Claude Code nested user MCP | `~/.claude/.claude.json` → `mcpServers` | Secondary Claude Code state copy |
| Claude Code plugins | `~/.claude/settings.json` → `enabledPlugins` | e.g. `playwright@claude-plugins-official` |
| Claude Code local plugins | `~/.claude/settings.local.json` → `enabledPlugins` | Local plugin overrides |
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` → `mcpServers` | Desktop stdio MCP |
| claude_desktop_config (profile copies) | `%LOCALAPPDATA%\Claude Desktop Profiles\Profiles\<name>\claude_desktop_config.json` | Per-profile Desktop MCP |
| Grok native MCP | `~/.grok/config.toml` → `[mcp_servers.*]` | Grok-only MCP |
| Grok Claude compat | `~/.grok/config.toml` → `[compat.claude] mcps` | When true/default, Grok loads `~/.claude.json` MCP |
| Session host registry | `~/.claude/cache/mcp-session-registry/mcp-host-<session>.json` | Written by SessionStart hook |

Grok merge order (product docs): `config.toml` > Claude `~/.claude.json` > Cursor > project `.mcp.json`.

## Package surfaces

| Path | Role |
|------|------|
| `hooks/lifecycle/mcp_session_lifecycle.py` | SessionStart host PID registry; SessionEnd targeted MCP tree teardown |
| `hooks/hooks_constants/mcp_session_lifecycle_constants.py` | Markers, registry paths, taskkill args |
| `scripts/mcp_lifecycle/apply_lean_mcp_policy.py` | Remove heavy stdio MCP + disable playwright plugin; optional Grok compat off |
| `scripts/mcp_lifecycle/measure_mcp_process_counts.py` | Live count recipe (`mcpvault_cmdline`, `playwright_mcp`, `serena`, `node`) |
| `scripts/mcp_lifecycle/recipe_mcp_teardown_within_deadline.py` | Synthetic teardown proof (deadline 60s) |
| `scripts/mcp_lifecycle/reap_orphaned_mcp_processes.py` | One-shot cleanup of MCP trees whose parent host is already dead |

## Operator recipe

```powershell
# 1) Baseline counts
python packages/claude-dev-env/scripts/mcp_lifecycle/measure_mcp_process_counts.py

# 2) Lean policy (preview then apply)
python packages/claude-dev-env/scripts/mcp_lifecycle/apply_lean_mcp_policy.py --dry-run
python packages/claude-dev-env/scripts/mcp_lifecycle/apply_lean_mcp_policy.py --apply --disable-grok-claude-mcps

# 3) Install hooks so SessionEnd reaps MCP children of the host
cd packages/claude-dev-env; node bin/install.mjs

# 4) Synthetic teardown deadline
python packages/claude-dev-env/scripts/mcp_lifecycle/recipe_mcp_teardown_within_deadline.py

# 5) After real multi-session work + host exit: mcpvault_cmdline should be ~0 within 60s
python packages/claude-dev-env/scripts/mcp_lifecycle/measure_mcp_process_counts.py
```

## Teardown rules

- Scope is **registered host PID + MCP command-line markers** only.
- Uses `taskkill /F /T /PID <id>` per matched descendant — not a blanket kill of `node.exe` / all MCP by name.
- HTTP MCP servers are left in place by lean policy (no per-session process tree).
