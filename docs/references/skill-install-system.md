# Skill and Config Install System

How skills, rules, hooks, and other config travel from this repo to a user's
`~/.claude/` directory, with skills and agents living under `~/.agents/`. Read
this before adding or changing a skill, or before touching the install pipeline.

## Where skills live

Each skill is a directory under `packages/claude-dev-env/skills/<name>/` with a `SKILL.md` file. The `SKILL.md` frontmatter holds:

- `name` — the skill id; this is what the user types as `/<name>`.
- `description` — one line covering what the skill does and its trigger phrases.
- `argument-hint` — optional, shown in the slash-command UI.

Skills are auto-discovered from the `skills/` directory. There is no manifest that lists them, so a new directory with a valid `SKILL.md` is a complete new skill on the source side.

Installed skills live at `~/.agents/skills/<name>/`. Claude Code discovers them at `~/.claude/skills/<name>/`, which is a directory pointer (a POSIX symlink, or a Windows junction) to that agents-home folder. Agent definition files follow the same rule: they live at `~/.agents/agents/` and `~/.claude/agents` points there. Rules, hooks, commands, docs, and `settings.json` stay under `~/.claude/`.

## How the installer copies content

The entry point is `packages/claude-dev-env/bin/install.mjs`, run as `npx claude-dev-env` (full install) or `npx claude-dev-env --only <groups>` (scoped install). It copies into `~/.claude/`, writes skills and agents into `~/.agents/` and publishes directory pointers at `~/.claude/skills` and `~/.claude/agents`, writes `~/.mypy.ini` (so mypy finds the installed hooks), copies Codex exec-policy files from `codex-rules/` into `~/.codex/rules` (`CODEX_HOME/rules` when that variable is set), and generates Cursor `.mdc` files into `~/.cursor/rules` from the installed Claude rules. Those destinations go on the manifest, so `--uninstall` names them.

Two paths matter:

- **Whole directories.** `CONTENT_DIRECTORIES` lists folders copied as-is from the package root: `rules`, `docs`, `commands`, `system-prompts`, `scripts`, `_shared`, `audit-rubrics`. Each maps to the same folder name under `~/.claude/`.
- **Skills and agents.** Skill directories under `skills/` copy to `~/.agents/skills/<name>/`. The `agents/` tree copies to `~/.agents/agents/`. The installer then publishes `~/.claude/skills` → `~/.agents/skills` and `~/.claude/agents` → `~/.agents/agents`. A full install also moves stale content out of every managed root, described below. A real directory already sitting at a Claude lookup path is merged into the agents home, then the pointer is written, so a personal skill next to the packaged ones stays reachable.

The agents-home path is one rule in `resolveAgentsHome`: a managed root named `.claude` pairs with a sibling `.agents` (`~/.claude` → `~/.agents`). Any other managed root — a named profile directory or an explicit `--target` — pairs with a sibling named `<root-name>.agents`, so two profile directories keep separate skill and agent trees.

A destination entry whose name differs from the shipped file name only in letter case is renamed to the shipped name before the bytes land, so a package shipping `README.md` over an installed `Readme.md` leaves one file carrying the shipped spelling. On a case-sensitive volume the two names are two files and each keeps its own content.

The source walk skips the build artifacts a contributor's tooling writes beside the source: the entry names `__pycache__`, `.ruff_cache`, `.pytest_cache`, `.mypy_cache`, `node_modules`, `.DS_Store`, and any file ending `.pyc` or `.pyo`. A skipped directory takes everything under it out of the walk. The `files` negations in `packages/claude-dev-env/package.json` keep the same artifacts out of the published tarball, and `.npmignore` carries those patterns for tooling that reads it — keep the two in step. An `npx` install reads a clean tree; the walk covers a local `node bin/install.mjs` run against a working tree that holds the artifacts. The skip and the cleanup of artifacts an earlier install copied are one code path: a `.pyc` a prior manifest records under any managed root sits outside the set the walk returns, so the next full install reads it as stale and moves it aside.

## Full install versus scoped install

