# Code rules for Claude, Cursor BugBot, Copilot, and other agents

This file is the **canonical** code-rules instruction set for every AI coding agent that reads `AGENTS.md` or `.cursor/BUGBOT.md` in this repository:

- **Claude** (Claude Code memory and review)
- **Cursor BugBot** (PR review)
- **GitHub Copilot** (chat, code review, and code generation)
- Any other coding agent that loads `AGENTS.md` at session start

Use these rules when writing new code, when modifying existing code, and when reviewing pull requests. Apply the rules to the **lines a change adds or modifies**; leave unrelated lines as they are.

When a rule lists exemptions (test files, migrations, config files), honor them. When a rule shows a before/after pair, treat the "after" form as the green-light pattern.

---

## Code rules

### Comments

- Use self-documenting names in modified **production** code so the diff carries no new `#` or `//` comments.
- Preserve every existing comment exactly as written; treat comments in the surrounding file as sacred.
- Use docstrings on new functions, methods, classes, and modules (including module-level docstrings).
- **Test files (`test_*.py`, `*_test.py`, `*.test.*`, `*.spec.*`, `conftest.py`) are fully exempt** — write inline comments and docstrings inside test functions whenever they help.
- Keep these directive markers as-is whenever they appear: shebangs, `# type:`, `# noqa`, `# pylint:`, `# pragma:`, `// @ts-...`, `// eslint-...`, `// prettier-...`, and `/// ` triple-slash reference directives.

### Naming

- Use full-word identifiers in place of common abbreviations: `ctx → context`, `cfg → configuration`, `msg → message`, `btn → button`, `idx → index`, `cnt → count`, `elem → element`, `val → value`, `tmp → temporary_value`.
- Use single-letter loop variables only for `i`, `j`, `k`, and use `e` for caught exceptions; use the `each_` prefix on every other loop variable (`each_order`, `each_user`).
- Prefix booleans with `is_`, `has_`, `should_`, or `can_` (`is_ready`, `has_payload`, `should_retry`, `can_skip`).
- Prefix collection names with `all_` (`all_orders`, `all_pending_jobs`).
- Name maps with the `X_by_Y` pattern (`price_by_product`, `user_by_id`).
- Name parameters with prepositions when they describe direction or source: `from_path=`, `to=`, `into=`.
- Replace generic placeholder identifiers (`result`, `data`, `output`, `response`, `value`, `item`, `temp`) with names that describe the domain meaning: `parsed_invoice`, `pending_orders`, `cached_lookup`, etc.
- Replace generic function-name prefixes (`handle_`, `process_`, `manage_`, `do_`) with the specific verb that describes what the function does: `parse_invoice`, `dispatch_event`, `migrate_schema`.
- Name components for what they are — choose the descriptive name over the generic placeholder: `Overlay` over `Screen`, `Validator` over `Handler`, `InvoicePreview` over `Wrapper`.

### Magic values & configuration

- Replace numeric, string, and boolean literals in **production** function bodies with named constants. Inline literals stay acceptable for `0`, `1`, `-1`, the empty string, and `True`/`False` when the meaning is obvious.
- **Test files are exempt** — write literal values inline in test functions and define test-local constants where they help.
- Treat structural fragments inside f-strings (paths, URLs, query patterns, regex) as magic values in production code; extract each fragment to a named constant.
- Place `UPPER_SNAKE_CASE` constants used in **production code** under `config/` (`config/timing.py`, `config/constants.py`, `config/selectors.py`). Honor these path exemptions: treat paths as case-insensitive, normalize backslashes to forward slashes, then check whether each pattern below appears anywhere in the path as a substring:
  - Django migrations: path contains `/migrations/`
  - Workflow registries: path contains the substring `/workflow/`, `_tab.py`, `/states.py`, or `/modules.py` (the exemption requires the workflow segment in the path, so `pkg/states.py` qualifies while a top-level `states.py` follows the standard `config/` rule)
  - Test files: path or filename matches common test layout signals (`test_`, `_test.`, `.spec.`, `conftest`, `/tests/`); test files may define local constants without using `config/`
- Search existing `config/` files for a reusable constant before adding a new one.

#### File-global constants

For every file-global constant declared at module scope in **production code outside `config/`** (for example, an `UPPER_SNAKE_CASE` value at the top of a file), count how many methods, functions, or classes in the same file actually consume it. A reference counts when the constant is compared, used in a decision, or passed into code that depends on its value; re-export references (where the method merely surfaces the value without comparing, deciding on, or passing it to dependent code) fall outside the count. One class counts as a single reference regardless of how many methods inside it use the constant. A module-level expression that consumes the constant counts as one reference, and a default parameter value counts as one reference from the enclosing function.

Apply this decision table:

