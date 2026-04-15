# Development Environment

## Repository Snapshot

`claude-code-config` is an npm workspaces repo currently centered on a single package:

- `packages/claude-dev-env/` - main package containing rules, hooks, commands, agents, skills, docs, and installer logic

Top-level workspace config remains enabled via `package.json` (`"workspaces": ["packages/*"]`), but only `claude-dev-env` is present in this checkout.

## Package Layout

Primary working paths under `packages/claude-dev-env/`:

- `agents/`
- `bin/`
- `commands/`
- `docs/`
- `hooks/`
- `rules/`
- `skills/`

## Standards and Source of Truth

Core standards docs live in:

- `packages/claude-dev-env/docs/CODE_RULES.md`
- `packages/claude-dev-env/docs/TEST_QUALITY.md`
- `packages/claude-dev-env/docs/REACT_PATTERNS.md`
- `packages/claude-dev-env/docs/DJANGO_PATTERNS.md`
- `packages/claude-dev-env/docs/PR_DESCRIPTION_GUIDE.md`

When implementing or reviewing code, treat these docs as authoritative.

## Hooks Architecture

Hook runner chain:

1. `run-hook-wrapper.js` (Node)
2. `run-hook.py` (Python)
3. individual hook modules

Hook folders are organized under `packages/claude-dev-env/hooks/` by purpose (for example `validation/`, `blocking/`, `workflow/`, `lifecycle/`, `session/`).

## Practical Workflow Notes

- Prefer `rg` / `rg --files` for search when available.
- For broad or repetitive edits, use scripted updates with preview/apply flow rather than manual line-by-line editing.
- Validate behavior with focused tests before and after refactors (BDD expectation: discovery, then failing specification, then code).

## Environment Gotchas

- Python executable name varies by machine (`python3`, `python`, or `py -3`).
- Network drives can be slower for heavy git operations.
- On Windows, hook execution may route through the Node wrapper for reliable stdin piping.
