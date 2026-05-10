---
name: code
description: >-
  Prepends strict code standards to every implementation session. Enforces
  strong typing, no Any, no casts, no type: ignore, treated-as-immutable
  TypedDicts, 100% test coverage, DRY, no mocks, no stubs, no fallbacks, and
  proper module structure. Triggers: /code, code standards, strict code, enforce
  standards, implement with standards.
---

# Code Standards Enforcer

Prepends these standards to every implementation session. Every criterion is binary — pass or fail. No partial credit.

## When this applies

Invoke at the start of any implementation task. The standards persist for the entire session.

**Refusal cases — first match wins:**

- **Not an implementation task.** "This skill applies to code implementation. Ask me to implement something specific."
- **Exploratory research or planning.** "Code standards are for implementation. Use /anthropic-plan for planning, then invoke /code when implementing."

## Gotchas

- **`make check` must run from pwsh, not bash.** The Bash tool routes through Git Bash on Windows, where `make` may not be on PATH. Always use `pwsh -NoProfile -Command 'make check 2>&1 | Select-Object -Last 100; exit $LASTEXITCODE'` so the pipeline does not mask a non-zero exit code from make.
- **`New-Item`, `Get-ChildItem`, `Remove-Item` are pwsh cmdlets.** Don't use them inside Bash tool calls. Use the PowerShell tool or prefix with `pwsh -NoProfile -Command`.
- **`TypedDict` encode/decode must be manual.** Pydantic and similar frameworks bypass the strict validation pattern. Write `_encode_*` and `_decode_*` functions by hand.
- **`_test_hooks.py` is per-module, not per-package.** Every module that has dependencies needs its own hooks file. A single `conftest.py` with mocks does not satisfy this rule.
- **Protocol must match the real API exactly.** If the real class has `async def fetch(self, key: str) -> bytes`, the Protocol must declare the same signature. A mismatch is caught at type-check time by mypy strict mode.

---

## Completion criteria

Every criterion below must be met before the change is complete.

### 1. Typing strictness

Zero violations across the project's source, test, and script directories (adapt `src/`, `tests/`, `scripts/` to the project's actual layout):

- No `Any`, `cast()`, `# type: ignore`, `# noqa`.
- No `.pyi` files, stubs, or shims.
- Mypy strict mode exits 0 with no errors.
- All TypedDicts are treated as immutable after construction and carry explicit `_encode_*` / `_decode_*` functions.
- All decode functions call `require_*` validation on every field.
- Internal encoder is typed — no untyped dict intermediaries.

### 2. Error handling

- No `try`/`except` in core logic that recovers, softens, or best-efforts a failure.
- Failures propagate. Callers decide whether to handle.
- APIs signal failure points through naming, docstrings, and test expectations — not by catching.

### 3. Test coverage

- Test runner exits 0 with full statement and branch coverage (e.g. `pytest -n auto --cov --cov-branch --cov-report=term-missing` with paths adapted to the project layout) (requires pytest-xdist and pytest-cov).
- Statement coverage: 100%. Branch coverage: 100%.
- Zero mocks. Every test exercises actual code paths through fakes injected via DI hooks (see criterion 4).
- Zero weak assertions. Every assert checks a specific, falsifiable property.
- Zero fake tests (tests that pass without validating behavior).

### 4. Dependency injection

- Every module that has external dependencies provides a `_test_hooks.py` with internal DI hooks (underscore = private). The hook file lives alongside the module it services.
- A shared testing utility module exports public test helpers for consumers (adapt the path to the project's conventions, e.g. `Libs/testing.py`).
- Production code sets hooks to real implementations at startup. Tests set them to fakes.
- No `if`/`else` branching on test vs. production — call the hook directly.

### 5. Codebase standards

- DRY: zero duplicate function bodies longer than 3 lines. Zero duplicate constant definitions.
- No placeholder code, no dead code, no commented-out blocks.
- No fallback paths, no back-compat shims, no legacy code.
- No `TypeAlias`, no `TYPE_CHECKING` import guards.

### 6. TypedDict protocol

- Every TypedDict has a paired `_encode_*` and `_decode_*` function.
- Every decode calls `require_*` (non-null, type-check, range-check) on every field before returning.
- Decode functions are the single point where untyped data becomes typed.

### 7. Redis boundary

- Use module-level helper functions or a Protocol.
- Never reference `Redis[Any]` in type annotations.

### 8. TOML boundary

- No `TYPE_CHECKING` guard for TOML types.
- Parse untyped dicts from TOML, then convert into TypedDict (no dataclasses) before use.

### 9. JSON recursive types

- Bypass framework validation (e.g., Pydantic).
- Parse with `json.loads()`, validate immediately with internal `_decode_*` / `_load_json_*` functions before any other use.

### 10. ASGI / framework boundaries

- Define a Protocol for the minimal interface (e.g., `async def body() -> bytes`).
- Never use `dict[str, Any]` in ASGI scopes.
- Parse at the edge, validate immediately, propagate as strict types.

### 11. Dynamic import pattern

When using `importlib.import_module()` + `getattr()`, the intermediate variables are untyped. Bind the final instance through a typed wrapper so the result carries a concrete type rather than `Any`:

```python
import importlib
from collections.abc import Callable

mod = importlib.import_module("module_name")
cls = getattr(mod, "ClassName")

def _construct(klass: Callable[..., TheProtocol]) -> TheProtocol:
    return klass()

instance = _construct(cls)
```

### 12. Documentation

Google-style docstrings on every public function, method, and class:

```python
def load_config(config_path: str) -> AppConfig:
    """Load and validate the application configuration from disk.

    Args:
        config_path: Absolute path to the TOML configuration file.

    Returns:
        A fully validated AppConfig TypedDict.

    Raises:
        FileNotFoundError: If config_path does not exist.
        ValidationError: If the parsed config fails require_* checks.
    """
```

### 13. Build infrastructure

The project under development must contain:

- `Makefile` with targets: `check`, `lint`, `test`, `coverage`.
- `pyproject.toml` with `[tool.mypy]` strict mode, `[tool.pytest.ini_options]` with `addopts = -n auto` (requires pytest-xdist).
- A lint guard script that covers the project's source, test, and script directories.

### 14. Lint gates

- `make lint` runs mypy (strict), ruff, and the project's guard script.
- All linters cover the project's source, test, and script directories.
- `make lint` exits 0 before `make test` is valid.

### 15. Protocol signature match

- Every Protocol's method signatures match the real API they abstract.
- If the real API changes, the Protocol fails type-checking — no silent drift.

### 16. Auth, credentials, multi-tenancy

- Auth and credential handling is explicit, typed, and testable.
- Multi-tenant DB access uses typed connection factories, not string-formatted queries.
- MCP-shared resources follow the same strictness as application code.

---

## Verification

Each criterion returns either **at least one finding** OR **exactly one proof-of-absence** with at least 3 adversarial probes specific to that criterion. A criterion returning neither is a protocol gap.

## File index

| File | Purpose |
|------|---------|
| `SKILL.md` | Hub — binary criteria, gotchas, when-to-apply, verification protocol |
