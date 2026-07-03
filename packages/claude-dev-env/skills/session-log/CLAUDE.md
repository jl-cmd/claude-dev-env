# session-log

Logs a session report as a self-contained HTML page in the Obsidian vault, publishes it with the `Artifact` tool, extracts unrecorded decisions, tidies the project session folder, and outputs a `/rename` command.

**Trigger:** `/session-log`, "journal this session", "log this work", "session report", "save session", "capture session", "document what we did".

## Purpose

Produces a self-contained HTML session report shaped to the session's character (feature build, incident, research, etc.) rather than a fixed template. The skill owns the vault path, session numbering, frontmatter contract, HTML composition and publishing, decision extraction, and folder hygiene.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Hub — six steps, gotchas, backend detection, frontmatter contract, run-and-report checklist. Single-file skill; no companion files. |

## Six steps

1. **Backend detection** — headless vault (`ob --version` + `OBSIDIAN_VAULT_PATH`) then local vault (`~/.claude/vault/`). Session number from `[N]. *.html` and `[N]. *.md` files in the project folder.
2. **Session metadata** — project name, session number, session ID from `CLAUDE_CODE_SESSION_ID`, date, title.
3. **Compose and publish via the Artifact tool** — loads the `artifact-design` skill first, designs the shape for the session's character (e.g., a PR-writeup shape for feature builds, a timeline shape for incidents), writes the HTML, then publishes it with the `Artifact` tool using the fixed favicon `📓`.
4. **Vault context tracking** — two Edit calls set `vault_context_retrieved` and append a vault-context line, then redeploy via `Artifact` on the same `file_path` so the URL stays the same.
5. **Decision extraction** — scans conversation for unrecorded decisions; prompts user via `AskUserQuestion` before invoking `/remember`.
6. **Session tidy** — audits `.html` files in the project folder for naming and frontmatter; auto-fixes minor issues and redeploys via `Artifact`.

## Conventions

- Session reports use HTML — the Artifact tool publishes HTML or Markdown, and HTML gives the report designer more visual structure.
- `write_existing_file_blocker` rejects Write on existing paths — use Edit for all vault-context updates.
- The `Artifact` tool redeploys to the same URL on repeat calls with the same `file_path` within the current run — edits made in steps 3 and 5 to the session created this run never mint a new URL.
- Final step copies `/rename [Project] - [Primary Outcome]` to the clipboard via `pwsh Set-Clipboard`.
