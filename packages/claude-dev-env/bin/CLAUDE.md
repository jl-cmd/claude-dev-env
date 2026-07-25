# bin

The installer and its companion modules. Running `npx claude-dev-env` (or `node bin/install.mjs`) copies package files into `~/.claude/`, merges hook entries into `~/.claude/settings.json`, installs Git hooks, and writes `~/.mypy.ini`.

## Files

| File | Purpose |
|---|---|
| `install.mjs` | Main installer: discovers install groups, copies content directories (`rules`, `docs`, `commands`, `agents`, `system-prompts`, `scripts`, `_shared`, `audit-rubrics`), merges hooks into `settings.json`, installs skills, prunes retired skill directories and stale skill files on a full install, runs `git_hooks_installer.mjs` and `install_mypy_ini.mjs` |
| `ever-shipped-skills.mjs` | Static `EVER_SHIPPED_SKILL_NAMES` set of every top-level skill directory name the package has shipped; the installer subtracts the current skill set from it to prune retired skills left under `~/.claude/skills` |
| `expand_home_directory_tokens.mjs` | Expands residual `$HOME` / `${HOME}` / `~/` tokens in settings.json hook and statusLine commands to absolute home paths at install time (literal-safe for homes that contain `$`) |
| `git_hooks_installer.mjs` | Installs or updates the `pre-commit`, `pre-push`, and `post-commit` Git hooks in the user's git config; writes hook scripts that delegate to the installed Python hooks |
| `install_mypy_ini.mjs` | Writes `~/.mypy.ini` with settings that make mypy find the hooks package and enforce strict type checking |
| `install.test.mjs` | Unit tests for `install.mjs` — covers conflict detection, interpreter detection, settings merging, and the stale-file prune: the manifest diff, path-key case folding, emptied-parent cleanup, and the warn-and-keep paths |
| `install.prune.test.mjs` | End-to-end prune tests that run the real installer against a sandbox `HOME` — retired-skill and stale-file moves into one timestamped backup, the manifest record a failed move keeps, the full-install and resolved-dependency gates |
| `git_hooks_installer.test.mjs` | Tests for `git_hooks_installer.mjs` |
| `install_mypy_ini.test.mjs` | Tests for `install_mypy_ini.mjs` |

## Retired-skill prune

The full-install prune renames a retired skill directory into a timestamped backup rather than deleting it. Each pruned directory is renamed to `~/.claude/.claude-dev-env-pruned/<timestamp>/<skill-name>/`, a backup root outside `~/.claude/skills` so a backed-up directory is never re-discovered as a skill. One run shares one timestamped root, so a run leaves one recovery point. Backups accumulate — nothing cleans them — so a user can recover a directory. A rename that fails leaves the directory in place with a logged warning and never falls back to deletion, so a prune failure costs at most a cosmetic leftover.

Matching is by directory name alone, so a user-authored directory whose name collides with a retired skill is backed up as if it were that skill. A directory is pruned when the prior install's manifest recorded it or the ever-shipped set names it, and the current install did not just write it. A name absent from all three of those sets, together with `~/.claude/skills/_shared`, is left in place.

## Stale-file prune

A full install also moves aside a file sitting inside a live skill directory that the run leaves unwritten. The installer reads the file list from `~/.claude/.claude-dev-env-manifest.json`, keeps the entries under `~/.claude/skills`, subtracts every skill file the run copied across all source roots, and moves what remains into the run's backup root, mirroring each file's path under the skills directory. Both prunes share that one backup root.

The manifest diff limits the move to files the installer itself wrote. Runtime-generated content — a Python `__pycache__` entry, a ruff cache, a log — and any file a user authored inside a skill directory stay in place, because no install recorded them. Path comparison ignores letter case on Windows and macOS, so a skill shipping `README.md` over an installed `Readme.md` keeps the bytes the run just wrote. A directory or a link standing where the manifest records a file is skipped with a warning, so the mover never renames a whole tree and never follows a link out of `~/.claude`. A directory emptied by a move is removed, walking up to the skills directory. A move that fails logs a warning and leaves the file in place, so a prune failure costs at most a stale file. The installer records each such path in the fresh manifest when the file is still on disk, so the file stays inside the next full install's diff and gets another attempt.

A missing or unreadable manifest, or one carrying no file list, holds the stale-file prune for that run: with no record of what an install wrote, the run has nothing to diff against.

A full install writes the manifest's file list wholesale from what it just installed, so the next diff reads as "the package stopped shipping this". A scoped `--only` install unions what it wrote onto the prior list, which holds every entry a later full install needs to spot a stale file. The prune itself bounds the list: a stale path leaves the record on the first full install that moves it aside.

## Prune gates

The retired-skill prune and the stale-file prune run behind the same two gates: a full install, and every declared dependency group resolved. When any dependency group fails to resolve, both are skipped for the whole run with a logged notice naming the unresolved group. An unresolved dependency contributes no skills to the installed set, so a live skill that a dependency package supplies would look retired and its files would look stale; holding both prunes until every dependency resolves keeps that skill and its files from being backed up.

## Key exports from install.mjs

| Export | Description |
|---|---|
| `CONTENT_DIRECTORIES` | Array of package subdirectory names copied verbatim to `~/.claude/` |
| `pythonCandidatesForPlatform(platform)` | Returns ordered Python interpreter candidates to probe; `py -3` first on Windows to avoid Microsoft Store alias issues |
| `isWindowsStorePythonStub(path)` | Returns true when the path resolves to the non-spawnable WindowsApps stub |
| `interpreterCommandFromPath(path)` | Formats an absolute interpreter path as a settings.json hook command prefix |
| `collectPackageSourceConflicts(dir)` | Returns any unmerged git conflicts in the package source; installer aborts when any exist |
| `pruneStaleInstalledFiles(priorFiles, currentFiles, destinationRoot, backupRoot, options)` | Moves each manifest-recorded file under the destination root that the run leaves unwritten into the run's backup root; returns `{ prunedCount, failedPaths }`. `options.isCaseInsensitive` drives path-key case folding, defaulting to this host's filesystem |
| `comparisonKeyForPath(path, options)` | Builds the key two paths are compared through: resolved, forward-slashed, and lowercased when `options.isCaseInsensitive` holds — which defaults to true on Windows and macOS |

## Install groups

`install.mjs` defines install groups (`core`, `journal`) plus any dependency groups discovered from `package.json` `dependencies`. The `core` group installs skills, all hooks, and the content directories. `journal` installs only its skill set.
