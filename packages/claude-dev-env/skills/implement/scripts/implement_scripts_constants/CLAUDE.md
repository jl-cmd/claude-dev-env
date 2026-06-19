# implement_scripts_constants

Constants module for the `implement` skill's `append_note.py` script.

## Key files

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `notes_constants.py` | `HEADING_BY_SLUG` dict (section slugs → display headings) and `DEFAULT_NOTES_FILENAME` |

## Exported constants

| Constant | Value | Used by |
|---|---|---|
| `HEADING_BY_SLUG` | `{"decisions": "Design decisions", "deviations": "Deviations", "tradeoffs": "Tradeoffs", "questions": "Open questions"}` | `append_note.py` — maps `--section` slug to the `<h2>` heading in the HTML file |
| `DEFAULT_NOTES_FILENAME` | `"implementation-notes.html"` | `append_note.py` — default output path when `--file` is omitted |

## Conventions

- This module is imported directly by `append_note.py` in the parent `scripts/` directory.
- Adding a new section requires a new entry in `HEADING_BY_SLUG` and a matching branch in `append_note.py`.