- **0 references:** the constant is dead code. Remove it.
- **1 reference:** move the value to `config/`, import it at module scope, and bind a local alias inside the consuming method (or, when the sole consumer is a class, declare it as a class attribute at class scope; or inline it as a local constant inside the consuming method; or, when the sole consumer is a module-level expression, reference the imported name directly at module scope). Source the local form's value from `config/`, a function argument, or another already-named constant so it stays free of the literals the magic-values rule covers.
- **2+ references:** keep the constant at file scope.

**Test files are exempt.** Test-file detection uses these anchored patterns against the full relative path: filename matches `test_*.py`; filename matches `*_test.py`; filename matches `*.test.*`; filename matches `*.spec.*`; filename is `conftest.py`; path contains the segment `/tests/`.

**`config/` files are exempt.** Constants placed in `config/` satisfy this rule regardless of reference count.

Move the constant into the consuming method when only one method uses it (the numeric `3` here is illustrative; production values live in `config/`):

```python
# Before — one method uses MAXIMUM_RETRIES; move the value into the method's scope
MAXIMUM_RETRIES = 3

def fetch_with_retries(url: str) -> str:
    for each_attempt_index in range(MAXIMUM_RETRIES):
        ...
```

```python
# After — value lives in config/, alias inside the consuming method
from config.timing import MAXIMUM_RETRIES

def fetch_with_retries(url: str) -> str:
    maximum_retries = MAXIMUM_RETRIES
    for each_attempt_index in range(maximum_retries):
        ...
```

Keep the constant at file scope when two or more methods consume it:

```python
MAXIMUM_RETRIES = 3

def fetch_with_retries(url: str) -> str:
    for each_attempt_index in range(MAXIMUM_RETRIES):
        ...

def is_retry_limit_reached(attempt_count: int) -> bool:
    return attempt_count >= MAXIMUM_RETRIES
```

### Types

- Annotate every function parameter and return value with a type hint.
- Reach for a precise type first. When `Any`, `any`, or `# type: ignore` is genuinely the right tool, leave a one-line note in the diff explaining the constraint.
- Use a concrete type that captures the value's actual shape, even when bare `object` would compile.

### Structure

- Treat file length as an advisory signal: emit a stderr note above ~400 lines and a stronger stderr note above ~1000 lines, while letting the file's role justify the length (migrations, generated code, registries, and large fixtures stay acceptable at any size).
- Keep functions at 30 lines or fewer.
- Match the language's blank-line convention between top-level functions; for Python, separate top-level functions with two blank lines. Leave 1-vs-2 blank-line differences in other languages alone unless the surrounding file clearly establishes a convention.
- Place every `import` statement at the top of the file. Move imports out of function bodies into the module-level import block.
- Use logging calls for application and runtime output. CLI tools and automation entrypoints may use `print()` when stdout is the integration contract (for example `print(json.dumps(...))`).
- Pass log arguments with `%`-style placeholders inside `log_*` and `logger.*` calls (`logger.info("delivered %s", message_id)`). Build the format string outside the call only when you need conditional formatting before the call site.

### Design

- Reach for functions when no state is involved. Reach for concrete classes when state is involved and only one implementation exists. Reach for an abstract base class, dependency-injection framework, or factory only when two or more concrete implementations already exist or are imminent.
- Apply Single Responsibility (SOLID **S**) per change reason: one reason to change per function, class, or module. Keep cohesive code together — a cohesive 80-line class stays as one class rather than splitting into four 20-line classes for line-count aesthetics.
- Apply Open/Closed, Liskov Substitution, Interface Segregation, and Dependency Inversion (SOLID **O / L / I / D**) only when two or more concrete implementations already exist or are imminent. Defer new interfaces, ABCs, abstract factories, and dependency-injection scaffolding until that bar is met.
- Add an optional parameter the moment a caller actually varies the value (YAGNI).
- Place construction logic (paths, URLs, formatting, transformations) inside the model or service that owns the data. When you see the same string-building pattern at two call sites, extract it into a method on the owning model.
- Build self-contained components: each component owns its own state, modals, overlays, and toasts; parents render `<Child />` alone.
- Reuse data already in scope; pass the existing record to the function that needs it.
- Mark scaffolding or placeholder code with a `TODO:` comment that names what replaces it and why.

### Tests

- Write one test for every new production code path in the same PR (BDD: agree the behavior first, write the failing specification, then write the production code that makes it pass).
- Mock every field the code under test reads. When a mock object stands in for a record, populate every attribute the code path touches.
- Write assertions that exercise behavior. Replace tautologies (`assert CONSTANT == CONSTANT`, `assert hasattr(module, "name")`) with assertions that would fail if the implementation regressed.

### Scope of review

- Apply every rule above to the **lines a PR adds or modifies**. Leave unrelated lines alone.
- For new files, apply the rules to every line in the file.
- When tooling reports a violation outside the changed lines, surface it as a non-blocking advisory.
