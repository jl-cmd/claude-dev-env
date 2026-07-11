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
- **Skills.** Skill directories under `skills/` copy to `~/.claude/skills/<name>/`, with one filter described below.

## Full install versus scoped install

`INSTALL_GROUPS` defines the built-in groups `core`, `journal`, and `research`, plus any groups discovered from package dependencies. Each group can carry a `skills` allowlist, an `includeDirectories` list, hook flags, and rule lists.

The filter on skills depends on whether the user scoped the install:

- **Full install** (`npx claude-dev-env`, no `--only`): the allowlist is empty, so every skill directory under `skills/` copies. A new skill is picked up with no further wiring.
- **Scoped install** (`npx claude-dev-env --only core`): only skills named in the active groups' `skills` arrays copy. A new skill must be added to a group's `skills` array to install under a scoped run.

So a new skill that should ship as part of a named group (for example `core`) needs its name added to that group's `skills` array in `install.mjs`. A skill left out of every group still ships on a full install, but a scoped install skips it.

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
