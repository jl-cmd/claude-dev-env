---
paths: **/*.py
---

# File-Global Constants

This rule extends the `constants-location` rule defined in `~/.claude/docs/CODE_RULES.md` — see the ⚡ HOOK-ENFORCED RULES table, Constants location row.

**file_global_constants_use_count:** A file-global constant is a module-level named constant declared at the top of a file (for example, an `UPPER_SNAKE_CASE` value assigned at module scope). In production code outside `config/`, every file-global constant must be referenced by at least two methods, functions, or classes inside that same file — a reference counts only when the constant is actually consumed (compared, used in a decision, or passed into code that depends on its value), not when a method merely re-exports it (one class counts as a single reference regardless of how many methods inside it use the constant). Module-level usages outside any function, method, or class body also count as a reference. A default parameter value counts as one reference from the enclosing function. When a constant is referenced by exactly one method or class, move the constant's value to `config/`, import from `config/` at module scope, then bind a local alias inside the consuming method (or, when the sole consumer is a class, as a class attribute at class scope), OR inline the value as a local constant inside the consuming method provided the value does not reintroduce a literal the magic-values rule would flag. When the sole reference is a module-level expression (for example, `ALL_ITEMS = build_registry(BATCH_SIZE)` at module scope), move the value to `config/` and reference the imported name directly at module scope; no local alias is needed.

## Decision table

- 0 references: dead code — remove the constant.
- 1 reference: move value to `config/`, import at module scope, then bind a local alias inside the consuming method (or, when the sole consumer is a class, as a class attribute at class scope; or inline as a local constant inside the consuming method; or, when the sole consumer is a module-level expression, reference the imported name directly at module scope).
- 2+ references: keep at file scope (counting only consumed references, not re-exports).

## Test files are exempt

Test-file detection uses the following anchored patterns against the full relative path: filename matches `test_*.py`; filename matches `*_test.py`; filename matches `*.test.*`; filename matches `*.spec.*`; filename is `conftest.py`; path contains the segment `/tests/`.

## `config/` files are exempt

Constants placed in `config/` satisfy the constants-location rule; the use-count requirement applies only to production code outside `config/`.

## Examples

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
