# Scoped installation

The installer can select groups, profiles, or one explicit destination.

## Sub-features

- `--only` group selection.
- Named profiles.
- An explicit `--target` directory.

## How to get to it (user POV)

Use `--only core`, `--profile <name>`, `--profiles <names>`, or `--target <path>` with the installer.

## Driving it with Node.js

Run `node --test packages/claude-dev-env/bin/install.test.mjs` and select scoped-install tests with `--test-name-pattern` when needed.

## Gotchas

Every destination must remain inside a disposable test root. Named profiles can publish several configuration trees.
