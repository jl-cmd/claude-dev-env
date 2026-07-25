# bin

The installer and its companion modules. Running `npx claude-dev-env` (or `node bin/install.mjs`) copies package files into `~/.claude/`, merges hook entries into `~/.claude/settings.json`, installs Git hooks, and writes `~/.mypy.ini`.

## Files

| File | Purpose |
|---|---|
| `install.mjs` | Main installer: discovers install groups, copies content directories (`rules`, `docs`, `commands`, `agents`, `system-prompts`, `scripts`, `_shared`, `audit-rubrics`), merges hooks into `settings.json`, installs skills, prunes retired skill directories, retired hook entries, and stale files under every managed root on a full install, retires older prune backups, runs `git_hooks_installer.mjs` and `install_mypy_ini.mjs` |
| `install-constants.mjs` | The named values `install.mjs` reads: `SKIPPED_SOURCE_ENTRY_NAMES` and `SKIPPED_SOURCE_FILE_EXTENSIONS` for the build artifacts the source walk leaves behind, `RUN_BACKUP_DIRECTORY_NAME_PATTERN` for the timestamp shape a run backup directory carries, `MANAGED_SKILLS_DIRECTORY_NAME` and `MANAGED_HOOKS_DIRECTORY_NAME` for the directory name each of those trees carries in a package source and under `~/.claude` — read by the copy loops, the hooks.json reads, the git-hook shims, the mypy configuration, and the prunes alike — `SETTINGS_FILE_NAME` for the settings file the merge, the retired-hook prune, and the uninstall purge share, and `MYPY_INI_FILE_NAME` for the home-directory file `install_mypy_ini.mjs` writes |
| `ever-shipped-skills.mjs` | Static `EVER_SHIPPED_SKILL_NAMES` set of every top-level skill directory name the package has shipped; the installer subtracts the current skill set from it to prune retired skills left under `~/.claude/skills` |
| `expand_home_directory_tokens.mjs` | Expands residual `$HOME` / `${HOME}` / `~/` tokens in settings.json hook and statusLine commands to absolute home paths at install time (literal-safe for homes that contain `$`) |
| `git_hooks_installer.mjs` | Installs or updates the `pre-commit`, `pre-push`, and `post-commit` Git hooks in the user's git config; writes hook scripts that delegate to the installed Python hooks |
| `install_mypy_ini.mjs` | Writes `~/.mypy.ini` with settings that make mypy find the hooks package and enforce strict type checking |
| `install.test.mjs` | Unit tests for `install.mjs` — covers conflict detection, interpreter detection, settings merging, the settings shapes the installer never wrote that every hook walk hands back untouched, the source-artifact skip in `collectFiles`, the case-only rename decision and the `copyTree` copy that acts on it, the retired-hook diff and settings prune, and the stale-file prune: the manifest diff, path-key case folding, emptied-parent cleanup, and the warn-and-keep paths |
| `install.prune.test.mjs` | End-to-end prune tests that run the real installer against a sandbox `HOME` — retired-skill, retired-hook, and stale-file moves into one timestamped backup, the settings entry a retired hook loses, the top-level paths every root's diff leaves alone, the manifest record a failed move keeps, the full-install and resolved-dependency gates, backup retention, and the uninstall: the `~/.mypy.ini` removal, the containment guard, and nested-directory cleanup |
| `git_hooks_installer.test.mjs` | Tests for `git_hooks_installer.mjs` |
| `install_mypy_ini.test.mjs` | Tests for `install_mypy_ini.mjs` |

## Source build artifacts

`collectFiles` walks the package source and skips the artifacts a contributor's tooling writes beside it: the entry names `__pycache__`, `.ruff_cache`, `.pytest_cache`, `.mypy_cache`, `node_modules`, `.DS_Store`, and any file ending `.pyc` or `.pyo`. A skipped directory takes everything under it out of the walk. `.npmignore` keeps the same artifacts out of the published tarball, so an `npx` install reads a clean tree; the walk covers a local `node bin/install.mjs` run against a working tree that holds them.

The skip and the cleanup of artifacts an earlier install copied are one code path. A `.pyc` under `~/.claude/skills` that a prior manifest records sits outside the set the walk returns, so the next full install reads it as stale and moves it into that run's backup root. An artifact recorded under another managed root leaves the manifest on that same run, so `--uninstall` stops naming it.

## Copying a file whose name changed letter case

`copyTree` renames a destination entry that differs from the shipped file name only in letter case to the shipped name, then copies. On a case-insensitive volume `copyFileSync` writes its bytes through whichever entry the filesystem resolves the path to, so a package shipping `README.md` over an installed `Readme.md` would fill the installed entry and leave the earlier spelling standing. The rename runs first because `renameSync` inside one directory is atomic: a run interrupted between the rename and the copy leaves the file present under the shipped name holding the earlier content, which the next install overwrites.

The decision reads the destination directory's entry names, cached one listing per directory for the whole copy run. On a case-sensitive volume the two names are two files, so the rename is skipped and each name keeps its own content. `caseOnlyRenameSourceName(shippedName, existingNames, options)` holds the decision, and `options.isCaseInsensitive` carries the platform answer as a value so a test drives either branch on a host of either kind.