`INSTALL_GROUPS` defines the built-in groups `core` and `journal`, plus any groups discovered from package dependencies. Each group can carry a `skills` allowlist, an `includeDirectories` list, hook flags, and rule lists. `node bin/install.mjs --help` prints the live list, and `--only` accepts exactly those names.

The filter on skills depends on whether the user scoped the install:

- **Full install** (`npx claude-dev-env`, no `--only`): the allowlist is empty, so every skill directory under `skills/` copies. A new skill is picked up with no further wiring.
- **Scoped install** (`npx claude-dev-env --only core`): only skills named in the active groups' `skills` arrays copy. A new skill must be added to a group's `skills` array to install under a scoped run.

So a new skill that should ship as part of a named group (for example `core`) needs its name added to that group's `skills` array in `install.mjs`. A skill left out of every group still ships on a full install, but a scoped install skips it.

## Removing content the package drops

Nothing is moved aside unless a prior install recorded it. That single rule is what makes covering every managed root as safe as covering one, and it holds for each kind of content below.

A full install moves three kinds of content into one timestamped backup directory per run, `~/.claude/.claude-dev-env-pruned/<timestamp>/`:

- **A retired skill directory** — a whole skill directory that the package leaves out of the set it ships, and that either the prior manifest's skills list or the ever-shipped set names. The directory lands at `<timestamp>/skills/<skill-name>/`, mirroring the lookup tree Claude Code reads. A directory the user created themselves, such as `~/.agents/skills/my-notes`, sits in neither of those sets and stays in place, as does `~/.agents/skills/_shared`.
- **A stale file under any managed root** — a file that the install manifest, `~/.claude/.claude-dev-env-manifest.json`, records under `rules`, `docs`, `commands`, `system-prompts`, `scripts`, `_shared`, `audit-rubrics`, `skills`, `agents`, or `hooks`, and that the run leaves unwritten. The prune runs once per root, so each call is confined to its own root: `~/.claude/_shared` and `~/.agents/skills/_shared` are distinct absolute paths and no file enters two diffs. Each moved file lands at `<timestamp>/<root-name>/<relative>`, and a directory the move empties is removed up to the root it sat under. A recorded path under no managed root — `~/.claude/CLAUDE.md`, `settings.json`, the manifest itself, and the `~/.mypy.ini` that sits in the home directory beside `~/.claude` — reaches no diff and stays where it is.
- **The `settings.json` entry of a retired hook** — the entry that runs a hook script the run is moving aside. The entry goes first, before the script leaves `~/.claude/hooks`, so no window exists where a session start invokes a missing file. The retired set is the manifest diff under the hooks root, so a user-authored hook is outside it; each command is matched on the anchored `/.claude/hooks/<relative>` tail, so a command whose path is a retired tail plus a suffix names another file and stays. The walk covers every event type the settings file holds, so an entry under an event type the package stopped shipping is reached too. The file is written once, and only when an entry left it, so a run that retires no hook leaves `settings.json` byte-identical. Every settings walk — this prune, the hook merge, and the uninstall purge — recognizes the shapes the installer writes and steps around the rest: a matcher group carrying no `hooks` array and a hook entry whose `command` is not a string survive every walk untouched. An event type whose value is not an array of groups survives this prune and the uninstall purge; the hook merge replaces that value with the group list the package ships for that event type and warns with the event type named, and an event type the package ships no groups for keeps whatever value the file holds.

The prunes move content rather than delete it, so anything caught by mistake is recoverable from that run's backup until the next pruning install writes its own. A move that fails logs a warning and leaves the content in place; a stale file whose move fails stays on the fresh manifest record, so the next full install retries it.

The stale-file comparison reads the manifest, so it touches only files an install wrote. Runtime-generated content — a Python `__pycache__` entry, a ruff cache, a log — and any file a user authored under a managed root stay in place, because no install recorded them. Path comparison ignores letter case on Windows and macOS.

