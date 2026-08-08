---
name: imagegen
description: Generate prompt-driven images at exact requested resolutions through OpenAI API or Codex OAuth, with verified Pillow dimensions, truthful receipts, and safe atomic publication.
argument-hint: --backend openai-api|codex-oauth --prompt "..." --size 2880x2880 --output path.png
---

# Exact-resolution image generation

Use `scripts/imagegen.py` for reusable image generation.

Prerequisites: Python 3.11 or newer and Pillow. The direct backend requires `OPENAI_API_KEY`; the OAuth backend requires an authenticated `codex` installation.

```text
python scripts/imagegen.py --backend openai-api --prompt "..." --size 2880x2880 --output generated.png
```

`openai-api` reads `OPENAI_API_KEY` from the environment and requests `gpt-image-2`. `codex-oauth` invokes the authenticated `codex` executable in an isolated temporary directory and measures its single PNG artifact.

Native provider dimensions publish unchanged source bytes. A mismatch fails with the default `--resize-policy forbid`; `--resize-policy allow` applies Pillow resizing and records `resized` in the JSON sidecar receipt.

The receipt sits beside the PNG with a `.json` suffix. It contains hashes, observed dimensions, backend, model or tool, transformation classification, prompt hash, and credential source name. Existing output or receipt files require `--overwrite`.
