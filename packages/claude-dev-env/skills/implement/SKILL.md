---
name: implement
description: "Implement a spec while maintaining a running implementation-notes.html file that captures design decisions, deviations, tradeoffs, and open questions. Triggers: /implement, implement this spec, build out this plan and keep notes."
argument-hint: "[path to spec file, or omit to use a spec already in context]"
---

# implement

Execute a spec end-to-end while keeping a sidecar `implementation-notes.html` that the user can read to see how the build diverged from or interpreted the written plan.

## Instructions

Carry out the following prompt against the spec resolved below.

### Resolve `<SPEC>`

- If `$ARGUMENTS` is non-empty, treat it as the path to the spec file and read it.
- Otherwise, use the most recent plan / spec / design doc already present in the conversation context.
- If neither is available, ask the user for the spec path via `AskUserQuestion` before proceeding.

### Prompt to execute

> Implement `<SPEC>`. As you work maintain a running `implementation-notes.html` file that captures anything I should know about how the implementation diverges from or interprets the spec, including:
>
> - **Design decisions:** choices you made where the spec was ambiguous
> - **Deviations:** places where you intentionally departed from the spec, and why
> - **Tradeoffs:** alternatives you considered and why you picked what you did
> - **Open questions:** anything you'd want me to confirm or revise

### How to write notes

Run `${CLAUDE_SKILL_DIR}/scripts/append_note.py` to append each entry. The script creates `implementation-notes.html` with the four sections on first run, then inserts a new `<li>` under the requested section. HTML-escapes `--about` and `--note` automatically. `${CLAUDE_SKILL_DIR}` is host-substituted by Claude Code at runtime so the bundled CLI is found regardless of the current working directory.

```
python "${CLAUDE_SKILL_DIR}/scripts/append_note.py" \
  --section decisions \
  --about "Storage location" \
  --note "Wrote notes next to the spec because the spec path was provided." \
  --file /path/to/spec-dir/implementation-notes.html
```

`--section` choices (slug → heading):

| Slug | Heading |
|---|---|
| `decisions` | Design decisions |
| `deviations` | Deviations |
| `tradeoffs` | Tradeoffs |
| `questions` | Open questions |

`--file` is optional. When omitted, the script writes to `./implementation-notes.html` in the current working directory. When a spec path is known, pass `--file` so notes land next to the spec rather than in CWD.

Append entries as decisions are made — do not batch them until the end.

## Gotchas

- **Do not hand-edit `implementation-notes.html`.** The append script locates each section by its `<section id="...">` marker and the first `</ul>` after it. Editing the structure breaks subsequent appends; the script raises a `RuntimeError` naming the missing marker.
- **`--about` and `--note` are HTML-escaped automatically** — pass raw text, not pre-escaped HTML.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | This hub |
| `scripts/append_note.py` | CLI to append one entry to a section |
| `scripts/config/notes_constants.py` | Section slugs → headings and default filename |
