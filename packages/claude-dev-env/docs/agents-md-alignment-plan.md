# AGENTS.md Alignment Plan

This document captures the alignment between `AGENTS.md` (the canonical code-rules instruction set consumed by Cursor BugBot, Copilot, Claude, and other code-review/authoring agents) and the local enforcement layer (`code_rules_enforcer.py` and companion blocking hooks).

## Goal

Two-way alignment:

1. Every rule the hooks enforce at write time is documented in `AGENTS.md` so review tools without hook access (Cursor BugBot, Copilot, external reviewers) flag the same violations from the diff alone.
2. Every rule `AGENTS.md` requires is either (a) enforced by a hook at write time, (b) explicitly listed as bugbot-only judgment because it requires diff-semantic reasoning, or (c) a candidate for a future hook.

This file is the single source of truth for the alignment status.

## Methodology

- Read every `check_*` function in `packages/claude-dev-env/hooks/blocking/code_rules_enforcer.py` (28 functions, lines 108–2236) plus the `validate_content` dispatch (line 2239).
- Read every Write/Edit hook registered in `packages/claude-dev-env/hooks/hooks.json`.
- Read `packages/claude-dev-env/hooks/blocking/sensitive_file_protector.py` for file-level blocks.
- Read every rule file in `~/.claude/rules/*.md` and the canonical CODE_RULES.md files in this repo.
- Walked `AGENTS.md` bullet by bullet against the above.

## What this PR changes

### Added to `AGENTS.md`

- Intro pointer to the new **Hook enforcement** appendix.
- **Magic values & configuration**: explicit config-domain table (`config/timing.py` for timing values, `config/constants.py` for ports/URLs/thresholds, `config/selectors.py` for DOM locators) and a flag rule for new constants whose value or semantic name already exists in `config/`.
- **Design**: tightened the YAGNI bullet to specify "every existing call site passes the same value → required (or inline)".
- **Tests**: five new bullets — delete-no-value tests, fail-not-skip rule, pragmatic-infra five-point checklist, public-API-only assertions, React query priority and `userEvent`/API-boundary mocking.
- **Platform and tooling**: the unsafe-`rmtree`-on-Windows pattern is blocked (with the canonical `force_rmtree` helper inlined), Node `mkdirSync` requires `{ recursive: true }` on possibly-existing paths, and all `gh` commands with markdown body content must use `--body-file`.
- **Repo hygiene**: never-commit list (`docs/plans/*.md`, `*.plan.md`, `SESSION_STATE.md`, `*.audit.json`, `*.audit.md`, image extensions) and a scratch-file pattern enumeration.
- **Hook enforcement** appendix mapping each hook-enforced rule to its enforcing hook file.

### Deliberately excluded

PR draft lifecycle bullets and one-commit-per-review-stage rules were proposed and then removed. Cursor BugBot reviews diffs and PR descriptions; it cannot toggle PR ready/draft state or enforce commit-stage discipline. Those rules belong in human-facing workflow documentation, not in `AGENTS.md`.

## Open items

The following are documented gaps. None are addressed in this PR.

### Category A — enforced locally, not yet in AGENTS.md

Each closure is concrete and additive — recommended for a follow-up PR titled `docs(agents): close remaining hook-vs-rule gaps`.

