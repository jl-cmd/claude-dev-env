# commands

Slash-command definitions installed into `~/.claude/commands/` by `bin/install.mjs`. Each `.md` file registers a `/command-name` the user can type in Claude Code. The file name (without `.md`) becomes the command name.

## Command files

| File | Command | What it does |
|---|---|---|
| `commit.md` | `/commit` | Commits and pushes changes to GitHub |
| `doc-gist.md` | `/doc-gist` | Uploads an HTML file as a secret gist and opens the htmlpreview URL |
| `docupdate.md` | `/docupdate` | Updates documentation to match current code state |
| `hook-log-extract.md` | `/hook-log-extract` | Extracts and formats hook log entries for a session |
| `hook-log-init.md` | `/hook-log-init` | Initializes a hook log file for the current session |
| `implement.md` | `/implement` | Implements a feature using the two-phase coder + verifier workflow |
| `initialize.md` | `/initialize` | Bootstraps a new project with standard Claude Code config |
| `plan.md` | `/plan` | Plans a feature through the `anthropic-plan` skill and workflow |
| `pr-comments.md` | `/pr-comments` | Fetches and formats PR review comments for response |
| `review-plan.md` | `/review-plan` | Reviews the current plan packet against code standards |
| `right-size.md` | `/right-size` | Checks an implementation against the Right-Sized Engineering rules |
| `stubcheck.md` | `/stubcheck` | Finds stub bodies (`pass`/`...`/`raise NotImplementedError`) in the diff |
| `sum.md` | `/sum` | Summarizes a file or diff in plain language |

## Format

Each file is plain Markdown. The first paragraph is the command's help text shown in the Claude Code UI. The body is the full instruction set Claude follows when the command runs.
