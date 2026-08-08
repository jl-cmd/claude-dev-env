# .claude/hooks

Repo-committed hooks that run in Claude Code sessions on this repository,
registered under `hooks` in `.claude/settings.json`.

## Key files

| File | Role |
|---|---|
| `session_start_refresh.py` | SessionStart hook: in a cloud session, compares the installed claude-dev-env manifest version against the npm registry and reinstalls on a difference. Fail-open — every failure path exits 0. |
| `config/` | Constants package for these hooks. Its `__init__.py` records why the `config` import resolves here: the hook runs as a script path, so this directory sits at `sys.path[0]`. |
