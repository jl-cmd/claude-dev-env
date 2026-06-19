# bin

The installer and its companion modules. Running `npx claude-dev-env` (or `node bin/install.mjs`) copies package files into `~/.claude/`, merges hook entries into `~/.claude/settings.json`, installs Git hooks, and writes `~/.mypy.ini`.

## Files

| File | Purpose |
|---|---|
| `install.mjs` | Main installer: discovers install groups, copies content directories (`rules`, `docs`, `commands`, `agents`, `system-prompts`, `scripts`, `_shared`, `audit-rubrics`), merges hooks into `settings.json`, installs skills, runs `git_hooks_installer.mjs` and `install_mypy_ini.mjs` |
| `git_hooks_installer.mjs` | Installs or updates the `pre-commit`, `pre-push`, and `post-commit` Git hooks in the user's git config; writes hook scripts that delegate to the installed Python hooks |
| `install_mypy_ini.mjs` | Writes `~/.mypy.ini` with settings that make mypy find the hooks package and enforce strict type checking |
| `install.test.mjs` | Tests for `install.mjs` — covers conflict detection, interpreter detection, settings merging |
| `git_hooks_installer.test.mjs` | Tests for `git_hooks_installer.mjs` |
| `install_mypy_ini.test.mjs` | Tests for `install_mypy_ini.mjs` |

## Key exports from install.mjs

| Export | Description |
|---|---|
| `CONTENT_DIRECTORIES` | Array of package subdirectory names copied verbatim to `~/.claude/` |
| `pythonCandidatesForPlatform(platform)` | Returns ordered Python interpreter candidates to probe; `py -3` first on Windows to avoid Microsoft Store alias issues |
| `isWindowsStorePythonStub(path)` | Returns true when the path resolves to the non-spawnable WindowsApps stub |
| `interpreterCommandFromPath(path)` | Formats an absolute interpreter path as a settings.json hook command prefix |
| `collectPackageSourceConflicts(dir)` | Returns any unmerged git conflicts in the package source; installer aborts when any exist |

## Install groups

`install.mjs` defines install groups (`core`, `journal`, `research`) plus any dependency groups discovered from `package.json` `dependencies`. The `core` group installs skills, all hooks, and the content directories. `journal` and `research` install only their skill sets.
