# Skill archive

This directory preserves 19 retired Claude Dev Environment skills from commit `f5a984af48df0eb0f87f5211d4e92421c38df91b`.

Each skill is a complete, unchanged copy of its original directory under `packages/claude-dev-env/.agents/skills/`, including its scripts, tests, templates, references, and instruction files. Git tree IDs in `source-trees.json` identify the exact source snapshots.

The repository's older archive remains at `packages/claude-dev-env/.agents/skills-archived/`. This batch uses the requested `skill-archive/` destination and the same unpacked-directory format.

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

The retirement request named `pr-name-by-compatibility`. The matching repository skill is `pr-name-by-capability`, preserved here under its existing name.

## Skill builder stub

The active `skill-builder/SKILL.md` contains the requested placeholder:

> TODO: Rework to follow pstack philosophy.

Its existing instruction files remain beside the stub. Its complete former implementation is preserved in this archive.

## Installation and recovery

Active skill discovery reads `packages/claude-dev-env/.agents/skills/`. This archive sits outside the installable package. The ever-shipped skill registry retains all retired names so the existing full-install retirement cleanup can recognize previously installed copies. `skill-builder` remains an installed skill through its stub.

This source change takes effect in a local environment after the changed package is installed. Installer group labels and historical references remain unchanged in this archival change.

To recover a skill, copy its archived directory back into the active skills directory and review its dependencies before reinstalling. The source commit above also preserves each skill at its original path.
