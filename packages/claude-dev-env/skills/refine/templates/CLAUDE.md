# refine/templates

Output structure templates for the `/refine` skill.

## Key files

| File | Purpose |
|---|---|
| `plan-template.md` | Required plan structure: YAML frontmatter (project, date, status, tags), H1 title, and sections (Goal, Non-goals, Current state, Implementation, Decisions log, Risks, Open questions, Acceptance). The `/refine` skill loads this on Step 6 and fills every placeholder before writing to the vault. |
| `implementation-notes-template.html` | Skeleton HTML file the fix agent copies on iteration 1 of the audit-fix loop, then appends to on each later iteration. Each iteration adds one `<section class="iteration">` block before `</body>`. The template has an HTML-commented reference block showing the section markup shape. |

## Conventions

- `plan-template.md` is for `mcp__obsidian__write_note` (Markdown only); the skill writes it to the vault directly.
- `implementation-notes-template.html` is for filesystem Write/Edit tools; `mcp__obsidian__write_note` cannot write `.html`.
- Both files have `{{slug}}` and other placeholder tokens that the skill substitutes before writing.
- Do not write to these templates directly — they are read-only reference structures consumed by the `/refine` workflow.