The prunes run behind the same two gates: a full install, and every dependency group resolved. An unresolved dependency contributes no skills, so a live skill it supplies would look retired and its files would look stale; holding every prune keeps that skill's files in place and keeps their manifest records, so a run with every dependency resolved can still prune them.

A run writes both manifest keys — the file list and the skill-name list — wholesale from what it just installed only when the prunes ran that run and read the prior record all the way through, so the next diff reads as "the package stopped shipping this". Every other run unions what it wrote onto the prior lists: a scoped `--only` install, a full install holding its prunes behind an unresolved dependency group, and a run whose prune step ends early with a logged warning. The union holds every entry a later prune needs to spot a stale file or a retired skill, and keeps `--uninstall` able to name the whole tree.

## Backup retention

A run that moves content into its timestamped backup directory then retires the other run backups under `~/.claude/.claude-dev-env-pruned/`, so the directory holds the one recovery point closest to what sits on disk. The retired-skill prune and the stale-file prune each report how many moves succeeded, and their sum is the signal the sweep answers to. The sweep removes a direct child whose name matches the installer's timestamp shape (`2026-07-25T18-04-11-923Z`), leaving anything else under the pruned-backup directory in place along with the directory itself. A removal that fails logs a warning and the sweep carries on, so retention never ends an install. The install output names the count when the sweep removes anything.

A run that moves nothing sweeps nothing, so every recovery point the user holds stays where it is. The mover creates the directories leading to a backup path ahead of each rename, so a run whose every move fails leaves that timestamped root standing empty; retention clears it with `rmdirSync` alone, depth first, so a directory holding anything survives.

## Uninstall

`npx claude-dev-env --uninstall` reads `~/.claude/.claude-dev-env-manifest.json` and removes each file it records.

Each record passes a containment guard first: the path resolves under `~/.claude`, or it names the `~/.mypy.ini` the install writes in the home directory, or it sits under the Codex rules directory the install writes, or it sits under the Cursor home, or it sits under the agents home (`~/.agents` for the default managed root). Every other record is skipped with a warning and counted. Skipping keeps one malformed record from stranding the user with a half-removed install — the purge removes every legitimate record, clears the manifest, and reports the skipped count.

Once the file loop ends, the purge walks up from each directory a removal touched to the managed top-level directory the file sits under, dropping each directory it finds empty. That reaches a nested tree such as `skills/<name>/scripts/`. A record under no managed root gets no walk, so `~/.claude` itself is never a stop root and a directory the installer never wrote stays.

## Dependency groups

`discoverDependencyGroups()` reads the package dependencies and turns each resolvable one into its own install group, carrying whatever `skills/`, `hooks/`, and `rules/` content that package ships. The group name comes from the dependency's `claudeDevEnv.groupName`, or the bare package name. This is how skills from packages such as `@jl-cmd/prompt-generator` join the install set. A dependency that fails to resolve logs a warning, contributes no group, and holds every prune for that run.

## Checklist: adding a new skill

1. Create `packages/claude-dev-env/skills/<name>/SKILL.md` with `name`, `description`, and trigger phrases.
2. To ship it in a scoped group, add `<name>` to that group's `skills` array in `packages/claude-dev-env/bin/install.mjs` (for example the `core` group).
3. Add a row to the matching group table in `README.md` so the documented skill set stays correct.
4. A full install copies the skill on its own; a scoped install relies on step 2.

## Related files

- `packages/claude-dev-env/bin/install.mjs` — the install pipeline.
- `packages/claude-dev-env/bin/resolve-install-root.mjs` — managed Claude root, agents home, and allowed destinations.
- `packages/claude-dev-env/bin/publish-directory-pointer.mjs` — lookup-path pointers (POSIX symlink or Windows junction).
- `packages/claude-dev-env/bin/install.test.mjs` — install behavior tests.
- `packages/claude-dev-env/bin/install.agents-home.test.mjs` — agents-home layout and pointer tests.
- `packages/claude-dev-env/bin/install.prune.test.mjs` — end-to-end prune and uninstall tests against a sandbox home.
- `README.md` — the documented group and skill tables.
