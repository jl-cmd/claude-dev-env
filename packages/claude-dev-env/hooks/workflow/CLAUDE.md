# hooks/workflow

PostToolUse hooks that trigger side-effects after Claude writes a file. They do not block writes; they produce companion artifacts or publish content automatically.

## Key files

| File | Event | What it does |
|---|---|---|
| `auto_formatter.py` | PostToolUse (Write/Edit) | Runs the project's auto-formatter (ruff, prettier, etc.) on the written file and sends a desktop notification when formatting changes are applied |
| `doc_gist_auto_publish.py` | PostToolUse (Write on `.html` files) | When an `.html` file has the `<!-- @publish-as-gist -->` marker, uploads it as a secret GitHub Gist and prints the htmlpreview URL into the harness output |
| `md_to_html_companion.py` | PostToolUse (Write/Edit on `.md` files) | Generates a styled `.html` companion file from the `.md` source with dark-mode styling |
| `investigation_tracker_reset.py` | PostToolUse | Resets the investigation tracker state after a tool call |
| `test_auto_formatter.py` | — | Tests for `auto_formatter.py` |
| `test_doc_gist_auto_publish.py` | — | Tests for `doc_gist_auto_publish.py` |
| `test_md_to_html_companion.py` | — | Tests for `md_to_html_companion.py` |

## Conventions

- All three main hooks exit 0 even on failure — they log warnings to stderr but do not break Claude's flow.
- `doc_gist_auto_publish.py` checks for the `<!-- @publish-as-gist -->` marker before doing any work; HTML files without it are ignored.
- Constants (marker text, blocked URL schemes, gist upload script path) live in `hooks_constants/doc_gist_auto_publish_constants.py` and `hooks_constants/html_companion_constants.py`.
- Tests run with `python -m pytest workflow/test_<name>.py`.