| ID | Hook check (file:line) | Gap |
|---|---|---|
| A1 | `code_rules_enforcer.py:404` `check_windows_api_none` | `win32gui.X(.., None)` — use `0` for unused int params |
| A2 | `code_rules_enforcer.py:603` `check_e2e_test_naming` | `online`/`offline` in `test()`/`it()`/`describe()` titles in `*.spec.*` files |
| A3 | `code_rules_enforcer.py:713` `check_type_escape_hatches` | `# type: ignore` requires trailing `# <reason>` of ≥5 chars |
| A4 | `code_rules_enforcer.py:2126` `check_inline_literal_collections` | inline `[...]` / `{...}` of constants in production function bodies |
| A5 | `code_rules_enforcer.py:2085` `check_string_literal_magic` | bare string literals (not just f-string fragments) matching path / URL / regex shape |
| A6 | `code_rules_enforcer.py:843` `check_constants_outside_config_advisory` | function-local `UPPER_SNAKE = ...` advisory |
| A7 | `code_rules_enforcer.py:2003` `check_library_print` | `print()` outside CLI markers (`/scripts/`, `_cli.py`, `/cli.py`) |
| A8 | `sensitive_file_protector.py` | edits to `package-lock.json`, `yarn.lock`, `Pipfile.lock`, `poetry.lock`, `pnpm-lock.yaml`, `composer.lock` |
| A9 | `sensitive_file_protector.py` | edits to `.env*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `credentials.json`, `secrets.json`, `id_rsa`, `id_ed25519` |
| A10 | `code_rules_enforcer.py:1175` `check_existence_check_tests` | `x is not None` as sole-assertion form (currently `AGENTS.md` lists only `callable` and `hasattr`) |
| A11 | `code_rules_enforcer.py:1839` `check_unused_optional_parameters` | the exact trigger: optional param where every call site passes the same value |
| A12 | `mypy_validator.py` | mypy-clean is required at write time |
| A13 | `auto_formatter.py` | auto-formatter runs on Write/Edit |
| A14 | `code_rules_enforcer.py:1072` `check_skip_decorators_in_tests` | the broader rule is "any decorator named `skip*`", not just `@skip_if_missing_dependency` |
| A15 | `code_rules_enforcer.py:1786` `check_duplicated_format_patterns` | identical format-string patterns at multiple call sites |

### Category B — required by AGENTS.md, no local hook (bugbot-only judgment)

These are reviewable from a diff but not amenable to AST/regex enforcement; they remain bugbot's judgment.

- **Naming**: `ctx`/`cfg`/`msg`/`btn`/`idx`/`cnt`/`elem`/`val`/`tmp` abbreviation expansion (B1); `X_by_Y` map naming (B2); preposition parameter prefixes (B3); banned function-name prefixes `handle_`/`process_`/`manage_`/`do_` (B4); component naming for what they ARE (B5).
- **Structure**: function length ≤ 30 lines (B6); two blank lines between Python top-level functions (B7).
- **Types**: concrete type captures actual shape, even when bare `object` would compile (B8).
- **Architecture**: functions vs classes vs ABCs (B9); SOLID S/O/L/I/D (B10); construction logic in models/services (B11); self-contained components (B12); `TODO:` on scaffolding (B14).
- **Data flow**: reuse data already in scope (B13); reuse-before-create semantic duplication (B23).
- **Tests**: pragmatic-infra five-point checklist (B15); test through public API (B16); React query priority and mocking strategy (B17).
- **Platform**: Node `mkdirSync({recursive: true})` (B18) — Python `shutil.rmtree` is hooked, Node equivalent is not.
- **Hygiene**: planning/image file globs (B19); scratch-file patterns (B20); PR-description references for kept files (B21).
- **Config**: domain placement within `config/` (B22); 0-reference dead-code constants (B24).

### Category C — JS/TS asymmetry

`code_rules_enforcer.py` `validate_content` (line 2239) dispatches on file extension. For `.js`/`.ts`/`.tsx`/`.jsx`, only three checks run:

- `check_comment_changes` — added inline / removed existing comments.
- `check_e2e_test_naming` — online/offline in spec test titles.
- `advise_file_line_count` — advisory.

Every other rule (magic values, constants location, banned identifiers, type annotations, boolean naming, loop variable naming, parameter annotations, return annotations, library print, optional-param-unused, `Any` detection) runs on Python files only. For JS/TS code, `AGENTS.md` is the only enforcement layer — bugbot review is the gate.

Whether each Python check has a JS/TS equivalent that ports cleanly: not investigated. Out of scope for this PR.

## Recommended hook additions

Not part of this PR — proposed as separate small PRs (one new check + tests per PR, following the existing `test_code_rules_enforcer_*.py` pattern). Each is AST/regex-tractable.

| Item | Suggested check | Note |
|---|---|---|
| B1 | extend `BANNED_IDENTIFIERS` | add `ctx`, `cfg`, `msg`, `btn`, `idx`, `cnt`, `elem`, `val`, `tmp` |
| B2 | dict-target naming rule | flag dict assignments whose target name lacks `_by_` |
| B3 | parameter-name prefix rule | flag direction parameters lacking `from_`/`to_`/`into_` |
| B4 | banned function-name prefixes | flag `def handle_*`, `def process_*`, `def manage_*`, `def do_*` |
| B6 | function-length advisory | per-function line count, advisory above 30 |
| B19 | extend `sensitive_file_protector.py` | block edits to `*.plan.md`, `SESSION_STATE.md`, `docs/plans/*.md`, `*.audit.{json,md}`, image extensions |
| B20 | scratch-file name patterns | block edits to `scratch_*.py`, `debug_*.py`, `try_*.py`, `repro_*.py` |
| B22 | config-domain placement | flag a constant added to `config/constants.py` whose name suggests `timing.py` or `selectors.py` |
| B24 | 0-reference dead-code constants | extend `check_file_global_constants_use_count` to also flag 0 callers |

## Files in this PR

- `AGENTS.md` (modified) — adds the rules and sections listed above.
- `packages/claude-dev-env/docs/agents-md-alignment-plan.md` (new) — this document.

## Verification

- Read updated `AGENTS.md` end-to-end and confirm each new bullet lives under the correct section heading.
- Confirm no rule mentioned in the **Hook enforcement** appendix is missing its source check in `code_rules_enforcer.py` or sibling hook file.
- Confirm the canonical `force_rmtree` helper code block in **Platform and tooling** describes the rule without containing the exact match-string the `windows_rmtree_blocker.py` hook scans for. Otherwise the hook will block any future edit to the file.
- No code changes — the `AGENTS.md` and plan doc are documentation only.

## Out of scope

- Closing the Category A gaps in `AGENTS.md` (tracked above; recommended follow-up PR).
- Implementing any of the Category B hook additions (each is its own small PR).
- Investigating JS/TS hook coverage parity (Category C).
- Changes to `code_rules_enforcer.py` or any other hook source file.
