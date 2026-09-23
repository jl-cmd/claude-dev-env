# Installer lifecycle

The installer shows help, installs the package into a home directory, writes the Claude and Codex hook files, and uninstalls every tracked file. A scratch home stands in for the live home in every verification run.

## Sub-features

- `install-help` prints usage and writes nothing.
- `install-full` writes skills, hooks, rules, `CLAUDE.md`, a manifest, and a `settings.json` hook roster.
- `install-codex-hooks` writes `~/.codex/hooks.json` with two `PreToolUse` groups: `multi_agent_v1__spawn_agent` for model routing and `Agent|Task` for the poteto-mode spawn rewrite.
- `install-retired-prune` removes retired hook registrations on reinstall.
- `install-playtest` installs, then starts installed hooks from the roster the install wrote.
- `install-uninstall` removes the manifest and every tracked file.

## How to get to it (user POV)

- Run `node packages/claude-dev-env/bin/install.mjs --help`.
- Run `node packages/claude-dev-env/bin/install.mjs`, then open a Claude Code or Codex session.
- Run `node packages/claude-dev-env/bin/install.mjs --uninstall`.

## Driving it with Node.js

Preconditions:

- `node` and `python3` are on `PATH`.
- Every run sets `HOME`, `USERPROFILE`, and `GIT_CONFIG_GLOBAL` to a scratch home. The helpers below do this.

- **Help, install, uninstall.** Run `node .cursor/skills/verify-claude-dev-env/scripts/verify-installer.mjs run` from the repository root. The transcript reports `21/21 checks passed`, `ALL CHECKS PASSED`, and `Sandbox removed`.
- **Playtest.** Run `node packages/claude-dev-env/scripts/ci/install-playtest.mjs --home <scratch> --evidence <scratch>-evidence`. Exit code `0` and three `[PASS] playtest` lines for `install`, `session_start_hook`, and `blocking_hook`.
- **Codex hooks file.** Open `<scratch>/.codex/hooks.json`. `hooks.PreToolUse` holds exactly the `Agent|Task` and `multi_agent_v1__spawn_agent` groups, and their commands point into `<scratch>/.codex/hooks/`.
- **Broken install.** Overwrite `<scratch>/.claude/hooks/session/working_style_prompt.py` with `print("")`, then run the playtest again with `--home <scratch> --skip-install`. Exit code `1` and the line `[FAIL] playtest session_start_hook The hook wrote no SessionStart envelope`.
- **Red direction.** Run `node --test packages/claude-dev-env/scripts/ci/install-playtest.test.mjs`. It passes when the driver exits `0` on a fresh install and `1` after it writes a script that prints an empty line over the installed `working_style_prompt.py`.
- **Proof.** Keep `tests/audit/data/hook-linter-conversion/evidence/installer-transcript.json` and `<scratch>-evidence`. Remove `<scratch>` after the run.

## Gotchas

- Use a helper. A direct installer run writes to the live home directory and global Git configuration.
- `scripts/ci/scratch-home-install.mjs` owns the scratch home. The playtest and `scripts/ci/installer-lifecycle.mjs` both import it.
- The `install-playtest` CI job runs on Ubuntu. The `windows-installer-lifecycle` job runs the lifecycle on Windows.
