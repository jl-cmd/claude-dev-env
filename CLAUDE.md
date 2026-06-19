# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A monorepo that builds and ships **`claude-dev-env`** — an npm package of shared Claude Code config (rules, docs, commands, agents, skills, and Python hooks). Users run `npx claude-dev-env` to copy these files into `~/.claude/` and merge the hook entries into their `settings.json`. Editing files under `packages/claude-dev-env/` changes what every user receives on their next install, so treat that directory as a published surface, not a private workspace.

`package.json` at the root declares the npm workspace (`packages/*`); `packages/claude-dev-env/` is the only package.

## Commands

Run from the repo root unless noted. The shell is Windows `pwsh`.

| Task | Command |
|------|---------|
| JS tests (installer + skill scripts) | `cd packages/claude-dev-env && npm test` |
| Python tests (whole repo) | `python -m pytest` |
| One Python test file | `python -m pytest tests/test_fan_out_dispatch.py` |
| Quality gate (ruff + mypy + enforcer tests) | `pwsh -File packages/claude-dev-env/scripts/check.ps1` |
| Install locally to `~/.claude/` | `cd packages/claude-dev-env && node bin/install.mjs` |

Notes:

- `npm test` runs `node --test` over `bin/*.test.mjs` and `skills/**/*.test.mjs` — the installer and skill helper scripts.
- The root `pytest.ini` sets `--import-mode=importlib`, puts `.` and `.github/scripts` on `pythonpath`, and collects both `test_*` and `should_*` functions.
- Hook tests live next to the hooks they cover (for example `packages/claude-dev-env/hooks/blocking/test_code_rules_enforcer*.py`). `check.ps1` runs mypy over `hooks/blocking` and `hooks/validators` using `hooks/pyproject.toml`, then runs the enforcer pytest suite. It exits on the first failing tool and prints `CHECK: OK` or `CHECK: FAILED tools=...`.
- The Python hook packages (the `*_constants` modules) are declared in `packages/claude-dev-env/pyproject.toml`. Install them editable (`pip install -e packages/claude-dev-env`) so hook tests resolve their constant imports.

## Architecture

### The install pipeline

`packages/claude-dev-env/bin/install.mjs` is the entry point. It detects the user's Python command, copies each shipped directory (`rules/`, `docs/`, `commands/`, `agents/`, `skills/`, `hooks/`, `system-prompts/`, `scripts/`, `_shared/`, `audit-rubrics/`, `CLAUDE.md`) into `~/.claude/`, rewrites hook paths to absolute locations, merges hook groups into `~/.claude/settings.json` without dropping the user's own entries, and writes `~/.claude/.claude-dev-env-manifest.json` for a clean uninstall. The `--only <group>` flag installs a subset; the groups are `core`, `journal`, `research`, and the discovered `prompt-generator` dependency group (run `node bin/install.mjs --help` for the live list). When changing how anything installs or syncs, read `docs/references/skill-install-system.md` first — it maps this pipeline.

### Hooks

Hooks are Python scripts under `packages/claude-dev-env/hooks/`, grouped by role: `blocking/` (PreToolUse gates that deny a Write/Edit/Bash and return a corrective message), `advisory/`, `validation/` (the mypy and hook-format validators), `validators/` (the `run_all_validators` entry point and its check modules), `diagnostic/`, `session/`, `lifecycle/`, `observability/`, `workflow/`, and `git-hooks/`. `hooks/hooks.json` is the registration map — a script can sit in the tree without being wired to an event, so check `hooks.json` to know what actually runs.

The largest blocking hook is `blocking/code_rules_enforcer.py`; its `validate_content` runs the AST checks for Python (and a narrow JS/TS subset) that enforce CODE_RULES at write time. Many sibling `code_rules_*.py` modules hold individual checks it composes.

### Constants packages

CODE_RULES forbids `UPPER_SNAKE_CASE` constants and magic values outside designated config modules — and the hooks hold themselves to that rule. So every hook area has a companion constants package (`hooks/hooks_constants/`, `_shared/pr-loop/scripts/pr_loop_shared_constants/`, each skill's `*_constants/`, and so on). `packages/claude-dev-env/pyproject.toml` maps each logical package name to its nested directory. When you add a constant for a hook or skill script, it belongs in that area's constants package, not inline.

### AI review rules (`AGENTS.md`)

`AGENTS.md` at the root is the single source for PR-review criteria — the same CODE_RULES, restated as findings that an agent applies to the lines a PR changes. `.github/scripts/sync_ai_rules.py` (driven by `.github/workflows/sync-ai-rules.yml` and `fan-out-ai-rules.yml`) syncs it to the Cursor BugBot rules file `.cursor/BUGBOT.md`. Edit `AGENTS.md`; never hand-edit the generated `.cursor/BUGBOT.md` copy.

CODE_RULES has two enforcement surfaces that must stay in step: `code_rules_enforcer.py` blocks violations at Write/Edit time, and `AGENTS.md` describes the same rules for PR review. A rule change usually touches both.

### Skills, agents, commands

These ship as plain files (`skills/<name>/SKILL.md` and helper scripts, `agents/*.md`, `commands/*.md`). The installer copies them verbatim into `~/.claude/`. A skill's executable helpers carry their own tests (`skills/**/*.test.mjs` for JS, `test_*.py` beside Python helpers).

## Conventions specific to this repo

- **Conventional Commits + release-please.** `release-please-config.json` drives versioning and `CHANGELOG.md` for the `claude-dev-env` package from commit types (`feat`, `fix`, `docs`, `chore`, `refactor`, `perf`, `ci`, `style`, `test`, `build`, `revert`). `publish.yml` releases to npm. `pr-check.yml` validates that the PR title is a semantic commit.
- **Two `CLAUDE.md` files ship to users.** `packages/claude-dev-env/CLAUDE.md` installs to `~/.claude/CLAUDE.md`. This root `CLAUDE.md` is for contributors and is not packaged.
- **Markdown is timeless and plain.** The `state-description-blocker` hook rejects historical or comparative phrasing (`previously`, `instead of`, `migrated from`, ...) in `.md` writes, and `plain_language_blocker` rejects heavy words in `.md` and `AskUserQuestion` content. Write what the system *is*, in everyday words.
