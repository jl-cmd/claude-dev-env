# Skill and Config Install System

How skills, rules, hooks, and other config travel from this repo to a user's `~/.claude/` directory. Read this before adding or changing a skill, or before touching the install pipeline.

## Where skills live

Each skill is a directory under `packages/claude-dev-env/skills/<name>/` with a `SKILL.md` file. The `SKILL.md` frontmatter holds:

- `name` — the skill id; this is what the user types as `/<name>`.
- `description` — one line covering what the skill does and its trigger phrases.
- `argument-hint` — optional, shown in the slash-command UI.

Skills are auto-discovered from the `skills/` directory. There is no manifest that lists them, so a new directory with a valid `SKILL.md` is a complete new skill on the source side.

## How the installer copies content

The entry point is `packages/claude-dev-env/bin/install.mjs`, run as `npx claude-dev-env` (full install) or `npx claude-dev-env --only <groups>` (scoped install). It copies into `~/.claude/`.

Two paths matter:

- **Whole directories.** `CONTENT_DIRECTORIES` lists folders copied as-is from the package root: `rules`, `docs`, `commands`, `agents`, `system-prompts`, `scripts`, `_shared`, `audit-rubrics`. Each maps to the same folder name under `~/.claude/`.
- **Skills.** Skill directories under `skills/` copy to `~/.claude/skills/<name>/`, with one filter described below. A full install also moves stale content out of `~/.claude/skills`, described below.

## Full install versus scoped install

`INSTALL_GROUPS` defines the built-in groups `core`, `journal`, and `research`, plus any groups discovered from package dependencies. Each group can carry a `skills` allowlist, an `includeDirectories` list, hook flags, and rule lists.

The filter on skills depends on whether the user scoped the install:

- **Full install** (`npx claude-dev-env`, no `--only`): the allowlist is empty, so every skill directory under `skills/` copies. A new skill is picked up with no further wiring.
- **Scoped install** (`npx claude-dev-env --only core`): only skills named in the active groups' `skills` arrays copy. A new skill must be added to a group's `skills` array to install under a scoped run.

So a new skill that should ship as part of a named group (for example `core`) needs its name added to that group's `skills` array in `install.mjs`. A skill left out of every group still ships on a full install, but a scoped install skips it.

## Removing skill content the package drops

A full install moves two kinds of content out of `~/.claude/skills` into one timestamped backup directory per run, `~/.claude/.claude-dev-env-pruned/<timestamp>/`:

- **A retired skill directory** — a whole skill directory that the package leaves out of the set it ships, and that either the prior manifest's skills list or the ever-shipped set names. The directory keeps its name inside the backup. A directory the user created themselves, such as `~/.claude/skills/my-notes`, sits in neither of those sets and stays in place, as does `~/.claude/skills/_shared`.
- **A stale file inside a live skill** — a file that the install manifest, `~/.claude/.claude-dev-env-manifest.json`, records under `~/.claude/skills` and that the run leaves unwritten. Each moved file mirrors its relative path inside the backup directory, and a directory the move empties is removed up to the skills directory.

Both prunes move content rather than delete it, so anything caught by mistake is recoverable from the backup. A move that fails logs a warning and leaves the content in place; a stale file whose move fails stays on the fresh manifest record, so the next full install retries it.

The stale-file comparison reads the manifest, so it touches only files an install wrote. Runtime-generated content — a Python `__pycache__` entry, a ruff cache, a log — and any file a user authored inside a skill directory stay in place, because no install recorded them. Path comparison ignores letter case on Windows and macOS.

Both prunes run behind the same two gates: a full install, and every dependency group resolved. An unresolved dependency contributes no skills, so a live skill it supplies would look retired and its files would look stale; holding both prunes keeps that content safe.

A full install writes the manifest's file list wholesale from what it just installed, so the next diff reads as "the package stopped shipping this". A scoped `--only` install unions what it wrote onto the prior list, which holds every entry a later full install needs to spot a stale file.

## Dependency groups

`discoverDependencyGroups()` reads the package dependencies and turns each one that has a `skills/` directory into its own install group. The group name comes from the dependency's `claudeDevEnv.groupName`, or the bare package name. This is how skills from packages such as `@jl-cmd/prompt-generator` join the install set.

## Checklist: adding a new skill

1. Create `packages/claude-dev-env/skills/<name>/SKILL.md` with `name`, `description`, and trigger phrases.
2. To ship it in a scoped group, add `<name>` to that group's `skills` array in `packages/claude-dev-env/bin/install.mjs` (for example the `core` group).
3. Add a row to the matching group table in `README.md` so the documented skill set stays correct.
4. A full install copies the skill on its own; a scoped install relies on step 2.

## Related files

- `packages/claude-dev-env/bin/install.mjs` — the install pipeline.
- `packages/claude-dev-env/bin/install.test.mjs` — install behavior tests.
- `README.md` — the documented group and skill tables.
- `docs/ai-rules-sync.md` — how rules sync to other tools.
