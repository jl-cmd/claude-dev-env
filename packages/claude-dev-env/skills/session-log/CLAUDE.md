# session-log

Logs a session report as a gallery-shaped HTML file in the Obsidian vault, auto-publishes it as a secret gist, extracts unrecorded decisions, tidies the project session folder, and outputs a `/rename` command.

**Trigger:** `/session-log`, "journal this session", "log this work", "session report", "save session", "capture session", "document what we did".

## Purpose

Produces a self-contained HTML session report shaped to the session's character (feature build, incident, research, etc.) rather than a fixed template. The skill owns the vault path, session numbering, frontmatter contract, decision extraction, and folder hygiene; it delegates HTML authorship to `doc-gist`.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Hub — six steps, gotchas, backend detection, frontmatter contract, run-and-report checklist. Single-file skill; no companion files. |

## Six steps

1. **Backend detection** — headless vault (`ob --version` + `OBSIDIAN_VAULT_PATH`) then local vault (`~/.claude/vault/`). Session number from `[N]. *.html` and `[N]. *.md` files in the project folder.
2. **Session metadata** — project name, session number, session ID from `CLAUDE_CODE_SESSION_ID`, date, title.
3. **HTML via doc-gist shape principles** — gallery-anchored design (e.g., `17-pr-writeup.html` for feature builds, `12-incident-report.html` for incidents). `<!-- @publish-as-gist -->` marker triggers auto-publish hook on Write/Edit.
4. **Vault context tracking** — two Edit calls set `vault_context_retrieved` and append a vault-context line. The URL from the final Edit is canonical.
5. **Decision extraction** — scans conversation for unrecorded decisions; prompts user via `AskUserQuestion` before invoking `/remember`.
6. **Session tidy** — audits `.html` files in the project folder for naming and frontmatter; auto-fixes minor issues.

## Conventions

- The `<!-- @publish-as-gist -->` marker must appear exactly as shown; each Edit re-fires the hook and produces a new gist ID.
- Session reports use HTML; `.md` paths are blocked by `md_to_html_blocker` for session paths.
- `write_existing_file_blocker` rejects Write on existing paths — use Edit for all vault-context updates.
- Final step copies `/rename [Project] - [Primary Outcome]` to the clipboard via `pwsh Set-Clipboard`.
