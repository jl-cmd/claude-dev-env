---
name: verify-claude-dev-env
description: Verifies the claude-dev-env command-line installer in a disposable home. Maps checks for configuration projections, hooks, policy lint, and continuous integration.
---

# Verify claude-dev-env

Run the installer with disposable home and Git configuration roots. Never use the live install commands for verification.

## Launch

Run this command from the repository root:

```powershell
node .cursor/skills/verify-claude-dev-env/scripts/verify-installer.mjs run
```

The command succeeds when the transcript reports `21/21 checks passed` and `ALL CHECKS PASSED`. The driver removes its sandbox before the helper exits.

## Doctor

Run the read-only environment check first:

```powershell
node .cursor/skills/verify-claude-dev-env/scripts/verify-installer.mjs doctor
```

Continue only when the command prints `Doctor command: ready`.

## Drive

`run` covers the installer lifecycle only. It calls `.cursor/skills/verify-claude-dev-env/scripts/driver.mjs`, the harness this skill owns.

For other changes, use the matching file in [features](features/README.md). Exercise each changed feature before you verify.

## Policy linter

Run `cde lint` through Node.js:

```powershell
node packages/claude-dev-env/bin/cde.mjs lint --files <path>
node packages/claude-dev-env/bin/cde.mjs lint --staged
node packages/claude-dev-env/bin/cde.mjs lint --base origin/main
node packages/claude-dev-env/bin/cde.mjs lint --repository
Get-Content -Raw .\src\file.py | node packages/claude-dev-env/bin/cde.mjs lint --text-as .\src\file.py
```

Use `--format text`, `--format json`, or `--format editor`. Relative `--files` and `--text-as` paths resolve from the caller directory, including a caller directory below the repository root. Use `--python <command>` to pick the Python interpreter.

Exit 0 is clean. Exit 1 reports diagnostics. Exit 2 reports invalid input or a launcher start failure. Exit 3 reports an incomplete rule run.

Do not run `node packages/claude-dev-env/bin/install.mjs` without an isolated home. That command writes to the user configuration directories.

## Evidence

Store evidence in `.audit/hook-linter-conversion/evidence/`.

- `installer-doctor.json` records tool availability.
- `installer-transcript.json` records the command, exit status, actions, and results.

The transcript must show each installer step and its result. Inspect installed settings, Codex hooks, Git configuration, and manifests when a change affects them.

## Cleanup

The installer driver removes only the temporary directory that it creates. It does not kill processes by name.

After each run, confirm that the transcript contains `Sandbox removed`. Keep the evidence files.

## Helpers

Run these helpers:

```powershell
node .cursor/skills/verify-claude-dev-env/scripts/verify-installer.mjs doctor
node .cursor/skills/verify-claude-dev-env/scripts/verify-installer.mjs run
node --test .cursor/skills/verify-claude-dev-env/scripts/verify-installer.test.mjs
python -m pytest packages/claude-dev-env/scripts/tests/test_policy_lint_selection.py packages/claude-dev-env/scripts/tests/test_policy_lint_rules_engine.py packages/claude-dev-env/scripts/tests/test_policy_lint_rules_registry.py packages/claude-dev-env/scripts/tests/test_cde_lint.py -q
node --test packages/claude-dev-env/bin/cde.test.mjs
```
