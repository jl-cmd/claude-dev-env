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
| Did the user already state a criterion, standard, or line that decides this? | Apply it, state the call and the reason, and keep going. |

Only after confirming the answer cannot be obtained through any available tool, ask the user.

## Prior-session facts expire

A path, port, branch name, or config value you recall from an earlier session counts as unanswered until a tool re-checks it this session. Memory records what was true when it was written; the file may have moved, the port may be down, the branch may have merged. Treat every recalled fact as a claim to re-ground, not an answer to reuse.

- When a tool can settle it, re-check in silence and act on the fresh result — no question to the user.
- When no tool can settle it and the user has a stake in the answer, ask through `AskUserQuestion`.

## Questions That Belong to the User

Reserve user questions for:
- **Preferences** — "Do you want approach A or B?" when both are viable and the user has a stake.
- **Missing context the user holds** — passwords, account names, intent, future plans.
- **Judgment calls** — tradeoffs the user needs to evaluate.
- **Scope decisions** — what to include or exclude from a piece of work.

A preference question is one where the user has not yet given the line. Once they have, every case under that line is yours to decide. Handing back each application of a stated criterion turns one decision into many and stalls the work, because the person who set the standard does not hold the individual answers. Apply the criterion, name the call and the reason it went that way, and escalate only what the criterion cannot settle: a new axis it never covered, or a step nobody can undo. [`long-horizon-autonomy.md`](long-horizon-autonomy.md) carries the same duty for authority the task already granted.

## Examples

**Wrong:** "Are there multiple images per folder, or just one image + one mp4?"
**Right:** List the folder contents directly, then state what was found.

**Wrong:** "What columns does the themes table have?"
**Right:** Query `information_schema.columns` and report the schema.

**Wrong:** "Is there a Prisma schema in this project?"
**Right:** Glob for `schema.prisma` and check.
