# bin

The installer and its companion modules. Running `npx claude-dev-env` (or `node bin/install.mjs`) copies package files into the managed root (`~/.claude/` by default; `CLAUDE_CONFIG_DIR` or `--target` selects another), copies skills and agents into the agents home (`~/.agents/` for the default root) and publishes directory pointers at `skills/` and `agents/` under the managed root, merges hook entries into that root's `settings.json`, installs Git hooks, writes `~/.mypy.ini` under the process home, and copies Codex exec-policy files into `~/.codex/rules` (`CODEX_HOME/rules` when that variable is set), and generates Cursor `.mdc` files into `~/.cursor/rules` from the installed Claude rules.

## Files

| File | Purpose |
|---|---|
| `install.mjs` | Main installer: builds a read-only plan via `install-plan.mjs`, then runs mutations inside `install-transaction.mjs` recovery (publish skill/agent lookup pointers, copy content directories, merge hooks, install skills, prune, git hooks, mypy.ini); routes `CLAUDE_HOME`, the agents home, the manifest path, and `~/.mypy.ini` through `resolve-install-root.mjs`; resolves single or multi-profile targets before mutation and writes one ownership manifest per target |
| `resolve-install-root.mjs` | Pure install-root resolver: precedence `--target` > `CLAUDE_CONFIG_DIR` > `~/.claude`, sibling `.agents` home (or `<root>.agents` for a named profile), separator-boundary containment, and the declared external allowlist for `~/.mypy.ini` plus files under the Codex rules directory, the Cursor home, and the agents home |
| `resolve-package-managed-directory.mjs` | Package-source resolver: skills and agents under `.agents/<name>/`, with a package-root `<name>/` fallback for dependency packages |
| `resolve-package-managed-directory.test.mjs` | Real-filesystem tests for the source resolver plus the live package `.agents` trees and `.claude` pointers |
| `publish-directory-pointer.mjs` | Directory-pointer helper: POSIX symlink or Windows junction from a Claude lookup path to the agents home; relocates a real directory at the lookup path into the target |
| `publish-directory-pointer.test.mjs` | Real-filesystem tests for pointer create, refresh, relocate, and unlink |
| `select-install-targets.mjs` | Pure target selection for main-default, explicit `--target`, and `--profile`/`--profiles`; rejects ambiguous or duplicate targets; builds per-target manifest records with `targetIdentity` and `managedRoot` |
| `install-plan.mjs` | Read-only install and uninstall plans: install preflight (managed root, source conflicts, Python, settings when hooks install) and uninstall preflight (settings JSON before removal, removable vs skipped manifest records), freezes plans E2/F execute |
| `install-transaction.mjs` | Install, update, and uninstall transaction journal: captures prior settings, manifest, managed files, and `core.hooksPath`, restores them on failure, and supports fault injection phases for recovery tests |
| `install.transaction.test.mjs` | Unit and sandbox installer tests for snapshot/restore and fault phases (`after_file_staging`, `after_settings_write`, `after_git_config`, `after_manifest_write`) |
| `install.uninstall-transaction.test.mjs` | Uninstall plan preflight and recovery: malformed/non-object settings fail before removal, each fault phase restores files/settings/manifest/`core.hooksPath`, retry succeeds, selected-root containment |
| `install.profile-root.test.mjs` | Contract tests for the install-root resolver: precedence, containment boundary, external allowlist, agents-home pairing, and the install.mjs import smoke check |
| `install.agents-home.test.mjs` | End-to-end tests that a sandbox install writes skills and agents under `.agents` and publishes `.claude/skills` and `.claude/agents` as directory pointers |
| `install.codex-rules.test.mjs` | Tests that Codex exec-policy files copy to `~/.codex/rules`, honor `CODEX_HOME`, skip `--only journal`, and uninstall without touching `default.rules` |
| `install.cursor-rules.test.mjs` | Tests that Cursor `.mdc` files generate into `~/.cursor/rules` from Claude rules, skip `--only journal`, and leave a local extra `.mdc` in place |
| `install-constants.mjs` | The named values `install.mjs` reads: `SKIPPED_SOURCE_ENTRY_NAMES` and `SKIPPED_SOURCE_FILE_EXTENSIONS` for the build artifacts the source walk leaves behind, `RUN_BACKUP_DIRECTORY_NAME_PATTERN` for the timestamp shape a run backup directory carries, `PACKAGE_AGENTS_HOME_DIRECTORY_NAME` for the `.agents` source home, `MANAGED_SKILLS_DIRECTORY_NAME` and `MANAGED_AGENTS_DIRECTORY_NAME` for the directory name each of those trees carries in a package source and under the agents home — read by the copy loops, the pointer publisher, and the prunes alike — `MANAGED_HOOKS_DIRECTORY_NAME` for the hooks tree under `~/.claude`, `SETTINGS_FILE_NAME` for the settings file the merge, the retired-hook prune, and the uninstall purge share, and `MYPY_INI_FILE_NAME` for the home-directory file `install_mypy_ini.mjs` writes, plus the Codex home and rules directory names `resolve-install-root.mjs` uses |
| `ever-shipped-skills.mjs` | Static `EVER_SHIPPED_SKILL_NAMES` set of every top-level skill directory name the package has shipped; the installer subtracts the current skill set from it to prune retired skills left under `~/.agents/skills` |
| `expand_home_directory_tokens.mjs` | Expands residual `$HOME` / `${HOME}` / `~/` tokens in settings.json hook and statusLine commands to absolute home paths at install time (literal-safe for homes that contain `$`) |
| `git_hooks_installer.mjs` | Installs or updates the `pre-commit`, `pre-push`, and `post-commit` Git hooks in the user's git config; writes hook scripts that delegate to the installed Python hooks |
| `install_mypy_ini.mjs` | Writes `~/.mypy.ini` with settings that make mypy find the hooks package and enforce strict type checking |
| `install.test.mjs` | Unit tests for `install.mjs` — covers conflict detection, interpreter detection, settings merging, the settings shapes the installer never wrote — those every hook walk hands back untouched, and the shipped-event value the merge replaces with a warning — the source-artifact skip in `collectFiles`, the case-only rename decision and the `copyTree` copy that acts on it, the retired-hook diff and settings prune, the stale-file prune: the manifest diff, path-key case folding, emptied-parent cleanup, and the warn-and-keep paths, and backup retention: the sweep a moved-content run drives, the empty root a run whose moves failed gives up, and the populated root retention keeps |
| `install.profiles.test.mjs` | Profile target-selection and per-target ownership manifest contract tests (main-default, multi-profile, ambiguity/duplicate rejection, help text) |
| `install.plan.test.mjs` | Read-only plan and preflight tests: zero-write plan construction, source-conflict and missing-Python fail-closed, settings check only when hooks install, tolerant broken-manifest, invalid managed root, mutation-kind list for E2 |
| `install.prune.test.mjs` | End-to-end prune tests that run the real installer against a sandbox `HOME` — retired-skill, retired-hook, and stale-file moves into one timestamped backup, the settings entry a retired hook loses, the top-level paths every root's diff leaves alone, the manifest record a failed move keeps, the full-install and resolved-dependency gates, backup retention, and the uninstall: the `~/.mypy.ini` removal, the containment guard, and nested-directory cleanup |
| `git_hooks_installer.test.mjs` | Tests for `git_hooks_installer.mjs` |
| `install_mypy_ini.test.mjs` | Tests for `install_mypy_ini.mjs` |

