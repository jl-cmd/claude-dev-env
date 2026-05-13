---
description: Upload an HTML file as a secret gist and open the htmlpreview URL. Manual escape hatch when the auto-publish hook's marker route doesn't apply.
allowed-tools: Bash
---

Argument: `$ARGUMENTS` is the path to an existing `.html` file.

Run the doc-gist skill's transport script directly:

```
python3 "${CLAUDE_PLUGIN_ROOT}/skills/doc-gist/scripts/gist_upload.py" --input "$ARGUMENTS"
```

Quote both URLs (`Gist:` and `Preview:`) from stderr back to the user as clickable markdown links. Surface any `gh gist create failed` error with the suggested `gh auth login` next-step.

When the user asks for a writeup or report rather than handing you a file path, design fresh HTML per [`skills/doc-gist/SKILL.md`](../skills/doc-gist/SKILL.md), include the `<!-- @publish-as-gist -->` marker, and write the file — the auto-publish hook will run on Write. Use this command only when the marker route doesn't fit (existing file you want to publish, HTML from a separate tool).
