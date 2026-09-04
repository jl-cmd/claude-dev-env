---
name: verify-claude-dev-env
description: Verifies the claude-dev-env command-line installer in a disposable environment and maps focused checks for configuration projections, hooks, policy lint, and continuous integration.
---

# Verify claude-dev-env

Drive the package through disposable home and Git configuration roots. Never use the live install commands for verification.

## Launch

Run the short-lived installer proof from the repository root:

```powershell
node .cursor/skills/verify-claude-dev-env/scripts/verify-installer.mjs run
```

The run is ready when the transcript reports `21/21 checks passed` and `ALL CHECKS PASSED`. The driver removes its sandbox before the helper exits.

## Doctor

Run the read-only environment check first:

```powershell
node .cursor/skills/verify-claude-dev-env/scripts/verify-installer.mjs doctor
```

Continue only when the command prints `Doctor command: ready`.

## Drive

Use the helper for the real installer lifecycle. The `run` command proves the installer only. It calls `packages/claude-dev-env/.agents/skills/run-claude-dev-env/driver.mjs`.

For other changes, use the matching file in [features](features/README.md). Exercise each changed feature before final verification. A later conversion unit adds the policy-lint and hook-lifecycle commands after those commands exist.

Do not run `node packages/claude-dev-env/bin/install.mjs` without an isolated home. That command writes to the user configuration directories.

## Evidence

Keep proof under `.audit/hook-linter-conversion/evidence/`.

- `installer-doctor.json` records tool availability.
- `installer-transcript.json` records the command, exit status, actions, and results.
- Final screenshots show the report and command results.
- The final video records the report and successful verification path.

The proof must show the action and the result. Inspect installed settings, Codex hooks, Git configuration, and manifests when a change affects them.

## Cleanup

The installer driver removes only the temporary directory that it creates. It does not kill processes by name.

After each run, confirm that the transcript contains `Sandbox removed`. Keep the evidence files.

## Helpers

Run these helpers:

```powershell
node .cursor/skills/verify-claude-dev-env/scripts/verify-installer.mjs doctor
node .cursor/skills/verify-claude-dev-env/scripts/verify-installer.mjs run
node --test .cursor/skills/verify-claude-dev-env/scripts/verify-installer.test.mjs
```
