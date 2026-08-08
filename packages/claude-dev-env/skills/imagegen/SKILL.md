---
name: imagegen
description: Generate prompt-driven images at exact requested resolutions through OpenAI API or Codex OAuth, with verified Pillow dimensions, truthful receipts, and safe atomic publication.
argument-hint: --backend openai-api|codex-oauth --prompt "..." --size 2880x2880 --output path.png [--reference-image path.png]... [--model name] [--reasoning-effort level]
---

# Exact-resolution image generation

Use `scripts/imagegen.py` for reusable image generation.

Prerequisites: Python 3.11 or newer and Pillow. The direct backend requires `OPENAI_API_KEY`; the OAuth backend requires an authenticated `codex` installation.

```text
python scripts/imagegen.py --backend openai-api --prompt "..." --size 2880x2880 --output generated.png
```

`openai-api` reads `OPENAI_API_KEY` from the environment and requests `gpt-image-2`. `codex-oauth` invokes the authenticated `codex` executable in an isolated temporary directory and measures its single PNG artifact.

Native provider dimensions publish unchanged source bytes. A mismatch fails with the default `--resize-policy forbid`; `--resize-policy allow` applies Pillow resizing and records `resized` in the JSON sidecar receipt.

Up to two `--reference-image path.png` flags attach reference images. Each is validated (exists, decodes with Pillow) before any backend spawns; a third reference fails loudly before either backend runs. `codex-oauth` attaches references with the Codex CLI's own `-i`/`--image` flag. `openai-api` sends them through the OpenAI image-edit endpoint.

`--model name` passes through to both backends. `--reasoning-effort level` passes through to `codex-oauth` only (as a `model_reasoning_effort` config override); `openai-api` has no reasoning-effort control and fails loudly if the flag is given.

The receipt sits beside the PNG with a `.json` suffix. It contains hashes, observed dimensions, backend, model or tool, transformation classification, prompt hash, credential source name, the reference image paths and their sha256 hashes, and the requested model and reasoning effort (`null` when not given). Existing output or receipt files require `--overwrite`.