## Source build artifacts

`collectFiles` walks the package source and skips the artifacts a contributor's tooling writes beside it: the entry names `__pycache__`, `.ruff_cache`, `.pytest_cache`, `.mypy_cache`, `node_modules`, `.DS_Store`, and any file ending `.pyc` or `.pyo`. A skipped directory takes everything under it out of the walk. The `files` negations in `package.json` (`!**/__pycache__/**`, `!**/*.py[cod]`, the cache directories, `!**/*.log`, `!**/*.egg-info/**`) keep the same artifacts out of the published tarball, and `.npmignore` carries those patterns for tooling that reads it — keep the two in step. An `npx` install reads a clean tree; the walk covers a local `node bin/install.mjs` run against a working tree that holds the artifacts.

The skip and the cleanup of artifacts an earlier install copied are one code path. A `.pyc` a prior manifest records under any managed root sits outside the set the walk returns, so the next full install reads it as stale, moves it into that run's backup root, and drops it from the manifest the run writes.

## Copying a file whose name changed letter case

`copyTree` renames a destination entry that differs from the shipped file name only in letter case to the shipped name, then copies. On a case-insensitive volume `copyFileSync` writes its bytes through whichever entry the filesystem resolves the path to, so a package shipping `README.md` over an installed `Readme.md` would fill the installed entry and leave the earlier spelling standing. The rename runs first because `renameSync` inside one directory is atomic: a run interrupted between the rename and the copy leaves the file present under the shipped name holding the earlier content, which the next install overwrites.

The decision reads the destination directory's entry names, cached one listing per directory for the whole copy run. On a case-sensitive volume the two names are two files, so the rename is skipped and each name keeps its own content. `caseOnlyRenameSourceName(shippedName, existingNames, options)` holds the decision, and `options.isCaseInsensitive` carries the platform answer as a value so a test drives either branch on a host of either kind.

