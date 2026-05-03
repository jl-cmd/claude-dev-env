# Code rules for Claude, Cursor BugBot, Copilot, and other agents

This file is the **canonical** review-criteria instruction set for every AI agent that audits pull requests in this repository:

- **Claude** (PR review)
- **Cursor BugBot** (PR review)
- **GitHub Copilot** (PR review)
- Any other agent that loads `AGENTS.md` or `.cursor/BUGBOT.md` for review

These rules describe the green-light state of code in this repository. Agents apply them to the **lines a PR adds or modifies**, surface deviations as findings, and recommend corrections. Output is review feedback.

Where a rule lists exemptions (test files, migrations, config files), the exemption applies. Where a rule shows a before/after pair, the "after" form is the green-light pattern.

This file is **rules-only**. Repo layout, build commands, and workflow guidance live elsewhere.

---

## Contents

- [Comments](#comments)
- [Naming](#naming)
- [Magic values & configuration](#magic-values--configuration)
- [Types](#types)
- [Structure](#structure)
- [Design](#design)
- [Tests](#tests)
- [Platform and tooling](#platform-and-tooling)
- [Repo hygiene](#repo-hygiene)
- [Scope of review](#scope-of-review)
- [Hook enforcement](#hook-enforcement)

Many bullets are implemented in `packages/claude-dev-env/hooks/blocking/code_rules_enforcer.py` (`validate_content` for Python and a small JavaScript subset). The default `PreToolUse` `Write|Edit` chain in `packages/claude-dev-env/hooks/hooks.json` does **not** register that script today; other hooks there (for example `tdd_enforcer.py`, `windows_rmtree_blocker.py`, and the `run_all_validators` entrypoint) cover overlapping or adjacent concerns on a different trigger model. **Hook enforcement** below maps rules to their **source script** and notes Python-only coverage where it applies. Flag violations from the diff in review even when no local hook runs the same check.

---

## Code rules

### Comments

- New production code uses self-documenting identifier names. New `#`/`//` inline comments added in production code are findings; new `#`/`//` standalone comment lines and `/* ... */` block comments at line start (non-docblock) are advisory ONLY. Docstrings, `/** ... */` JSDoc docblocks, and standalone directive-marker lines (the markers listed below) are exempt. Python inline directive markers (`# noqa`, `# type:`, `# pylint:`, `# pragma:` mid-line) are also exempt; inline JS/TS directive markers (`// @ts-...`, `// eslint-...`, `// prettier-...` mid-line) remain findings.
- **IMPORTANT:** Existing comments remain exactly as written. Comments in the surrounding file are sacred.
- Docstrings on new functions, methods, classes, and modules (including module-level docstrings) are welcome.
- **Test files (`test_*.py`, `*_test.py`, `*.test.*`, `*.spec.*`, `conftest.py`) are fully exempt** — inline comments and docstrings inside test functions are welcome.
- Directive markers remain exactly as written: shebangs, `# type:`, `# noqa`, `# pylint:`, `# pragma:`, `// @ts-...`, `// eslint-...`, `// prettier-...`, and `/// ` triple-slash reference directives.

### Naming

#### Identifiers

- Identifiers use full words. Common abbreviations to expand: `ctx → context`, `cfg → configuration`, `msg → message`, `btn → button`, `idx → index`, `cnt → count`, `elem → element`, `val → value`, `tmp → temporary_value`.
- Component names describe what the component IS: `Overlay`, `Validator`, `InvoicePreview`. Generic placeholders to replace: `Screen → Overlay`, `Handler → Validator`, `Wrapper → InvoicePreview`.

#### Loop variables

- Multi-letter loop variables carry the `each_` prefix: `each_order`, `each_user`. Single-letter `i`, `j`, `k` apply to indices; `e` applies to caught exceptions.

#### Booleans, collections, and maps

- Boolean variables, parameters, and methods carry an `is_`, `has_`, `should_`, or `can_` prefix: `is_ready`, `has_payload`, `should_retry`, `can_skip`.
- Collection variables carry the `all_` prefix: `all_orders`, `all_pending_jobs`.
- Maps and dicts follow the `X_by_Y` pattern: `price_by_product`, `user_by_id`.

#### Parameters and banned names

- Direction and source parameters carry a preposition prefix: `from_path=`, `to=`, `into=`.
- Identifiers in production code describe domain meaning: `parsed_invoice`, `pending_orders`, `cached_lookup`. Generic placeholders to replace: `result`, `data`, `output`, `response`, `value`, `item`, `temp`.
- Function names use specific verbs: `parse_invoice`, `dispatch_event`, `migrate_schema`. Generic prefixes to replace: `handle_`, `process_`, `manage_`, `do_`.

### Magic values & configuration

- Production function bodies use named constants for numeric, string, and boolean values. Inline literals stay acceptable for `0`, `1`, `-1`, the empty string, and `True`/`False` when the meaning is obvious.
- **Test files are exempt** — literal values in test functions and test-local constants are welcome.
- Production code extracts structural fragments inside f-strings (paths, URLs, query patterns, regex) into named constants.
- **IMPORTANT:** Production code places `UPPER_SNAKE_CASE` constants under `config/` (`config/timing.py`, `config/constants.py`, `config/selectors.py`). Path exemptions (treat paths as case-insensitive, normalize backslashes to forward slashes, then check whether each pattern below appears anywhere in the path as a substring):
  - Django migrations: path contains `/migrations/`
  - Workflow registries: path contains any of these substrings — `/workflow/`, `_tab.py`, `/states.py`, or `/modules.py`. Each substring matches independently against the path; `pkg/states.py` qualifies because `/states.py` appears as a substring, while a top-level `states.py` follows the standard `config/` rule.
  - Test files: path or filename matches common test layout signals (`test_`, `_test.`, `.spec.`, `conftest`, `/tests/`); test files may define local constants directly.
- New constants belong in `config/`, in the file matching their domain:

| Constant type | File |
|---|---|
| Timeouts, delays, retries, polling intervals | `config/timing.py` |
| Ports, URLs, thresholds, magic numbers, named strings | `config/constants.py` |
| CSS selectors, DOM locators, XPath queries | `config/selectors.py` |

- New constants reuse existing entries where the value or semantic name already lives in another `config/` file. Flag a new constant whose value or semantic name already appears elsewhere in `config/` — the diff should import the existing constant rather than redefine it. Flag a new `config/` file when an existing file's domain already covers the constant.

#### File-global constants

For every file-global constant declared at module scope in production code outside `config/`, count how many methods, functions, classes, or module-level expressions in the same file consume it. **0 references:** dead code; the diff removes the constant. **1 reference:** the value moves to `config/`, and the consumer takes one of these green-light forms — a local alias inside the consuming method, a class attribute (when the sole consumer is a class), an inlined local constant (when the value avoids reintroducing a magic literal), or a direct module-scope reference (when the sole consumer is a module-level expression); see the linked rule for the full decision table. **2+ references:** the constant stays at file scope. Test files and `config/` files are exempt.

Full rule including the decision table, examples, and reference-counting details: [`packages/claude-dev-env/rules/file-global-constants.md`](packages/claude-dev-env/rules/file-global-constants.md).

### Types

- Function parameters and return values carry type annotations.
- Python `# type: ignore` directives carry a second trailing `#` comment with ≥5 characters of justification (e.g. `# type: ignore[misc]  # stubs missing in foo library`). Plain trailing text without a leading `#` does not satisfy the rule. The trailing reason comment is part of the directive and exempt from the comment-preservation rule.
- `Any` (Python) and `any` (TypeScript/JavaScript) annotations are findings — author should replace with an explicit type.
- Concrete types match the value's actual shape.

### Structure

- File length is advisory (stderr only): a soft note above ~400 lines, a stronger note above ~1000 lines. The file's role (migrations, generated code, registries, large fixtures) justifies any size.
- Functions stay at 30 lines or fewer. If it's longer, flag as advisory ONLY.
- Top-level functions follow the language's blank-line convention: Python uses two blank lines between top-level functions. Other languages defer to file-established convention.
- `import` statements live at the top of the file.
- Application and library code uses logging calls. CLI tools and automation entrypoints may use `print()` when stdout is the integration contract (`print(json.dumps(...))`).
- `log_*` and `logger.*` calls use `%`-style placeholders: `logger.info("delivered %s", message_id)`.

### Design

- Functions handle stateless work. Concrete classes handle stateful single-implementation cases. Abstract base classes, dependency-injection frameworks, and factories arrive when two or more concrete implementations exist or are imminent.
- SRP (SOLID **S**): each function, class, or module has one reason to change. Cohesive code stays together — an 80-line cohesive class remains a single class.
- OCP / LSP / ISP / DIP scaffolding (interfaces, ABCs, abstract factories, DI containers) arrives when two or more concrete implementations exist or are imminent.
- Optional parameters appear when at least one call site varies the value (YAGNI). When every existing call site passes the same value, make the parameter required (or inline the value as a local constant). Remove parameters that no caller passes and no body reads.
- Construction logic (paths, URLs, formatting, transformations) lives in the model or service that owns the data. The same string-building pattern appearing at two call sites belongs as a method on the owning model.
- Components own their complete feature: each manages its own state, modals, overlays, and toasts; parents render `<Child />` alone.
- Functions reuse data already in scope; the existing record passes through to where it's needed.
- Scaffolding and placeholder code carry a `TODO:` comment naming what replaces it and why.

### Tests

- Every new production code path ships with a paired test in the same PR (BDD: behavior is agreed first, then a failing specification, then the production code that satisfies it).
- Mocks populate every field the code under test reads — every attribute touched by the code path appears on the mock. If a mock omits a field, flag as advisory ONLY.
- Assertions exercise behavior. Replace tautologies (`assert CONSTANT == CONSTANT`, `assert hasattr(module, "name")`) with assertions that would fail on real regression.
- Delete tests that add no value: tests that only verify a function exists (`callable(func)`), tests that re-assert constant values (`assert CACHE_DIR == "cache"`), and tests that duplicate coverage already provided by another test.
- When a system dependency is missing, the test fails with a clear error rather than skipping. Do not use `@skip_if_missing_dependency`, environment-based skip decorators, or guard clauses that swallow the missing dependency.
- Keep test infrastructure pragmatic. A test helper file passes when all of these hold: (1) ONE file, not a package; (2) only `def` functions, no class definitions; (3) no module-level state besides one or two simple constants; (4) no caching, no lazy initialization, no abstractions added "for future use"; (5) imports cover the test target plus stdlib only — no helper imports another helper.
- Test through the public API. Do not assert on private state, hook return values, internal class fields, or `component.state.X`. If the test needs visibility the public API does not provide, the public API needs a method, not the test.
- For React components, query in this priority order: `getByRole` → `getByLabelText` → `getByText` → `getByTestId`. Use `userEvent` over `fireEvent`. Mock at API boundaries (network calls, external services), not internal hooks or utilities.

### Platform and tooling

- On Windows, do not call `shutil.rmtree` with the `ignore_errors=True` keyword argument. Files carrying the `ReadOnly` attribute (`.git/objects/pack/`, anything Claude Code writes under `~/.claude/teams/`) raise `PermissionError`, which the keyword silently swallows; the tree stays on disk and cleanup looks successful but removes nothing. Linux is unaffected because `unlink` only needs write on the parent directory. Tests using `pytest`'s `tmp_path` do not exercise this path; the regression appears only on real Windows checkouts. Replace with the canonical handler that strips `S_IWRITE` and retries the failing syscall — see `~/.claude/rules/windows-filesystem-safe.md` for the full pattern.
- On Windows, when calling Node `mkdirSync(path)` against a path that may already exist, use `{ recursive: true }` so existing directories with the `ReadOnly` attribute do not raise. If a non-recursive `mkdirSync` is required for an explicit existence assertion, strip the attribute via `os.chmod(path, stat.S_IWRITE)` (Python) or `(Get-Item $path -Force).Attributes = "Directory"` (PowerShell) before the call.
- All `gh` commands that include markdown body content use `--body-file <path>` with a temp file. Never pass body text via the `--body` argument or its `-b` shorthand. Inline backticks in body arguments may be stored on GitHub as the literal string `\`` instead of rendering as code formatting. Affects: `gh issue create|edit|comment`, `gh pr create|edit|comment|review`.

### Repo hygiene

- Do not commit working documents or generated artifacts. The following must not appear in any PR diff:
  - Planning files: `docs/plans/*.md`, `*.plan.md`, `SESSION_STATE.md`, `*.audit.json`, `*.audit.md`.
  - Image assets: `*.png`, `*.jpg`, `*.jpeg`, `*.gif`, `*.webp`, `*.avif`, `*.svg`, `*.ico` (image assets belong in external storage, not the repo).
- Flag the following file categories for removal before merge unless the PR description explicitly states the reason they are kept:
  - Scripts written to test a hypothesis or run a one-off check (e.g. `scratch_*.py`, `debug_*.py`, `try_*.py`, `repro_*.py`).
  - Debug output files, log dumps, and intermediate data exports (e.g. `*.log` outside `logs/`, `output_*.txt`, `dump_*.json`).
  - Helper files created to work around a tool limitation that the PR did not explicitly call out.
  - Any file the PR description does not reference and that a reviewer cannot trace to one of the listed changes.

### Scope of review

- **IMPORTANT:** Every rule applies to the **lines a PR adds or modifies**. Unrelated lines stay as-is.
- For new files, every line is in scope.
- Findings outside the changed lines surface as advisories.

---

## Hook enforcement

The table lists **where the rule is encoded** (the script or module that implements it). Registration for `PreToolUse`, `PostToolUse`, `Bash`, and other matchers lives in `packages/claude-dev-env/hooks/hooks.json`; a script can exist in the tree without being wired to every event. Rows that cite `code_rules_enforcer.py` apply to **Python** sources inside `validate_content` (plus the narrow JS/TS checks described in that function); they are **not** a guarantee that the same AST checks run for every language in the repo. Many additional `check_*` rules live in that module; this table is representative, not exhaustive.

| Rule | Source |
|---|---|
| No new inline comments in production diffs | `code_rules_enforcer.py` (Python; JS/TS comment-change checks only where `validate_content` runs them) |
| Imports at file top, never inside functions | `code_rules_enforcer.py` (Python) |
| Logging format args (no f-strings inside `log_*` and `logger.*`) | `code_rules_enforcer.py` (Python) |
| No literal values in production function bodies | `code_rules_enforcer.py` (Python) |
| `UPPER_SNAKE_CASE` constants live under `config/` | `code_rules_enforcer.py` (Python) |
| Production `Write|Edit` touches require a recently modified sibling test candidate | `tdd_enforcer.py` (heuristic freshness gate — not a proof that a brand-new test assertion shipped in the same PR) |
| `shutil.rmtree` `ignore_errors=True` blocked on Windows | `windows_rmtree_blocker.py` |
| `gh ... --body` markdown bodies must use `--body-file` | Policy in [Platform and tooling](#platform-and-tooling); no `gh_body_arg_blocker.py` entry in the default `hooks.json` chain |
