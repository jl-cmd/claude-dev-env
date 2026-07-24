# output-styles

Output-style instruction files installed into `~/.claude/output-styles/` by `bin/install.mjs`. Each file instructs an agent or session to respond in a specific voice or format.

## Files

| File | Style | Effect |
|---|---|---|
| `caveman-agent.md` | Caveman Agent | Terse fragments, lead with answer, smallest artifact that solves the stated problem, question premise before building |
| `plain-brief.md` | Plain Brief | ADHD-friendly plain claims, one idea per sentence, meaning before mechanism; required for AskUserQuestion wording |

## Format

Each file uses YAML frontmatter (`name`, `description`, optional `keep-coding-instructions`) followed by Markdown instructions. The `keep-coding-instructions: true` flag tells Claude Code to keep the session's coding rules even when this style is active.

## Adding a style

Create a `.md` file with frontmatter and behavioral instructions, then run `bin/install.mjs` to copy it to `~/.claude/output-styles/`.
