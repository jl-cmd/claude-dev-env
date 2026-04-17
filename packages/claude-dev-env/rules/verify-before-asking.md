# Verify Before Asking

**When this applies:** Before asking the user any clarifying question during discovery, scoping, or implementation planning.

## Rule

If a question can be answered by inspecting files, running a command, querying a database, reading a config, or using any available tool, answer it yourself. Only ask the user questions that require their judgment, preference, or knowledge that is not accessible to automated inspection.

## Decision Checklist

Before writing any AskUserQuestion or asking a clarifying question in chat, evaluate:

| Check | Action |
|---|---|
| Does the answer live in a file on disk? | Read the file. |
| Does the answer live in a directory structure? | List the directory. |
| Does the answer live in a database? | Query the database. |
| Does the answer live in git history? | Run `git log` or `git blame`. |
| Is the answer determined by file naming patterns or contents? | Glob a sample and inspect. |
| Is the answer a value in a config or environment variable? | Read the config or check the env. |
| Is the answer retrievable from any available MCP tool? | Use the tool. |

Only after confirming the answer cannot be obtained through any available tool, ask the user.

## Questions That Belong to the User

Reserve user questions for:
- **Preferences** — "Do you want approach A or B?" when both are viable and the user has a stake.
- **Missing context the user holds** — passwords, account names, intent, future plans.
- **Judgment calls** — tradeoffs the user needs to evaluate.
- **Scope decisions** — what to include or exclude from a piece of work.

## Examples

**Wrong:** "Are there multiple images per folder, or just one image + one mp4?"
**Right:** List the folder contents directly, then state what was found.

**Wrong:** "What columns does the themes table have?"
**Right:** Query `information_schema.columns` and report the schema.

**Wrong:** "Is there a Prisma schema in this project?"
**Right:** Glob for `schema.prisma` and check.
