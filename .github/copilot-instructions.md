# Code Review Instructions for LLMs

Review every change against these rules. Flag each violation with its rule name. Treat rules as mandatory standards; honor file-level exception markers where they appear.

## Comments
- Flag every new inline comment (`#` or `//`) added to modified **production** code; require self-documenting names.
- Preserve every existing comment as-is; treat comments in the surrounding file as sacred.
- Allow docstrings on new functions, methods, classes, or modules (including module-level docstrings).
- **Test files (`test_*.py`, `*_test.py`, `*.test.*`, `*.spec.*`) are fully exempt** — comments and docstrings inside test functions are allowed.
- Exempt markers: shebangs, `# type:`, `# noqa`, `// eslint-...`.

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

## Magic values and configuration
- Require named constants for numeric, string, and boolean literals in **production** function bodies; exempt `0`, `1`, `-1`, empty string, and `True`/`False` where the meaning is obvious.
- **Test files are exempt** — inline literals in test functions and test-local constants are allowed.
- Treat structural fragments inside f-strings (paths, URLs, query patterns, regex) as magic values in production code; require extraction to a named constant.
- Require `UPPER_SNAKE_CASE` constants in **production code** to live in `config/` (`config/timing.py`, `config/constants.py`, `config/selectors.py`); flag definitions located elsewhere. Test files may define local constants without using `config/`.
- Require a search of existing `config/` files for reuse before adding any new production constant.

## Types
- Require type hints on all function parameters and return values; flag missing hints.
- Flag `Any`, `any`, and `# type: ignore` when the diff lacks a justifying note.

## Structure
- Flag files over 1000 lines; note files over 400 lines as a soft smell.
- Flag functions longer than 30 lines.
- Require top-level function spacing to follow the language and existing file convention; for Python, require the standard 2 blank lines between top-level functions, and do not flag 1-vs-2 blank-line differences in other file types unless the surrounding file clearly establishes a convention.
- Require all `import` statements at the top of the file; flag imports inside function bodies.
- Require logging calls for application/runtime output; flag `print()` there, but allow `print()` in hook entrypoints and CLI tools when stdout is the integration contract (for example `print(json.dumps(...))`).
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