## Retired-skill prune

The full-install prune renames a retired skill directory into a timestamped backup rather than deleting it. Each pruned directory is renamed to `~/.claude/.claude-dev-env-pruned/<timestamp>/skills/<skill-name>/`, a backup root outside `~/.claude/skills` so a backed-up directory is never re-discovered as a skill. The `skills/` segment mirrors `~/.claude`, matching the layout the stale-file prune writes, so one recovery point reads as a copy of the tree it came from. One run shares one timestamped root, so a run leaves one recovery point. A rename that fails leaves the directory in place with a logged warning and never falls back to deletion, so a prune failure costs at most a cosmetic leftover.

Matching is by directory name alone, so a user-authored directory whose name collides with a retired skill is backed up as if it were that skill. A directory is pruned when the prior install's manifest recorded it or the ever-shipped set names it, and the current install did not just write it. A name absent from all three of those sets, together with `~/.claude/skills/_shared`, is left in place. Recovery of a wrongly-matched directory runs until the next pruning install, which keeps its own backup and retires the rest.

## Stale-file prune

A full install also moves aside a file under a managed root that the run leaves unwritten. `copyTree` adds and overwrites but never removes, so every root the installer writes carries the same drift, and the prune covers all of them: `rules`, `docs`, `commands`, `agents`, `system-prompts`, `scripts`, `_shared`, `audit-rubrics`, `skills`, and `hooks` — the names in `MANAGED_TOP_LEVEL_DIRECTORY_NAMES`.

Nothing moves unless a prior install recorded it. That single rule is what makes covering ten roots as safe as covering one: the installer reads the file list from `~/.claude/.claude-dev-env-manifest.json`, subtracts every file the run copied across all source roots, and moves what remains.

The prune runs once per root, each call confined to its own root. Per-root iteration gives the containment guard and the emptied-parent walk the root that owns each file, and it settles `_shared`: `~/.claude/_shared` and `~/.claude/skills/_shared` are distinct absolute paths, so the `_shared` call and the `skills` call each see their own files and no path enters two diffs. Each root's content lands under `~/.claude/.claude-dev-env-pruned/<timestamp>/<root-name>/<relative>`, so the backup mirrors `~/.claude`. Every prune in a run shares that one timestamped root. A recorded path under no managed root — `~/.claude/CLAUDE.md`, `settings.json`, the manifest itself, and the `~/.mypy.ini` that sits in the home directory beside `~/.claude` — reaches no root's diff and stays where it is. The install summary reports the skills root's own count on the `skills:` line and the sum across roots on its own line.

The manifest diff limits the move to files the installer itself wrote. Runtime-generated content — a Python `__pycache__` entry, a ruff cache, a log — and any file a user authored under a managed root stay in place, because no install recorded them. Path comparison ignores letter case on Windows and macOS, so a package shipping `README.md` over an installed `Readme.md` keeps the bytes the run just wrote. A directory or a link standing where the manifest records a file is skipped with a warning, so the mover never renames a whole tree and never follows a link out of `~/.claude`. A directory emptied by a move is removed, walking up to the root the file sat under. A move that fails logs a warning and leaves the file in place, so a prune failure costs at most a stale file. The installer records each such path in the fresh manifest when the file is still on disk, so the file stays inside the next full install's diff and gets another attempt.

A missing or unreadable manifest, or one carrying no file list, holds the stale-file prune for that run: with no record of what an install wrote, the run has nothing to diff against.

A run writes both manifest keys — the file list and the skill-name list — wholesale from what it just installed only when the prunes ran that run and read the prior record all the way through, so the next diff reads as "the package stopped shipping this". Every other run unions what it wrote onto the prior lists: a scoped `--only` install, a full install holding its prunes behind an unresolved dependency group, and a run whose prune step ends early with a logged warning. The union keeps every entry a later prune needs to spot a stale file or a retired skill, and keeps `--uninstall` able to name the whole tree. The prune itself bounds the lists: a stale path leaves the record on the first full install that moves it aside.

## Retired-hook entries in settings.json

A hook script under `~/.claude/hooks` carries a second reference: the `settings.json` entry that runs it. A full install removes that entry in the same run that moves the script aside, and removes it first — a `settings.json` naming a script that has left the hooks directory makes every session start invoke a missing file.

The retired set comes from the manifest diff alone: the hook files a prior install recorded that this run leaves unwritten, each taken relative to `~/.claude/hooks`. A script the run still writes stays out of the set, and a path no install of ours recorded never enters it, so a user-authored hook is out of reach of the prune. Each command is matched on the anchored `/.claude/hooks/<relative>` tail the merge uses to tell this installer's entries from a user's, so a command whose path is a retired tail plus a suffix (`retired_gate.py.bak`) names another file and stays.

The walk covers every event type the settings file holds rather than the ones the current `hooks.json` names, so an entry under an event type the package stopped shipping is reached too. A matcher group left empty is dropped, and an event type left empty goes with it. The file is written once, and only when an entry left it, so a run that retires no hook leaves `settings.json` byte-identical.

