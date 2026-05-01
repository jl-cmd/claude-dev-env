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
- [Scope of review](#scope-of-review)

---

## Code rules

### Comments

- New production code uses self-documenting identifier names. New inline comments added in production code are findings. New standalone comment lines are advisory ONLY.
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
  - Workflow registries: path contains the substring `/workflow/`, `_tab.py`, `/states.py`, or `/modules.py` (the exemption applies when the workflow segment appears in the path, so `pkg/states.py` qualifies while a top-level `states.py` follows the standard `config/` rule)
  - Test files: path or filename matches common test layout signals (`test_`, `_test.`, `.spec.`, `conftest`, `/tests/`); test files may define local constants directly.
- New constants reuse existing entries where the value or semantic name already lives in another `config/` file.

#### File-global constants

For every file-global constant declared at module scope in production code outside `config/`, count how many methods, functions, or classes in the same file consume it. **0 references:** dead code; the diff removes the constant. **1 reference:** the value moves to `config/` with a local alias inlined inside the consuming method. **2+ references:** the constant stays at file scope. Test files and `config/` files are exempt.

Full rule including the decision table, examples, and reference-counting details: [`packages/claude-dev-env/rules/file-global-constants.md`](packages/claude-dev-env/rules/file-global-constants.md).

### Types

- Function parameters and return values carry type annotations.
- `Any`, `any`, and `# type: ignore` carry a one-line note explaining the constraint.
- Concrete types match the value's actual shape.

### Structure

- File length is advisory: a soft note above ~400 lines, a stronger note above ~1000 lines. The file's role (migrations, generated code, registries, large fixtures) justifies any size.
- Functions stay at 30 lines or fewer. If it's longer, flag as advisory ONLY.
- Top-level functions follow the language's blank-line convention: Python uses two blank lines between top-level functions. Other languages defer to file-established convention.
- `import` statements live at the top of the file.
- Application and library code uses logging calls. CLI tools and automation entrypoints may use `print()` when stdout is the integration contract (`print(json.dumps(...))`).
- `log_*` and `logger.*` calls use `%`-style placeholders: `logger.info("delivered %s", message_id)`.

### Design

- Functions handle stateless work. Concrete classes handle stateful single-implementation cases. Abstract base classes, dependency-injection frameworks, and factories arrive when two or more concrete implementations exist or are imminent.
- SRP (SOLID **S**): each function, class, or module has one reason to change. Cohesive code stays together — an 80-line cohesive class remains a single class.
- OCP / LSP / ISP / DIP scaffolding (interfaces, ABCs, abstract factories, DI containers) arrives when two or more concrete implementations exist or are imminent.
- Optional parameters appear when at least one call site varies the value (YAGNI — otherwise the parameter stays required, or the value stays inlined).
- Construction logic (paths, URLs, formatting, transformations) lives in the model or service that owns the data. The same string-building pattern appearing at two call sites belongs as a method on the owning model.
- Components own their complete feature: each manages its own state, modals, overlays, and toasts; parents render `<Child />` alone.
- Functions reuse data already in scope; the existing record passes through to where it's needed.
- Scaffolding and placeholder code carry a `TODO:` comment naming what replaces it and why.

### Tests

- Every new production code path ships with a paired test in the same PR (BDD: behavior is agreed first, then a failing specification, then the production code that satisfies it).
- Mocks populate every field the code under test reads — every attribute touched by the code path appears on the mock. If a mock omits a field, flag as advisory ONLY.
- Assertions exercise behavior. Replace tautologies (`assert CONSTANT == CONSTANT`, `assert hasattr(module, "name")`) with assertions that would fail on real regression.

### Scope of review

- **IMPORTANT:** Every rule applies to the **lines a PR adds or modifies**. Unrelated lines stay as-is.
- For new files, every line is in scope.
- Findings outside the changed lines surface as advisories.
