---
name: doc-gist
description: >-
  Use when the user asks to share, publish, preview, or open as a webpage any
  HTML doc, writeup, report, plan, decision record, runbook, explainer, status
  update, or interactive artifact. Triggers on `/doc-gist`, "publish this",
  "share as a gist", "open this as a webpage", "make me a writeup", "publish my
  report", or any request that ends in a shareable HTML preview URL. Provides
  the `gist_upload` transport script, an auto-publish hook keyed off the
  `<!-- @publish-as-gist -->` HTML comment, and a 20-file gallery of HTML
  artifact patterns to draw from when designing fresh.
---

# doc-gist

Design fresh HTML for the artifact at hand, mark it for publishing, write it. The rest is automatic — a hook spots the marker, uploads to a secret gist, and prints the htmlpreview URL into your output for the user to click.

## Principle (and what this skill deliberately does not ship)

This skill ships **transport, not shape**. There are no document templates here. There is no markdown-to-HTML converter. There is no rebase-report mode. The shape of every artifact is your fresh design per request, drawing on the gallery in [`references/examples/`](references/examples/) for inspiration.

Per Thariq's html-effectiveness thesis: *"twenty self-contained .html files an agent produced — each one trades a document you'd skim for one you'd actually read."* Every doc-gist invocation produces a fresh design appropriate to the work, not a template fill.

## How auto-publish works

1. You write HTML to any path (no directory rule, no naming rule).
2. The HTML contains the marker comment `<!-- @publish-as-gist -->` — typically as the first child of `<head>` or just inside `<body>`.
3. The PostToolUse hook ([`workflow/doc_gist_auto_publish.py`](../../hooks/workflow/doc_gist_auto_publish.py)) fires after the Write/Edit completes, sees the marker, and runs [`skills/doc-gist/scripts/gist_upload.py`](scripts/gist_upload.py) against the file.
4. The upload script's gist + preview URLs print into your tool output. Quote them back to the user.

The hook is a no-op for any HTML that lacks the marker — React components, test fixtures, scraped pages, partial fragments. The marker is the *intent signal*; absent marker means "this HTML isn't for sharing."

## Gotchas

- **`gh` must be authenticated.** The upload runs `gh gist create`. If `gh auth status` is failing, the hook surfaces the error to stderr and exits 0 (does not block the write). Run `gh auth login` and re-trigger by editing the HTML once more.
- **The marker is a literal HTML comment, not a meta tag.** `<!-- @publish-as-gist -->` exactly. `<meta name="publish-as-gist">` does not match. Whitespace inside the marker breaks it.
- **htmlpreview render delay.** First load of the preview URL takes 5–10 seconds while htmlpreview.github.io fetches the raw gist content. A blank page on first visit means refresh once.
- **Filenames carry into the gist.** The gist filename is the same as the source file's name. Name your files for the artifact, not for filesystem convenience — `auth-migration-plan.html` reads better in the gist UI than `tmp_plan_v3_final.html`.
- **Markers in code samples need escaping.** If you embed an example HTML snippet inside `<pre><code>` and that snippet contains the literal marker text, the hook will publish on first save. Either escape the comment angle brackets in the embedded sample, or write the marker as `<!- - @publish-as-gist - ->` in the embedded version.
- **Self-contained HTML only.** The upload sends a single file. External CSS/JS via `<link href="./style.css">` or `<script src="./app.js">` will fail to load in the htmlpreview view. Inline everything — `<style>`, `<script>`, base64 images, SVG.
- **Secret gist, not private.** `gh gist create` defaults to "secret" (anyone with the URL can view; not indexed; not on your public profile). Treat the preview URL like a shareable Google Doc — share with intent.

## When to include the marker

Include `<!-- @publish-as-gist -->` when **the artifact is for sharing or reading**: writeups, plans, reports, explainers, decision records, runbooks, status updates, prototypes the user will look at. Skip the marker for: HTML that's part of a code change (React components, test fixtures), HTML you're authoring as a one-off scratch file you'll delete, embedded HTML samples inside other artifacts.

The user's prompt is the strongest signal. *"Make me a writeup of this PR"* → publish. *"Add this React component"* → don't publish.

## The transport script — `skills/doc-gist/scripts/gist_upload.py`

For manual invocation when the marker route doesn't apply (an existing file you want to publish, HTML piped from another tool, a one-off):

```
python3 skills/doc-gist/scripts/gist_upload.py --input <path-or-stdin>
                              [--filename gist-file.html]
                              [--description "short label"]
                              [--no-open]
```

Reads HTML from `--input <path>` or stdin (`--input -`), runs `gh gist create`, prints `Gist:` and `Preview:` URLs to stderr, prints the preview URL to stdout (so callers can pipe), opens the preview in the default browser unless `--no-open`.

## Designing fresh — the example gallery

The skill ships [`references/examples/`](references/examples/) with all 20 of Thariq's html-effectiveness prototypes verbatim from [thariqs.github.io/html-effectiveness](https://thariqs.github.io/html-effectiveness/). They are *examples to learn from, not templates to fill.*

When the user requests an artifact, decide the shape that fits. Use the gallery for grounding:

| User wants | Gallery entries to study |
|---|---|
| PR writeup with file-by-file tour | `17-pr-writeup.html` |
| Annotated diff or code review | `03-code-review-pr.html` |
| Code-explainer with module map | `04-code-understanding.html` |
| Implementation plan with timeline + risks | `16-implementation-plan.html` |
| Side-by-side approach exploration | `01-exploration-code-approaches.html` |
| Visual design comparison | `02-exploration-visual-designs.html` |
| Design system swatches | `05-design-system.html` |
| Component variants matrix | `06-component-variants.html` |
| Animation tuning sandbox with sliders | `07-prototype-animation.html` |
| Multi-screen interaction mockup | `08-prototype-interaction.html` |
| Slide deck (keyboard-navigable) | `09-slide-deck.html` |
| SVG illustration | `10-svg-illustrations.html` |
| Status report (visual) | `11-status-report.html` |
| Incident timeline / post-mortem | `12-incident-report.html` |
| Flowchart / pipeline diagram | `13-flowchart-diagram.html` |
| Feature explainer with collapsibles | `14-research-feature-explainer.html` |
| Concept explainer (interactive learning) | `15-research-concept-explainer.html` |
| Triage / kanban board (drag-drop) | `18-editor-triage-board.html` |
| Feature flag toggles with deps | `19-editor-feature-flags.html` |
| Live-updating template editor | `20-editor-prompt-tuner.html` |

Read the matching example for the artifact you're designing. Crib palette, typography, spatial idioms, component patterns. **Adapt — do not copy.** A PR writeup for a hooks PR shouldn't look identical to one for a notification-queue PR. The gallery teaches what shapes work; the request decides which shape fits.

## Folder map

- `SKILL.md` — this file.
- `skills/doc-gist/scripts/gist_upload.py` — transport: HTML in, gist + preview URLs out.
- `skills/doc-gist/scripts/doc_gist_scripts_constants/gist_upload_constants.py` — the URL prefixes and template strings.
- `references/examples/` — Thariq's 20 html-effectiveness prototypes.
- (PostToolUse hook lives in `packages/claude-dev-env/hooks/workflow/doc_gist_auto_publish.py` — wired into the plugin's `hooks.json`.)
