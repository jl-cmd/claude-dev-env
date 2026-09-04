# Installer lifecycle

The command shows help, installs the package into a disposable home, and uninstalls every tracked file.

## Sub-features

- Help without writes.
- Full install with a manifest.
- Clean uninstall.

## How to get to it (user POV)

Run the isolated verification helper. It supplies disposable home and Git configuration roots for install and uninstall.

## Driving it with Node.js

Run `node .cursor/skills/verify-claude-dev-env/scripts/verify-installer.mjs run` from the repository root.

## Gotchas

Use the helper. A direct installer run writes to the live home directory and global Git configuration.
