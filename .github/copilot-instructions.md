# Code Review Instructions for LLMs

Review every change against these rules. Flag each violation with its rule name. Treat rules as mandatory standards; honor file-level exception markers where they appear.

## Comments
- Flag every new inline comment (`#` or `//`) added to modified **production** code; require self-documenting names.
- Preserve every existing comment as-is; treat comments in the surrounding file as sacred.
- Allow docstrings on new functions, methods, classes, or modules (including module-level docstrings).
- **Test files (`test_*.py`, `*_test.py`, `*.test.*`, `*.spec.*`) are fully exempt** — comments and docstrings inside test functions are allowed.
- Exempt markers: shebangs, `# type:`, `# noqa`, `# pylint:`, `# pragma:`, `// @ts-...`, `// eslint-...`, `// prettier-...`, and `/// ` triple-slash reference directives.

## Naming
- Require full words: `context` for `ctx`, `configuration` for `cfg`, `message` for `msg`, `button` for `btn`, `index` for `idx`, `count` for `cnt`, `element` for `elem`, `value` for `val`, `temporary_value` for `tmp`.
- Allow single-letter loop variables `i`, `j`, `k`, and `e` for caught exceptions.
- Require the `each_` prefix on other loop variables (`each_order`, `each_user`).
- Require booleans to use `is_`, `has_`, `should_`, or `can_` prefixes.
- Require the `all_` prefix on collection names (`all_orders`).
- Require maps to follow `X_by_Y` (`price_by_product`, `user_by_id`).
- Require preposition parameter names: `from_path=`, `to=`, `into=`.
- Flag banned identifiers: `result`, `data`, `output`, `response`, `value`, `item`, `temp`.
- Flag banned function-name prefixes: `handle`, `process`, `manage`, `do`.
- Require component names that describe what the component is (`Overlay` for `Screen`, `Validator` for `Handler`).

## Magic values & configuration
- Require named constants for numeric, string, and boolean literals in **production** function bodies; exempt `0`, `1`, `-1`, empty string, and `True`/`False` where the meaning is obvious.
- **Test files are exempt** — inline literals in test functions and test-local constants are allowed.
- Treat structural fragments inside f-strings (paths, URLs, query patterns, regex) as magic values in production code; require extraction to a named constant.
- Require `UPPER_SNAKE_CASE` constants in **production code** to live in `config/` (`config/timing.py`, `config/constants.py`, `config/selectors.py`); flag definitions located elsewhere unless the file path matches one of these exemptions. Treat paths as case-insensitive, normalize backslashes to forward slashes, then check whether each pattern below appears anywhere in the path as a substring:
  - Django migrations: path contains `/migrations/`
  - Workflow registries: path contains the substring `/workflow/`, `_tab.py`, `/states.py`, or `/modules.py` (a file named literally `states.py` at repo root is not exempt; `pkg/states.py` is)
  - Test files: path or filename matches common test layout signals (`test_`, `_test.`, `.spec.`, `conftest`, `/tests/`, etc.); test files may define local constants without using `config/`
- Require a search of existing `config/` files for reuse before adding any new production constant.

### File-Global Constants

This rule extends the `constants-location` rule defined in `~/.claude/docs/CODE_RULES.md` — see the ⚡ HOOK-ENFORCED RULES table, Constants location row.

**file_global_constants_use_count:** Require every file-global constant (a module-level named constant declared at the top of a file (for example, an `UPPER_SNAKE_CASE` value assigned at module scope)) in **production code outside `config/`** to be referenced by at least two methods, functions, or classes in the same file — a reference counts only when the constant is actually consumed (compared, used in a decision, or passed into code that depends on its value), not when a method merely re-exports it (one class counts as a single reference regardless of how many methods inside it use the constant). Module-level usages outside any function, method, or class body also count as a reference. A default parameter value counts as one reference from the enclosing function. A constant used by exactly one method or class must have its value moved to `config/`, imported from `config/` at module scope, then bind a local alias inside the consuming method (or, when the sole consumer is a class, as a class attribute at class scope), OR inlined as a local constant inside the consuming method provided the value does not reintroduce a literal the magic-values rule would flag. When the sole reference is a module-level expression (for example, `ALL_ITEMS = build_registry(BATCH_SIZE)` at module scope), move the value to `config/` and reference the imported name directly at module scope; no local alias is needed.

