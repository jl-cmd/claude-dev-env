# Development Environment

## Plugin Ecosystem

claude-code-config is the primary plugin providing rules, docs, agents, commands, skills, and hooks. All behavioral rules live in `.claude/rules/` files. Additional plugins: claude-journal, claude-deep-research, claude-workflow, GSD (npx get-shit-done-cc).

## Docs

Reference documents in `docs/` are available but not auto-loaded. Skills can `@` import them as needed.

- `docs/CODE_RULES.md` -- hook-enforced code standards
- `docs/TEST_QUALITY.md` -- testing quality guidelines
- `docs/emotion-informed-prompt-design.md` -- emotion-informed prompt design (Anthropic research + best practices)
- `docs/REACT_PATTERNS.md` -- React patterns
- `docs/DJANGO_PATTERNS.md` -- Django patterns

## Agent Gate

The `agent-gate` MCP server evaluates prompts before execution. The `gate_enforcer.py` PreToolUse hook blocks execution tools until `evaluate_prompt` clears. Subagents bypass the gate via a `*` prefix in their prompt.

## Obsidian Vault

Search with `mcp__obsidian__search_notes` before starting substantive work. Prior sessions and decisions inform current tasks.

- `sessions/[Project]/` -- session reports
- `decisions/` -- active or superseded decisions
- `Research/` -- deep research documents

## Search Tools

- zoekt MCP server for indexed code search
- Context7 MCP for current library and framework docs
- Everything `es.exe` for fast file search (Windows environments)

## Git

Multiple GitHub accounts configured via SSH. The `git-account-switcher.py` hook auto-detects the correct account per repo.

## Hooks

Settings.json hooks are machine-specific only. Plugin hooks are registered via the plugin system. The two do not overlap.

### Hook System Architecture

- **Runner pattern**: `run-hook-wrapper.js` (Node.js) -> `run-hook.py` (Python) -> individual hook
- **Hook directory**: `hooks/` with subfolders: `session/`, `notification/`, `advisory/`, `validation/`, `lifecycle/`, `blocking/`, `git-hooks/`, `github-action/`, `workflow/`, `validators/`
- **Event types**: SessionStart, UserPromptSubmit, PreToolUse (can block), PostToolUse, SubagentStop, Stop
- **Adding hooks**: Create Python file in appropriate subfolder, register in settings.json using `run-hook-wrapper.js` pattern with explicit timeouts (10000-30000ms)
- **Blocking hooks**: exit 2 with `hookSpecificOutput.permissionDecision`; advisory hooks exit 0

## Bulk Operations

For bulk updates (replace all, rename all, change all, fix all), use a Python script with `--preview`/`--apply` flags instead of line-by-line edits.

## Gotchas

- Python command varies by platform. Detect which of `python3`, `python`, or `py -3` resolves to Python 3.12+.
- Network drives can be slow for git. Clone to local temp dirs for intensive operations.
- The agent-gate MCP server disconnects intermittently. Run `/mcp` to reconnect if tools are blocked but the MCP tool is unavailable.
- On Windows, Python hooks route through a `node` wrapper (`run-hook-wrapper.js`) for stdin piping.
