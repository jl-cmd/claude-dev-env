# Cross-tool projection

The package projects shared rules and hooks into Claude, Codex, and Cursor formats.

## Sub-features

- Claude settings and hook files.
- Codex rules and hook materialization.
- Cursor rule files.

## How to get to it (user POV)

Install the package for Claude. Run the Codex compatibility command for Codex. Open Cursor after the rule projection completes.

## Driving it with Node.js

Run `node packages/claude-dev-env/.agents/skills/run-claude-dev-env/driver.mjs`. Run `python -m pytest packages/claude-dev-env/scripts/tests/test_codex_compat_materializer.py -q` for Codex.

## Gotchas

The installer and the Codex materializer have different owners. Verify both projections after a hook change.
