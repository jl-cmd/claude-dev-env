# Hook lifecycle

The package registers session, tool, stop, and session-end hooks. Policy checks run as linters and continuous-integration jobs.

## Sub-features

- Session, tool, stop, and session-end events.
- Policy-linter timing.
- Claude, Codex, and native Git configuration.

## How to get to it (user POV)

Install into a disposable profile. Exercise one edit, one staged lint, and the package audit.

## Driving it with Node.js

Run the installer helper. Then run `python tests/audit/hooks/run_hook_audit.py` and the hook tests.

## Gotchas

Hooks must not return `deny`, `block`, or `ask`. A linter may fail only its own command.
