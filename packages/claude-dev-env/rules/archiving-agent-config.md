# Archiving a Rule, Skill, Agent, or Command

**When this applies:** Pruning agent configuration in this package — moving a
rule, skill, agent, or command out of service, and deciding whether one is
still used at all.

## Prove disuse before you remove

A prune is only as good as the usage evidence behind it, and three habits give
confident wrong answers here.

**Grepping the file's own name measures documentation, not use.** Enforcement in
this package is rarely named after the file that describes it. Resolve what the
file names instead: does the script exist, does the lint rule id appear in the
registry, does the check run. A rule with no mention of its slug anywhere can
still have a live checker behind it under a different name.

**Three files name every capability and prove nothing about any of them.**
`CHANGELOG.md` records history. The `README.md` inventory table lists what
ships. `bin/ever-shipped-skills.mjs` is a registry the prune reads, and it keeps
archived names on purpose. Subtract all three before you read a referrer count.

**A path this tree does not hold is not by itself a stale reference.** This
package installs into other repositories, so a rule or skill naming a file that
lives in the host repository is working as intended. Ask whether the specific
script or id it names resolves where it would run, not whether the path exists
here.

## Archive rather than delete

Move the file with `git mv` into the archive sibling: `rules-archived/` beside
`rules/`, `.agents/skills-archived/` beside `.agents/skills/`. The archive is a
sibling and never a child, because the installer copies a content directory
whole.

Archives ship nothing by omission. `CONTENT_DIRECTORIES` in `bin/install.mjs`
names the directories the installer writes, and no archive sibling is on that
list; skills are enumerated from `.agents/skills` alone. So an archived file
leaves every install without any further step, and it comes back with the
reverse `git mv`.

Record a row in the archive manifest for each file: why it went, the `git mv`
that restores it, and every other edit a restore has to undo. A restore that has
to be reconstructed from the diff is not recoverable in any useful sense.

## Make the archive stick

Two things do not follow the file on their own.

**A skill's name stays in `bin/ever-shipped-skills.mjs`.** The prune computes
the retired set as every name ever shipped minus the names installed now, and
that is how a stale copy is moved out of a host's agents home. Delete the name
and the copy is stranded on every machine that has it. The reference checker in
`scripts/active_capability_references.py` derives its retired set the same way,
so the registry entry is also what makes a leftover mention of the archived
name report. No second list needs the name.

**A renamed skill directory takes its tests out of the run.** The node test
command globs `.agents/skills/**/*.test.mjs`, so a suite under an archived skill
stops running without failing. Check that the count you expect still runs.

## Sibling rules

| Rule | Role |
|---|---|
| [`retired-hook-prose.md`](retired-hook-prose.md) | Prose names only hooks that run, and retiring a gate drops the detours it required |
| [`doc-inventory-integrity.md`](doc-inventory-integrity.md) | Inventory tables stay in step with what ships |
