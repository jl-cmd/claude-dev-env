# system-prompts

System prompt files installed into `~/.claude/system-prompts/` by `bin/install.mjs`. Claude Code loads these as the base persona and behavioral protocol for a session.

## Files

| File | Purpose |
|---|---|
| `software-engineer.xml` | Primary system prompt: defines the software engineering role, task-scope rules, output style, and the BDD `<behavior_protocol>` that rules in `rules/bdd.md` reference |

## Format

Files use XML with named sections (`<role>`, `<task_scope>`, `<output_style>`, `<behavior_protocol>`, etc.). Claude Code injects the full file into the system prompt slot at session start.

## Adding a prompt

Create a new `.xml` file and run `bin/install.mjs` to copy it to `~/.claude/system-prompts/`. Reference the new file in the relevant rule or skill by its installed path.
