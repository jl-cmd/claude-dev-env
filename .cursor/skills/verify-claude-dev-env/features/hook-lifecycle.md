# Hook lifecycle

The package registers bounded lifecycle automation and moves policy checks into explicit linters and continuous integration.

## Sub-features

- Session, tool, stop, and session-end events.
- Policy-linter timing.
- Claude, Codex, and native Git readback.

## How to get to it (user POV)

Install into a disposable profile. Exercise one edit, one staged lint, and the package audit.

## Driving it with Node.js

Run the installer helper. Then run `node packages/claude-dev-env/scripts/audit-hooks-cli.mjs --format text` and the focused hook tests.

## Gotchas

No hook can return `deny`, `block`, or `ask` in the target state. Linters can fail only their own command.