## Retired-skill prune

The full-install prune renames a retired skill directory into a timestamped backup rather than deleting it. Each pruned directory is renamed to `~/.claude/.claude-dev-env-pruned/<timestamp>/skills/<skill-name>/`, a backup root outside `~/.agents/skills` so a backed-up directory is never re-discovered as a skill. The `skills/` segment matches the layout the stale-file prune writes, so one recovery point reads as a copy of the tree it came from. One run shares one timestamped root, so a run leaves one recovery point. A rename that fails leaves the directory in place with a logged warning and never falls back to deletion, so a prune failure costs at most a cosmetic leftover.

Matching is by directory name alone, so a user-authored directory whose name collides with a retired skill is backed up as if it were that skill. A directory is pruned when the prior install's manifest recorded it or the ever-shipped set names it, and the current install did not just write it. A name absent from all three of those sets, together with `~/.agents/skills/_shared`, is left in place. Recovery of a wrongly-matched directory runs until the next pruning install, which keeps its own backup and retires the rest.

## Stale-file prune

A full install also moves aside a file under a managed root that the run leaves unwritten. `copyTree` adds and overwrites but never removes, so every root the installer writes carries the same drift, and the prune covers all of them: `rules`, `docs`, `commands`, `agents`, `system-prompts`, `scripts`, `_shared`, `audit-rubrics`, `skills`, and `hooks` — the names in `MANAGED_TOP_LEVEL_DIRECTORY_NAMES`.

Nothing moves unless a prior install recorded it. That single rule is what makes covering ten roots as safe as covering one: the installer reads the file list from `~/.claude/.claude-dev-env-manifest.json`, subtracts every file the run copied across all source roots, and moves what remains.

The prune runs once per root, each call confined to its own root. Per-root iteration gives the containment guard and the emptied-parent walk the root that owns each file, and it settles `_shared`: `~/.claude/_shared` and `~/.agents/skills/_shared` are distinct absolute paths, so the `_shared` call and the `skills` call each see their own files and no path enters two diffs. Each root's content lands under `~/.claude/.claude-dev-env-pruned/<timestamp>/<root-name>/<relative>`. Every prune in a run shares that one timestamped root. A recorded path under no managed root — `~/.claude/CLAUDE.md`, `settings.json`, the manifest itself, and the `~/.mypy.ini` that sits in the home directory beside `~/.claude` — reaches no root's diff and stays where it is. The install summary reports the skills root's own count on the `skills:` line and the sum across roots on its own line.

The manifest diff limits the move to files the installer itself wrote. Runtime-generated content — a Python `__pycache__` entry, a ruff cache, a log — and any file a user authored under a managed root stay in place, because no install recorded them. Path comparison ignores letter case on Windows and macOS, so a package shipping `README.md` over an installed `Readme.md` keeps the bytes the run just wrote. A directory or a link standing where the manifest records a file is skipped with a warning, so the mover never renames a whole tree and never follows a link out of `~/.claude`. A directory emptied by a move is removed, walking up to the root the file sat under. A move that fails logs a warning and leaves the file in place, so a prune failure costs at most a stale file. The installer records each such path in the fresh manifest when the file is still on disk, so the file stays inside the next full install's diff and gets another attempt.

A missing or unreadable manifest, or one carrying no file list, holds the stale-file prune for that run: with no record of what an install wrote, the run has nothing to diff against.

A run writes both manifest keys — the file list and the skill-name list — wholesale from what it just installed only when the prunes ran that run and read the prior record all the way through, so the next diff reads as "the package stopped shipping this". Every other run unions what it wrote onto the prior lists: a scoped `--only` install, a full install holding its prunes behind an unresolved dependency group, and a run whose prune step ends early with a logged warning. The union keeps every entry a later prune needs to spot a stale file or a retired skill, and keeps `--uninstall` able to name the whole tree. The prune itself bounds the lists: a stale path leaves the record on the first full install that moves it aside.

## Retired-hook entries in settings.json

A hook script under `~/.claude/hooks` carries a second reference: the `settings.json` entry that runs it. A full install removes that entry in the same run that moves the script aside, and removes it first — a `settings.json` naming a script that has left the hooks directory makes every session start invoke a missing file.

The retired set comes from the manifest diff alone: the hook files a prior install recorded that this run leaves unwritten, each taken relative to `~/.claude/hooks`. A script the run still writes stays out of the set, and a path no install of ours recorded never enters it, so a user-authored hook is out of reach of the prune. Each command is matched on the anchored `/.claude/hooks/<relative>` tail the merge uses to tell this installer's entries from a user's, so a command whose path is a retired tail plus a suffix (`retired_gate.py.bak`) names another file and stays.