Every settings walk — this prune, the merge, and the uninstall purge — recognizes the shapes the installer writes and hands back the rest. An event type whose value is not an array of groups, a matcher group carrying no `hooks` array, and a hook entry whose `command` is not a string each survive untouched, so a hand-edited or third-party `settings.json` carries an install through rather than ending it.

## Backup retention

A run that moves content writes `~/.claude/.claude-dev-env-pruned/<timestamp>/` and then retires the other run backups, so the directory holds the one recovery point closest to what sits on disk. The sweep removes a direct child whose name matches the installer's timestamp shape (`2026-07-25T18-04-11-923Z`), which leaves anything else under the pruned-backup directory in place, along with the directory itself. A removal that fails logs a warning and the sweep carries on, so retention never ends an install. The install output names the count when the sweep removes anything.

A run that moves nothing writes no backup root and sweeps nothing, so every recovery point the user holds stays where it is.

## Uninstall

`--uninstall` reads the manifest and removes each file it records.

Each record passes a containment guard first: the path resolves under `~/.claude`, or it names the `~/.mypy.ini` the install writes in the home directory. Every other record is skipped with a warning and counted. Skipping keeps one malformed record — hand-edited, or written by an installer that ran against a different home — from stranding the user with a half-removed install. The purge removes every legitimate record, clears the manifest, and reports the skipped count.

Removing a file leaves its directory a candidate for cleanup. Once the file loop ends, the purge walks up from each such directory to the managed top-level directory the file sits under (`MANAGED_TOP_LEVEL_DIRECTORY_NAMES`), removing each directory it finds empty. That reaches a nested tree such as `skills/<name>/scripts/`. A record under no managed root gets no walk, so `~/.claude` itself is never a stop root and a directory the installer never wrote stays. A separate pass drops each managed top-level directory the purge empties.

## Prune gates

Every prune runs behind the same two gates: a full install, and every declared dependency group resolved. When any dependency group fails to resolve, all of them are skipped for the whole run with a logged notice naming the unresolved group. An unresolved dependency contributes no skills to the installed set, so a live skill that a dependency package supplies would look retired and its files would look stale; holding every prune until each dependency resolves keeps that skill's files in place and keeps their manifest records, so a run with every dependency resolved can still prune them.

## Key exports from install.mjs

| Export | Description |
|---|---|
| `CONTENT_DIRECTORIES` | Array of package subdirectory names copied verbatim to `~/.claude/` |
| `MANAGED_TOP_LEVEL_DIRECTORY_NAMES` | The content directories plus `skills` and `hooks`; the stale-file prune walks it to give each root its own diff, and the uninstall purge reads it to find the root a recorded file belongs to |
| `collectFiles(directory)` | Lists every file under a source directory, skipping the build-artifact names and extensions in `install-constants.mjs` |
| `pythonCandidatesForPlatform(platform)` | Returns ordered Python interpreter candidates to probe; `py -3` first on Windows to avoid Microsoft Store alias issues |
| `isWindowsStorePythonStub(path)` | Returns true when the path resolves to the non-spawnable WindowsApps stub |
| `interpreterCommandFromPath(path)` | Formats an absolute interpreter path as a settings.json hook command prefix |
| `collectPackageSourceConflicts(dir)` | Returns any unmerged git conflicts in the package source; installer aborts when any exist |
| `pruneStaleInstalledFiles(priorFiles, currentFiles, destinationRoot, backupRoot, options)` | Moves each manifest-recorded file under the destination root that the run leaves unwritten into the run's backup root; returns `{ prunedCount, failedPaths }`. `options.isCaseInsensitive` drives path-key case folding, defaulting to this host's filesystem; `options.managedHomeDirectory` sets the home the containment guard tests against, defaulting to `~/.claude` |
| `copyTree(sourceBase, destBase, options)` | Copies every file under a source directory, renaming a destination entry that differs from the shipped name only in letter case to the shipped name first; returns `{ created, updated, paths }`. `options.isCaseInsensitive` drives that rename, defaulting to this host's filesystem |
| `caseOnlyRenameSourceName(shippedName, existingNames, options)` | Returns the existing directory entry a shipped file name would overwrite through a case-only spelling difference, or null; `options.isCaseInsensitive` defaults to this host's filesystem |
| `retiredManagedHookRelativePaths(priorFiles, currentFiles, hooksRoot)` | Returns the hook script paths a prior install recorded under the hooks root that this run leaves unwritten, each relative to that root |
| `pruneRetiredHookEntriesFromSettings(settingsPath, retiredPaths)` | Removes each settings.json entry running a retired managed hook script, writing the file only when an entry left it; returns the removed count |
| `comparisonKeyForPath(path, options)` | Builds the key two paths are compared through: resolved, forward-slashed, and lowercased when `options.isCaseInsensitive` holds — which defaults to true on Windows and macOS |

## Install groups

`install.mjs` defines install groups (`core`, `journal`) plus any dependency groups discovered from `package.json` `dependencies`. The `core` group installs skills, all hooks, and the content directories. `journal` installs only its skill set.
