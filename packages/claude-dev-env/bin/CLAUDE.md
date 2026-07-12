# bin

The installer and its companion modules. Running `npx claude-dev-env` (or `node bin/install.mjs`) copies package files into `~/.claude/`, merges hook entries into `~/.claude/settings.json`, installs Git hooks, and writes `~/.mypy.ini`.

## Files

| File | Purpose |
|---|---|
| `install.mjs` | Main installer: discovers install groups, copies content directories (`rules`, `docs`, `commands`, `agents`, `system-prompts`, `scripts`, `_shared`, `audit-rubrics`), merges hooks into `settings.json`, installs skills, prunes retired skills on a full install, runs `git_hooks_installer.mjs` and `install_mypy_ini.mjs` |
| `ever-shipped-skills.mjs` | Static `EVER_SHIPPED_SKILL_NAMES` set of every top-level skill directory name the package has shipped; the installer subtracts the current skill set from it to prune retired skills left under `~/.claude/skills` |
| `expand_home_directory_tokens.mjs` | Expands residual `$HOME` / `${HOME}` / `~/` tokens in settings.json hook and statusLine commands to absolute home paths at install time (literal-safe for homes that contain `$`) |
| `git_hooks_installer.mjs` | Installs or updates the `pre-commit`, `pre-push`, and `post-commit` Git hooks in the user's git config; writes hook scripts that delegate to the installed Python hooks |
| `install_mypy_ini.mjs` | Writes `~/.mypy.ini` with settings that make mypy find the hooks package and enforce strict type checking |
| `install.test.mjs` | Tests for `install.mjs` — covers conflict detection, interpreter detection, settings merging |
| `git_hooks_installer.test.mjs` | Tests for `git_hooks_installer.mjs` |
| `install_mypy_ini.test.mjs` | Tests for `install_mypy_ini.mjs` |

## Retired-skill prune

The full-install prune renames a retired skill directory into a timestamped backup rather than deleting it. Each pruned directory is renamed to `~/.claude/.claude-dev-env-pruned/<timestamp>/<skill-name>/`, a backup root outside `~/.claude/skills` so a backed-up directory is never re-discovered as a skill. Backups accumulate — nothing cleans them — so a user can recover a directory. A rename that fails leaves the directory in place with a logged warning and never falls back to deletion, so a prune failure costs at most a cosmetic leftover.

Matching is by directory name alone, so a user-authored directory whose name collides with a retired skill is backed up as if it were that skill. Only a name in neither the installed set nor the ever-shipped set, and `~/.claude/skills/_shared`, are left in place.

The prune is skipped for the whole run — with a logged notice naming the unresolved group — when any declared dependency group fails to resolve. An unresolved dependency contributes no skills to the installed set, so a live skill that a dependency package supplies would look retired; holding the prune until every dependency resolves keeps such a skill from being backed up.

## Key exports from install.mjs

| Export | Description |
|---|---|
| `CONTENT_DIRECTORIES` | Array of package subdirectory names copied verbatim to `~/.claude/` |
| `pythonCandidatesForPlatform(platform)` | Returns ordered Python interpreter candidates to probe; `py -3` first on Windows to avoid Microsoft Store alias issues |
| `isWindowsStorePythonStub(path)` | Returns true when the path resolves to the non-spawnable WindowsApps stub |
| `interpreterCommandFromPath(path)` | Formats an absolute interpreter path as a settings.json hook command prefix |
| `collectPackageSourceConflicts(dir)` | Returns any unmerged git conflicts in the package source; installer aborts when any exist |

## Install groups

`install.mjs` defines install groups (`core`, `journal`) plus any dependency groups discovered from `package.json` `dependencies`. The `core` group installs skills, all hooks, and the content directories. `journal` installs only its skill set.
