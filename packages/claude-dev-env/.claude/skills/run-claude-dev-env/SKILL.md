---
name: run-claude-dev-env
description: Build, install, run, and test the claude-dev-env installer. Use when asked to run claude-dev-env, install the Claude Code config into ~/.claude, drive the installer, smoke-test it against a sandbox, or run its test suite.
---

`claude-dev-env` is the npm-distributed installer that copies this repo's rules, hooks, agents, commands, docs, and skills into `~/.claude/` and merges its hook entries into `~/.claude/settings.json`. Its entry point is `bin/install.mjs`. Drive it with the smoke driver at `.claude/skills/run-claude-dev-env/driver.mjs`, which runs the installer against a throwaway sandbox home directory so a run never touches the real `~/.claude/`.

All paths below are written from the `packages/claude-dev-env/` directory.

## Prerequisites

The installer needs three tools on `PATH`:

- **Node.js 18+** — the installer is an ES module (verified on Node 22.17).
- **Python 3.8+** — the installer bakes a Python interpreter into every hook command and aborts if it finds none. On Windows it skips the Microsoft Store stub (verified `py -3` → Python 3.13.5).
- **git** — the installer reads `git status` to guard against installing from a conflicted source, and sets a global git hooks path.

```bash
node --version
git --version
py -3 --version    # POSIX: python3 --version
```

On a fresh Ubuntu container the three come from `sudo apt-get install -y nodejs python3 git`.

## Run (agent path) — the smoke driver

The driver is the handle to reach for first. It spawns the installer against a fresh temp home directory with `HOME`, `USERPROFILE`, and `GIT_CONFIG_GLOBAL` all redirected, runs the `--help` → install → `--uninstall` lifecycle, asserts the result of each step against the sandbox tree, then deletes the sandbox. It works the same on Windows and POSIX.

```bash
node .claude/skills/run-claude-dev-env/driver.mjs
```

Expected tail:

```
16/16 checks passed.
ALL CHECKS PASSED
```

The driver proves a full install lands skills, hook scripts, rules, the `CLAUDE.md` hub, a populated `settings.json`, and a tracking manifest under `<sandbox>/.claude/`, and that `--uninstall` removes every manifest-tracked file. The real `~/.claude/` and the real global git config stay untouched. Exit code is 0 only when all checks hold.

## Run (human path) — install for real

These write into your real `~/.claude/` and set a global git hooks path. Run them only when you mean to install on this machine.

```bash
node bin/install.mjs --help         # usage only, no side effects
node bin/install.mjs                # install every group
node bin/install.mjs --only core    # install one or more named groups
node bin/install.mjs --update       # remove manifest-tracked files, then reinstall
node bin/install.mjs --uninstall    # remove every installed file
```

Groups: `core`, `prompt-generator`, `journal`, `research`. The published package runs the same entry point as `npx claude-dev-env`.

## Test

```bash
npm test
```

Runs `node --test` over `bin/*.test.mjs` and `skills/**/*.test.mjs` with Node's built-in test runner — no extra dependency, no network. Expected: `# pass 185  # fail 0` (count grows as tests are added).

## Gotchas

- **The install target is `os.homedir()/.claude` with no override flag** (`bin/install.mjs:12`). To drive the installer without overwriting your real config, redirect the home directory: set `USERPROFILE` (Windows) and `HOME` (POSIX) to a temp dir. The driver does this for you.
- **The installer reaches outside `~/.claude/`.** It runs `git config --global core.hooksPath ...`, which applies to every git repo on the machine, and it writes `~/.mypy.ini`. The driver isolates both by pointing `GIT_CONFIG_GLOBAL` at a sandbox file and redirecting the home directory.
- **git "dubious ownership" aborts the install.** The source-conflict guard runs `git status`; when the checkout sits on a path git distrusts (a UNC network share owned by another account), git exits 128 with a dubious-ownership message that the installer rethrows. The driver seeds its sandbox git config with `safe.directory = *` so the guard runs. For a real install on such a checkout, add the exception: `git config --global --add safe.directory '<repo-path>'`.
- **`npm install` at the repo root fails on a Windows network-share checkout.** npm symlinks the workspace package into root `node_modules` and the share rejects the symlink (`UNKNOWN ... symlink`, errno -4094). The package's own `node_modules` already carries its single dependency, so the driver and tests run without it. The installer also keeps working when `@jl-cmd/prompt-generator` cannot resolve — it skips that group with a warning (`bin/install.mjs:99-104`).
- **Microsoft Store Python is rejected on Windows.** The installer skips any interpreter under a `WindowsApps` directory because that stub cannot run as a hook subprocess (`bin/install.mjs:201-203`). Install Python from python.org if detection fails.

## Troubleshooting

- **`ERROR: No usable Python 3 found`**: no `py -3` / `python3` / `python` resolves to a non-Store Python 3. Install Python 3.8+ from python.org and reopen the shell.
- **`fatal: detected dubious ownership in repository`**: add the `safe.directory` exception shown above, then rerun.
- **`ERROR: settings.json is malformed JSON`**: `~/.claude/settings.json` has a syntax error; fix the JSON and rerun.

## Files

- `SKILL.md` — this page: the agent path (the driver), the human install path, the test command, gotchas, and troubleshooting.
- `driver.mjs` — the smoke harness that drives `bin/install.mjs` against a sandbox home directory. Run it; you do not need to read it. It sits beside this file at `.claude/skills/run-claude-dev-env/driver.mjs`.

The `/run` skill auto-discovers this skill when asked to run, install, or test `claude-dev-env`.