The walk covers every event type the settings file holds rather than the ones the current `hooks.json` names, so an entry under an event type the package stopped shipping is reached too. A matcher group left empty is dropped, and an event type left empty goes with it. The file is written once, and only when an entry left it, so a run that retires no hook leaves `settings.json` byte-identical.

Every settings walk recognizes the shapes the installer writes and steps around the rest, so a hand-edited or third-party `settings.json` carries an install through rather than ending it. A matcher group carrying no `hooks` array and a hook entry whose `command` is not a string survive every walk untouched. An event type whose value is not an array of groups survives this prune and the uninstall purge; the merge replaces that value with the group list it ships for that event type, warning with the event type named so the user can recover the value from their own history. An event type the package ships no groups for keeps whatever value the file holds.

## Backup retention

A run that moves content into `~/.claude/.claude-dev-env-pruned/<timestamp>/` then retires the other run backups, so the directory holds the one recovery point closest to what sits on disk. The retired-skill prune and the stale-file prune each report how many moves succeeded, and their sum is the signal the sweep answers to. The sweep removes a direct child whose name matches the installer's timestamp shape (`2026-07-25T18-04-11-923Z`), which leaves anything else under the pruned-backup directory in place, along with the directory itself. A removal that fails logs a warning and the sweep carries on, so retention never ends an install. The install output names the count when the sweep removes anything.

A run that moves nothing sweeps nothing, so every recovery point the user holds stays where it is. `moveIntoRunBackup` creates the directories leading to a backup path before it renames, so a run whose every move fails — the antivirus scanner or open editor case — leaves that timestamped root standing empty. Retention clears it with `rmdirSync` alone, depth first, so a directory holding anything survives every step.

## Uninstall

`--uninstall` builds a read-only uninstall plan, captures a recovery snapshot, then removes each file the plan lists.

Settings JSON is validated before any removal. A malformed or non-object `settings.json` fails closed with the managed files still on disk. Each manifest record passes a containment guard: the path resolves under `~/.claude`, or it names the `~/.mypy.ini` the install writes in the home directory, or it sits under the Codex rules directory, or it sits under the Cursor home, or it sits under the agents home. Every other record is skipped with a warning and counted. Skipping keeps one malformed record — hand-edited, or written by an installer that ran against a different home — from stranding the user with a half-removed install. The purge removes every legitimate record, clears the manifest, and reports the skipped count.

The uninstall runs inside the same snapshot/restore journal as install: prior settings, manifest, managed files, and `core.hooksPath` restore when a later phase fails, so a retry starts from a complete ownership record. The journal is discarded only after a successful commit.

Removing a file leaves its directory a candidate for cleanup. Once the file loop ends, the purge walks up from each such directory to the managed top-level directory the file sits under (`MANAGED_TOP_LEVEL_DIRECTORY_NAMES`), removing each directory it finds empty. That reaches a nested tree such as `skills/<name>/scripts/`. A record under no managed root gets no walk, so `~/.claude` itself is never a stop root and a directory the installer never wrote stays. A separate pass drops each managed top-level directory the purge empties.

## Prune gates

Every prune runs behind the same two gates: a full install, and every declared dependency group resolved. When any dependency group fails to resolve, all of them are skipped for the whole run with a logged notice naming the unresolved group. An unresolved dependency contributes no skills to the installed set, so a live skill that a dependency package supplies would look retired and its files would look stale; holding every prune until each dependency resolves keeps that skill's files in place and keeps their manifest records, so a run with every dependency resolved can still prune them.

## Key exports from install.mjs

| Export | Description |
|---|---|
| `CONTENT_DIRECTORIES` | Array of package subdirectory names copied verbatim to `~/.claude/` (skills and agents are outside this list; they copy into the agents home) |
| `MANAGED_TOP_LEVEL_DIRECTORY_NAMES` | The content directories plus `skills`, `agents`, and `hooks`; the stale-file prune walks it to give each root its own diff, and the uninstall purge reads it to find the root a recorded file belongs to |
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
| `retainNewestRunBackupOnly(runBackupRoot, didRunMoveContent)` | Retires every run backup sitting beside the run's own when `didRunMoveContent` holds; clears the run's empty root with `rmdirSync` when it does not |
| `comparisonKeyForPath(path, options)` | Builds the key two paths are compared through: resolved, forward-slashed, and lowercased when `options.isCaseInsensitive` holds — which defaults to true on Windows and macOS |

## Install groups

`install.mjs` defines install groups (`core`, `journal`) plus any dependency groups discovered from `package.json` `dependencies`. The `core` group installs skills, all hooks, and the content directories. `journal` installs only its skill set.
