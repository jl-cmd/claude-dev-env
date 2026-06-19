# doc-gist

Designs fresh HTML artifacts and publishes them as secret GitHub gists with a shareable htmlpreview URL. Triggered by `/doc-gist`, `publish this`, `share as a gist`, `open this as a webpage`, `make me a writeup`, or any request ending in a shareable HTML preview URL.

## Purpose

The skill ships transport, not templates. For each request the model designs a fresh HTML artifact suited to the work, marks it with `<!-- @publish-as-gist -->`, and writes it to disk. A PostToolUse hook (`hooks/workflow/doc_gist_auto_publish.py`) spots the marker, runs `packages/claude-dev-env/skills/doc-gist/scripts/gist_upload.py`, and prints the gist and htmlpreview URLs into the tool output for the user to click.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Full instructions: the auto-publish hook flow, the transport script CLI, a gallery-to-artifact-type mapping table, and gotchas (`gh` auth, marker syntax, self-contained HTML only, secret-not-private note). |

## Subdirectories

| Directory | Role |
|---|---|
| `references/` | Reference material — the example HTML gallery and related docs. |
| `scripts/` | The `gist_upload.py` transport script and its constants package. |

## Auto-publish vs manual

- **Auto:** write HTML with `<!-- @publish-as-gist -->` anywhere in the file; the hook handles the rest.
- **Manual:** run `python scripts/gist_upload.py --input <path>` for an existing file or when the marker route does not apply.
