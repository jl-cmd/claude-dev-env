# commands

Slash-command definitions installed into `~/.claude/commands/` by `bin/install.mjs`. Each `.md` file registers a `/command-name` the user can type in Claude Code. The file name (without `.md`) becomes the command name.

## Command files

| File | Command | What it does |
|---|---|---|
| `sr-loop.md` | `/sr-loop` | Runs the converging cleanup loop: /simplify passes until clean, then a code-review fix pass |

## Format

Each file is plain Markdown. The first paragraph is the command's help text shown in the Claude Code UI. The body is the full instruction set Claude follows when the command runs.
