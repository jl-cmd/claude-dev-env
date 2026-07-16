# system-prompts

System-prompt reference files installed into `~/.claude/system-prompts/` by `bin/install.mjs`. Rules and skills pull a file (or one of its sections) into context on demand by citing its installed path.

## Files

| File | Purpose |
|---|---|
| `software-engineer.xml` | Software-engineering reference: defines the engineering role, task-scope rules, output style, and the BDD `<behavior_protocol>` that `rules/bdd.md` cites on demand |

## Format

Files use XML with named sections (`<role>`, `<task_scope>`, `<output_style>`, `<behavior_protocol>`, etc.). A rule or skill cites a file, or one of its sections, to pull it into context when the task needs it.

## Adding a prompt

Create a new `.xml` file and run `bin/install.mjs` to copy it to `~/.claude/system-prompts/`. Reference the new file in the relevant rule or skill by its installed path.
