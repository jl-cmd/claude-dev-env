# Build Needs a User

**When this applies:** Before you build a new tool, script, hook, gate, skill,
command, or workflow step. That includes a hook or check built to answer a
correction.

## Rule

Answer three questions before the first line of the build:

1. **Who calls it?** Name the hook entry, workflow step, skill, command, or
   module that will run it in this same change.
2. **When does it first run?** Name the date or the event of first use.
3. **When was this job last done by hand?** Name the last time, and how often it
   comes up.

Build when all three have a concrete answer. When the only answer is "it might
help" or "we could use it later", stop and send the owner one line: what the
build is for and which question has no answer. Keep the rest of the task moving
while that line waits.

Search first, per [`prefer-existing-tools.md`](prefer-existing-tools.md). A
tool that already exists answers the need, and the build is the glue.

## Size the first build to the first use

Build the smallest version that serves the first caller. A correction starts
as a row in a rule file. It becomes a hook or a lint only when the same
correction arrives a second time, per
[`correction-lens.md`](correction-lens.md).

## Where it is enforced

The staged policy lint's `uncalled-new-file` rule reads each code file a change
adds under `scripts/`, `hooks/`, or `bin/`. It reports the file when its name
appears only in its own tests, `CHANGELOG.md`, `README.md`, and
`bin/ever-shipped-skills.mjs`. CI runs that lint against the merge base, so a
file with no caller turns the pull request red.

## Why

The history of this package holds files that lived weeks and ran never. The
Codex compatibility watcher shipped 502 lines and 599 lines of tests in July,
and PR 1488 deleted it in September. Its own test was the only file that named
it.

## Sibling rules

| Rule | Role |
|---|---|
| [`prefer-existing-tools.md`](prefer-existing-tools.md) | Search before you build |
| [`correction-lens.md`](correction-lens.md) | A repeated correction moves up a layer |
| [`archiving-agent-config.md`](archiving-agent-config.md) | How an unused capability leaves service |
