# Development Environment

## Monorepo Structure

This is an npm workspaces monorepo with three packages in `packages/`:

- `packages/claude-dev-env/` -- main package: rules, docs, commands, agents, skills, hooks
- `packages/claude-journal/` -- journal skills: dream, session-log, session-tidy
- `packages/claude-deep-research/` -- research skills and agent: deep-research, research-mode

The main installer (`packages/claude-dev-env/bin/install.mjs`) discovers and installs content from workspace siblings and npm dependencies. Each package also has a standalone installer for independent use. Additional external plugins: claude-workflow, GSD (npx get-shit-done-cc).

The prompt-generator skill, the agent-prompt skill, and the prompt-workflow blocking hooks live in the standalone @jl-cmd/prompt-generator package — claude-dev-env declares it as a runtime dependency and installs it transparently.

## Docs

Reference documents in `packages/claude-dev-env/docs/` are available but not auto-loaded. Skills can `@` import them as needed. Canonical text for several policies lives in `packages/claude-dev-env/system-prompts/software-engineer.xml` (for example `<code_quality>` and `<behavior_protocol>`); the installer copies that file to `~/.claude/system-prompts/`. Shipped `docs/CODE_RULES.md` and many `rules/*.md` files are one-line pointers into that XML (see JonEcho/llm-settings PR 17 for the consolidation pattern).

- `packages/claude-dev-env/system-prompts/software-engineer.xml` -- canonical system prompt sections for Claude Code
- `packages/claude-dev-env/docs/CODE_RULES.md` -- pointer to `<code_quality>` (hook-enforced standards live in the XML)
- `packages/claude-dev-env/docs/TEST_QUALITY.md` -- testing quality guidelines
- `packages/claude-dev-env/docs/emotion-informed-prompt-design.md` -- emotion-informed prompt design (Anthropic research + best practices)
- `packages/claude-dev-env/docs/REACT_PATTERNS.md` -- React patterns
- `packages/claude-dev-env/docs/DJANGO_PATTERNS.md` -- Django patterns

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
- **Blocking hooks**: For `PreToolUse` denials, Claude Code documents **exit 0** and JSON on **stdout** with `hookSpecificOutput.permissionDecision` (see [hooks reference](https://code.claude.com/docs/en/hooks)); **exit 2** + stderr also blocks but **does not** parse JSON. Advisory hooks exit 0 without deny.

## Bulk Operations

For bulk updates (replace all, rename all, change all, fix all), use a Python script with `--preview`/`--apply` flags instead of line-by-line edits.

## Gotchas

- Python command varies by platform. Detect which of `python3`, `python`, or `py -3` resolves to Python 3.12+.
- Network drives can be slow for git. Clone to local temp dirs for intensive operations.
- The agent-gate MCP server disconnects intermittently. Run `/mcp` to reconnect if tools are blocked but the MCP tool is unavailable.
- On Windows, Python hooks route through a `node` wrapper (`run-hook-wrapper.js`) for stdin piping.