**Decision table:**
- 0 references: dead code — remove the constant.
- 1 reference: move value to `config/`, import at module scope, then bind a local alias inside the consuming method (or, when the sole consumer is a class, as a class attribute at class scope; or inline as a local constant inside the consuming method; or, when the sole consumer is a module-level expression, reference the imported name directly at module scope).
- 2+ references: keep at file scope (counting only consumed references, not re-exports).

**Test files are exempt.** Test-file detection uses the following anchored patterns against the full relative path: filename matches `test_*.py`; filename matches `*_test.py`; filename matches `*.test.*`; filename matches `*.spec.*`; filename is `conftest.py`; path contains the segment `/tests/`.

**`config/` files are exempt.** Constants placed in `config/` satisfy the constants-location rule regardless of reference count.

Flag (single method references the file-global constant — move it inside the method):

```python
MAXIMUM_RETRIES = 3

def fetch_with_retries(url: str) -> str:
    for each_attempt_index in range(MAXIMUM_RETRIES):
        ...
```

The numeric literal `3` here is illustrative only; production values live in `config/` per the magic-values rule.

Accept (constant declared locally when only one method uses it):

The local form may bind its value to something sourced from config (an import, a function argument, or another already-named constant), OR inline as a local constant inside the consuming method — either path is acceptable. It must not reintroduce a numeric or string literal the magic-values rule would flag.

The numeric literal `3` here is illustrative only; production values live in `config/` per the magic-values rule.

The original file-scope `MAXIMUM_RETRIES = ...` declaration is removed when the value moves to `config/`.

```python
from config.timing import MAXIMUM_RETRIES

def fetch_with_retries(url: str) -> str:
    maximum_retries = MAXIMUM_RETRIES
    for each_attempt_index in range(maximum_retries):
        ...
```

Flag (zero references — dead code, remove):

A file-global constant with zero references is dead code; remove it rather than migrate it to a local.

Accept (constant kept at file scope when two or more methods reference it):

A reference counts only when the constant is actually consumed — compared, used in a decision, or passed into code that depends on its value — not when a method merely re-exports it.

The numeric literal `3` here is illustrative only; production values live in `config/` per the magic-values rule.

```python
MAXIMUM_RETRIES = 3

def fetch_with_retries(url: str) -> str:
    for each_attempt_index in range(MAXIMUM_RETRIES):
        ...

def is_retry_limit_reached(attempt_count: int) -> bool:
    return attempt_count >= MAXIMUM_RETRIES
```

## Types
- Require type hints on all function parameters and return values; flag missing hints.
- Flag `Any`, `any`, and `# type: ignore` when the diff lacks a justifying note.
- Flag bare `object` used as an escape hatch in place of a proper type.

## Structure
- File length is an advisory smell signal only, not a hard gate by itself: note files above ~400 lines as a soft concern and files above ~1000 lines as a stronger concern. Long files are acceptable when the file's role justifies it (migrations, generated code, registries, large fixtures).
- Flag functions longer than 30 lines.
- Require top-level function spacing to follow the language and existing file convention; for Python, require the standard 2 blank lines between top-level functions, and do not flag 1-vs-2 blank-line differences in other file types unless the surrounding file clearly establishes a convention.
- Require all `import` statements at the top of the file; flag imports inside function bodies.
- Require logging calls for application/runtime output; flag `print()` there, but allow `print()` in CLI tools and automation entrypoints when stdout is the integration contract (for example `print(json.dumps(...))`).
- Require `%`-style arguments inside `log_*` / `logger.*` calls (`logger.info("msg %s", value)`); flag f-strings inside logging calls.

## Design
- Favor functions over classes when state is absent; favor concrete classes over abstract base classes for single implementations; flag dependency-injection frameworks, single-type factories, and multi-level inheritance hierarchies.
- Add optional parameters only when a caller actually varies the value (YAGNI).
- Require construction logic (paths, URLs, formatting, transformations) to live inside model methods; flag the same string-building pattern duplicated across call sites.
- Require self-contained components: each component owns its own state, modals, overlays, and toasts; parents render `<Child />` alone.
- Reuse in-scope data; flag redundant fetches of the same record.
- Require a `TODO:` comment on scaffolding or placeholder code explaining what replaces it and why.

## Tests
- Require a paired test in the same PR for every new production code path (BDD: agree behaviors first, then failing specification before production code).
- Require mocks to include every field the code under test reads; flag partial mocks.
- Flag tests that only assert a constant equals itself or that a symbol exists.

## Scope of review
- Apply these rules only to lines the PR adds or modifies; leave unrelated code alone.
