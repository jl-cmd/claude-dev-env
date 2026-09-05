# Skill archive

This directory holds 19 retired Claude Dev Environment skills, copied unchanged from `packages/claude-dev-env/.agents/skills/` at commit `f5a984af48df0eb0f87f5211d4e92421c38df91b`. Each copy includes scripts, tests, templates, references, and instruction files. `source-trees.json` records the source commit and original Git tree ID for every skill.

The older archive at `packages/claude-dev-env/.agents/skills-archived/` stays in place. This batch uses the same unpacked-directory format at `skill-archive/`.

## Retired skills

- `hitl`
- `autoconverge`
- `pr-cleanup`
- `pr-name-by-capability`
- `pr-plain-language-cleanup`
- `pr-refinement`
- `pr-shared-extraction`
- `pr-small-cl`
- `pr-title-description`
- `prototype`
- `rebase`
- `review-router`
- `review-tier`
- `run-claude-dev-env`
- `session-log`
- `session-tidy`
- `skill-builder`
- `source-command-sr-loop`
- `update`

The request named `pr-name-by-compatibility`. The repository skill is `pr-name-by-capability`, archived under that name.

## Skill builder stub

Active `skill-builder/SKILL.md` is the placeholder:

> TODO: Rework to follow pstack philosophy.

Its instruction files stay beside the stub. The former implementation is in this archive.

## Recovery

Installers read `packages/claude-dev-env/.agents/skills/`. This archive sits outside the installable package. `bin/ever-shipped-skills.mjs` still lists every retired name so full-install cleanup can remove leftover copies. `skill-builder` stays installed as the stub.

To apply this in a local environment, install the changed package. Installer group labels and historical references still name some of these skills.

To restore a skill, copy its archived directory back into the active skills directory. Review its dependencies, then reinstall. The source commit also still has each skill at its original path.
