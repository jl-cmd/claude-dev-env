# Code Rules Reference

Compact reference for agents. Hook-enforced rules marked with ⚡.

---

## COMMENT PRESERVATION (ABSOLUTE RULE)

**NEVER remove existing comments.** If you are not adding or removing code on a line, do not touch its comments.

- Existing comments are SACRED — never delete, rewrite, or "clean up" existing comments
- New inline comments are not needed — write self-documenting code instead
- Module-level docstrings are allowed in all files
- Docstrings for new files/methods/classes are allowed
- **Test files are exempt:** comments and docstrings inside test functions are allowed
- The hook enforces BOTH directions: blocks new inline comments AND blocks deletion of existing comments

**Scope:** Only evaluate comments on lines YOU are actively changing. If code is untouched, its comments are untouched.

---

## CORE PRINCIPLES

### Self-Documenting Code
New code explains itself through naming. Do not add new inline comments — use descriptive names instead. Docstrings on functions/methods/classes are allowed.

> **Full readability standard:** `~/.claude/skills/readability-review/SKILL.md` — 8-dimension rubric (naming, SRP, abstraction, control flow, domain language, call sites, state clarity, visual rhythm). Run `/check` for parallel team review or `/readability-review` standalone.

### Centralized Configuration
One source of truth. Every constant lives in ONE place (`config/`).

### Reuse Before Create
Search first. Import second. Create last.

### Encapsulation Enables Cleaner Naming
Expose constants via helper functions: `isMaxLevel(level)` > `level >= MAXIMUM_LEVEL`

---

## ⚡ HOOK-ENFORCED RULES

These rules are automatically enforced by `code_rules_enforcer.py`. Violations block Write/Edit.

| Rule | What's Checked |
|------|----------------|
| No NEW comments | `#` / `//` in new production code only (existing comments NEVER removed; exempt markers: shebangs, `# type:`, `# noqa`, `# pylint:`, `# pragma:`, `// @ts-`, `// eslint-`, `// prettier-`, `/// `; docstrings and module docstrings are always allowed; all test files are exempt) |
| Imports at top | No `import` inside function bodies |
| Logging format args | No `log_*(f"...")` - use `log_*("...", arg)` |
| File line count | Advisory only — see [File length guidance](#65-file-length-guidance) |
| Magic values | No literals in production function bodies (0, 1, -1 exempt). **Test files exempt.** Includes string templates — if you strip the interpolations from an f-string and the remaining literal text is structural (paths, URLs, patterns), those fragments are magic values that belong in config |
| Constants location | No `UPPER_SNAKE =` outside `config/` in **production code**. **Test files may define local constants.** |
| Hardcoded user paths | No string literals naming a specific user's home directory in production code (`C:/Users/jon/...`, `/Users/alice/...`, `/home/bob/...`). Use `pathlib.Path.home()` or `os.path.expanduser('~')`. **Exempt:** test files, `config/` files, workflow registry paths (`/workflow/`, `_tab.py`, `/states.py`, `/modules.py`), Django migrations (`/migrations/`), and hook infrastructure (the enforcer embeds path patterns and must not self-block). |
| sys.path.insert dedup | `sys.path.insert(0, X)` must be guarded by `if X not in sys.path:` (or equivalent membership test) so reloads do not push the same entry repeatedly. **Test files exempt.** |
| Unused module-level imports | Module-level imports never referenced in the file body are flagged. Skipped for files declaring `__all__` (re-exports), files using `TYPE_CHECKING` (annotation-only imports), and lines marked `# noqa`. **Test files exempt.** |
| Banned identifiers | Single-letter or 2–4 char abbreviations in production code: `ctx`, `cfg`, `msg`, `btn`, `idx`, `cnt`, `tmp`, `elem`, `val`. Test files exempt; loop counters `i`/`j`/`k` and exception `e` exempt. See §5 for the full list and rationale. |
| Banned function prefixes | Function names starting with `handle_`, `process_`, `manage_`, or `do_` are flagged — these prefixes describe nothing about behavior. Name functions after the noun they produce or the verb they perform (`fetch_user`, `validate_payload`). **Test files exempt.** |
| Type escape hatches | `from typing import Any`, `cast()`, and inline `Any` in production are flagged outside boundary files (`__init__.py`, `protocols.py`, `types.py`, `conftest.py`). Name the concrete shape instead. |
| Bare except | `except:` and `except BaseException:` swallow KeyboardInterrupt/SystemExit; `except Exception:` hides bugs by catching nearly every error class. Name the specific exception(s) you intend to catch (tuple form `except (ValueError, KeyError):` is fine). **Test files and hook infrastructure exempt.** |
| Boundary types — Any in signatures | `Any` appearing directly or nested inside a generic in a function signature (parameters, return type) or class attribute annotation is flagged. Local variable annotations are exempt. Files named `protocols.py` or `types.py` are interface-declaration surfaces and exempt. |
| Stub implementations | Functions whose body is `pass`, `...`, or `raise NotImplementedError` in production code are flagged unless declared abstract (`@abstractmethod`) or part of a `Protocol`. Implement the function or remove it. |
| TypedDict encode/decode pairs | Every `class FooPayload(TypedDict):` in production code must have companion `_encode_foo_payload(...)` and `_decode_foo_payload(...)` functions in the same module — boundary serialization should not leak to callers. |
| Test-mode branching in production | Reading `TESTING`, `PYTEST_CURRENT_TEST`, `IS_TEST`, etc. from production code creates two parallel implementations. Use dependency injection so production stays single-path. **Test files and hook infrastructure exempt.** |
| Thin wrapper files | A non-`__init__.py` module whose body is only imports (optionally with an `__all__` assignment) is a re-export indirection with no payload. Callers should import from the real module. `__init__.py` is the canonical re-export surface and is exempt. |
| Docstring format (Google-style) | Public functions/methods (no leading underscore, not dunder, body > 3 lines, not `@property`/`@abstractmethod`) require Google-style `Args:` / `Returns:` (or `Yields:`) / `Raises:` sections matching the signature. **Test files exempt.** |

### Where UPPER_SNAKE is allowed

The "Constants location" rule is enforced at Write time. The hook exempts these path families where UPPER_SNAKE identifiers are either the canonical home or the native convention rather than misplaced scalar constants:

| Path pattern | Why it is exempt |
|---|---|
| `config/*` | Canonical home for scalar constants. |
| `/migrations/` (Django migrations) | Migration files are self-contained by framework convention; their UPPER_SNAKE identifiers are operation names, not misplaced configuration. |
| `/workflow/`, `_tab.py`, `/states.py`, `/modules.py` (path normalized to forward slashes, matched as substrings) | Workflow state and module registries declare `StateDefinition` / `WorkflowModule` instances as module-level singletons using UPPER_SNAKE names. These are registry entries, not constants to hoist. |
| Test files (`test_*.py`, `*_test.py`, `*.spec.*`, `conftest.py`, paths under `/tests/`) | Test files may define local constants without using `config/`. |

Any production file outside these families that defines an UPPER_SNAKE at module scope is still flagged and must be moved to `config/`.

> See also: [File-global constants use-count rule](../rules/file-global-constants.md) for the use-count requirement on file-global constants outside `config/`.

---

## 3. REUSE CONSTANTS (DRY CONFIG)

**Before writing ANY constant:**

```bash
# Find config files
# Search your project for existing config files before creating new ones

# Search for value
grep -r "VALUE" config/
```

**Decision tree:**
1. Search exact value → Found? → IMPORT IT
2. Search semantic match → Found? → USE EXISTING NAME
3. Config file exists? → ADD TO EXISTING
4. Create new (rare)

---

## 4. CONFIG LOCATIONS

| Constant Type | Location |
|---------------|----------|
| Timeouts, delays, retries | `config/timing.py` |
| Ports, URLs, thresholds | `config/constants.py` |
| CSS selectors | `config/selectors.py` |

---

## 5. NO ABBREVIATIONS

Full words only. No mental translation.

| Bad | Good |
|-----|------|
| `ctx`, `cfg`, `msg` | `context`, `configuration`, `message` |
| `btn`, `idx`, `cnt` | `button`, `index`, `count` |
| `tmp`, `elem`, `val` | `temporary_value`, `element`, `value` |

**Exception:** `i`, `j`, `k` in loops; `e` for exception.

**Extended naming rules** :
- Loop vars: `each_order`, `each_user` (prefix `each_`)
- Booleans: `is_valid`, `has_permission`, `should_retry` (prefix `is_`/`has_`/`should_`/`can_`)
- Collections: `all_orders`, `all_users` (prefix `all_`)
- Maps: `price_by_product`, `user_by_id` (pattern `X_by_Y`)
- Preposition params: `from_path=`, `to=`, `into=`
- **Banned names:** `result`, `data`, `output`, `response`, `value`, `item`, `temp`
- **Banned prefixes:** `handle`, `process`, `manage`, `do`

---

## 6. COMPLETE TYPE HINTS

```python
def function_name(
    parameter: str,
    optional: Optional[str] = None,
) -> ReturnType:
```

- ALL parameters typed
- ALL returns typed
- No `Any` type
- No `# type: ignore`

*(Also enforced by mypy_validator.py hook)*

---

## 6.5 FILE LENGTH GUIDANCE

File length is a **smell signal, not a hard threshold**. Long files often hide multiple responsibilities, but legitimately long files exist (migrations, generated code, registries, fixtures). The hook surfaces advisories instead of blocking.

**Two advisory thresholds (non-blocking, stderr only):**

| Threshold | Source basis | Hook behavior |
|-----------|--------------|---------------|
| `>= 400` lines | Robert C. Martin, *Clean Code* (2008), Ch. 5 "Formatting" — small files preferred; Martin Fowler, *Refactoring* — "Large Class" code smell | Soft advisory: "consider splitting" |
| `>= 1000` lines | pylint default `max-module-lines=1000`; SonarQube rule S104 default `1000` | Strong nudge: "exceeds widely-used static-analysis defaults" |

**What we deliberately reject:**

- **Hard numeric blocks** — Google's Python Style Guide imposes no file-length cap (only a ~40-line function review hint at https://google.github.io/styleguide/pyguide.html). A blocking rule produces false positives on legitimate cases.
- **A single magic number** — Different sources land at 200 (*Clean Code* preference), 750 (some SonarQube language profiles), or 1000 (pylint, Sonar Java). No source justifies a single universal cap.

**When to actually split:**

The size signal matters *because* of what it usually indicates: multiple responsibilities (Single Responsibility Principle — Robert C. Martin, *Agile Software Development*, 2002), poor cohesion (Steve McConnell, *Code Complete 2e*, 2004, Ch. 5–6), or the "Large Class" / "Long Function" smells (Fowler). Use the readability rubric (`~/.claude/skills/readability-review/SKILL.md`) when an advisory fires — split based on cohesion, not line count.

---

## 7. RIGHT-SIZED ENGINEERING

**Simple > Clever. Functions > Classes. Concrete > Abstract.**

Never: ABC for single impl, DI frameworks, factory for single type
Always: Functions when no state, concrete classes, simple imports

---

## 7.5 SOLID PRINCIPLES

**Apply where two or more concrete implementations already share a contract. For code with a single concretion, §7 (Right-Sized Engineering) takes precedence: use concrete classes, functions when no state, and direct imports.**

Reference: Robert C. Martin, *Agile Software Development: Principles, Patterns, and Practices* (2002), Ch. 8–12.

| Letter | Principle | What it means here |
|--------|-----------|--------------------|
| **S** | Single Responsibility Principle | A class, function, or module has one reason to change. One unit = one axis of variation. Ties to §6.5 (file length as smell signal) and Fowler's "Large Class" / "Long Function" smells. |
| **O** | Open/Closed Principle | Extend behavior by adding new code. Favor a new branch/handler/subclass over editing the same switch in five places. |
| **L** | Liskov Substitution Principle | A subtype must be usable anywhere its parent type is expected without surprising the caller. If a subclass override breaks caller assumptions, flatten the hierarchy or prefer composition. |
| **I** | Interface Segregation Principle | Each client depends on exactly the methods it calls. Split one fat interface into several role-specific ones so each caller imports only the role it needs. |
| **D** | Dependency Inversion Principle | When two or more concretions exist or are imminent, depend on the shared abstraction. With exactly one concretion, import the concrete type directly (see §7). |

### Reconciling SOLID with Right-Sized Engineering (§7)

SOLID was written for OO codebases where most abstract types have two or more concrete subclasses. In this codebase:

- **SRP always applies.** Functions, classes, and modules must have one reason to change regardless of paradigm. This is the only SOLID letter that applies immediately, without waiting for a second implementation.
- **OCP, LSP, ISP, DIP apply where two or more concrete implementations already share a contract.** A single concrete class satisfies SOLID by default. Introduce interfaces, ABCs, or DI containers only when the second concretion lands.
- **For code with fewer than two concretions, §7 wins:** concrete classes, functions when no state, direct imports. Refactor toward OCP/DIP at the commit that introduces the second concrete implementation (YAGNI).

### Signals that SOLID is being misapplied

- Creating an interface or ABC with exactly one implementation (violates §7 DIP guard)
- Splitting a cohesive 80-line class with one reason to change into four 20-line classes because "SRP" — SRP counts distinct change reasons; size is a separate signal tracked in §6.5
- Abstract factories for types that have exactly one concrete product
- Dependency-injection containers where every injected type has exactly one concrete implementation across production and tests

### When SOLID adds value

- Two or more concrete implementations already exist → DIP and ISP earn their keep
- A class shows multiple unrelated change reasons in git history → SRP split is justified
- Subclass overrides break caller assumptions → LSP violation; fix or flatten the hierarchy
- Editing the same `if`/`switch` block every time a new case is added → OCP refactor is justified

---

## 8. TDD PROCESS

1. **RED** - Failing test first
2. **GREEN** - Minimum code to pass
3. **REFACTOR** - Only if valuable

---

## 9. SELF-CONTAINED COMPONENTS

Components own their complete feature. Parents just render `<Child />`.

Child handles: state, modals, overlays, toasts
Parent knows: nothing about child's internals

---

## 9.5 NO THIN WRAPPER MODULES

A non-`__init__.py` module whose body is only imports (optionally with an `__all__` assignment) is a thin wrapper. Callers should import from the real module. The wrapper adds no payload — only an indirection layer that obscures where things live.

`__init__.py` is the canonical re-export surface and is exempt; package surface aggregation is its job.

---

## 9.6 NO BACKWARDS-COMPATIBILITY SHIMS

Removed code is removed. Do not leave behind:

- Renamed functions that re-export the old name with a `# deprecated` comment
- `_old_*` aliases pointing to the new implementation
- Wrapper modules whose only purpose is to keep an old import path alive
- `// removed in vX` comment markers next to deleted blocks

When a symbol moves or its signature changes, update the call sites in the same commit. The git log records what changed; the codebase records what exists now.

> **See also:** [`skills/code/SKILL.md`](../skills/code/SKILL.md) §5 ("No fallback paths, no back-compat shims, no legacy code") states the same principle as a session-start prompt directive. This section is the authoritative wording; the skill amplifies it for `/code` sessions.

---

## 9.7 NO FALLBACK / BEST-EFFORT WRAPPERS

Do not wrap a call in `try/except` that swallows the failure and returns a default unless the caller has explicitly opted in to that behavior at the boundary.

```python
# BAD — silently hides every failure mode
def fetch_user(user_id: int) -> User | None:
    try:
        return _registry[user_id]
    except Exception:
        return None
```

```python
# GOOD — names the specific failure and propagates the rest
def fetch_user(user_id: int) -> User | None:
    try:
        return _registry[user_id]
    except KeyError:
        return None
```

Fallback values mask programming errors (KeyError vs RuntimeError vs AttributeError all collapse to "None"), making debugging impossible. Production code names the specific failure mode it intends to handle.

> **See also:** [`skills/code/SKILL.md`](../skills/code/SKILL.md) §2 ("No `try`/`except` in core logic that recovers, softens, or best-efforts a failure") states the same principle as a session-start prompt directive. The hook check `check_bare_except` enforces the narrowest case (bare/`Exception`/`BaseException` handlers); this section + the `code` skill cover the broader "any swallowing handler" intent.

---

## 10. NO REDUNDANT DATA FETCHES

If you already have data, don't fetch again.

```typescript
// BAD
const profile = await getProfile();
const localProfile = await db.profile.first(); // same data!

// GOOD
const profile = await db.profile.first();
// ... use profile throughout ...
```

---

## 11. ENFORCEMENT SURFACES

Rules in this document are enforced through three distinct surfaces, each with different latency and reach. Knowing which surface owns a rule tells you what happens when you violate it.

| Surface | What it catches | When it runs | Failure mode |
|---------|-----------------|--------------|--------------|
| **⚡ Hook** | Pattern-matchable violations: comments, magic values, banned identifiers, bare except, boundary `Any`, thin wrappers, docstring shape, etc. | PreToolUse on Write/Edit (and PostToolUse advisories) | Blocks the write — Claude must fix and retry |
| **🤖 Prompt** | Judgment-driven principles: SRP, Right-Sized Engineering, KISS, conservative-action, BDD discovery; strict-mode standards via the `/code` skill (no `Any`/`cast`, immutable TypedDicts, DI hooks, 100% branch coverage, no fallback `try/except`) | Read into the model context at session start (CLAUDE.md, rules/*.md, skill prepends) | Influences Claude's decisions; no automatic block |
| **👥 Audit rubric** | Cross-file architectural concerns: SOLID misapplication, abstraction leaks, multi-file coupling | Run on demand via `/check`, `/readability-review`, agent-driven audits | Surfaces in audit output; humans decide whether to act |

### Prompt-enforced rules (no hook coverage)

These principles cannot be reduced to a regex or AST visitor. They live in user-private `~/.claude/rules/` and `~/.claude/CLAUDE.md`, and are read into context every session:

- **Right-Sized Engineering** — concrete classes for single concretions, functions when no state, no DI frameworks for solo-scale code
- **SRP / SOLID misapplication signals** — see §7.5
- **conservative-action** — when intent is ambiguous, ask before acting
- **explore-thoroughly** — investigate before committing to an approach
- **agent-spawn-protocol** — verify context before delegating to a subagent
- **`code` skill ([`skills/code/SKILL.md`](../skills/code/SKILL.md))** — invoked via `/code`, prepends strict-mode standards for the entire session: no `Any`/`cast()`/`# type: ignore`, immutable TypedDicts with manual `_encode_*`/`_decode_*` and `require_*` validation, per-module `_test_hooks.py` for DI, 100% statement + branch coverage, zero mocks. Several criteria overlap with §9.6/§9.7 and the ⚡ B-series checks; the skill is the canonical entry point when the user explicitly opts into strict mode for an implementation task.

### Audit-rubric reference

For multi-file architectural reviews see [`packages/claude-dev-env/audit-rubrics/`](../audit-rubrics/). Categories A–F, I, K stay as agent rubrics rather than ⚡ blocking rules because they require multi-file reasoning that single-file hooks cannot perform.

---

## 12. DEFERRED RULES (P1 — TRACKED, NOT ENFORCED)

The following rules are documented in `~/.claude/rules/` and applied by Claude through prompt context, but have no hook coverage in `code_rules_enforcer.py`. Promotion to ⚡ blocking enforcement is on the backlog and will land as separate hardening commits.

| Rule | Source | Promotion path |
|------|--------|----------------|
| Context7 before web search for library/SDK questions | [`rules/context7.md`](../rules/context7.md) | New PreToolUse hook on WebSearch when query mentions a library name |
| Verify-before-asking checklist | [`rules/verify-before-asking.md`](../rules/verify-before-asking.md) | Stop hook scanning AskUserQuestion calls for "where is", "what file", etc. |
| BDD naming (`should_…` / `describe…it…`) | [`rules/bdd.md`](../rules/bdd.md) | `code_rules_enforcer.py::check_test_naming` (new) — flag test functions starting with `test_` lacking corresponding `should_…` form |
| `gh` pagination requires `--paginate --slurp` plus external `jq` | [`rules/gh-paginate.md`](../rules/gh-paginate.md) | PreToolUse Bash hook matching `gh api .*/(reviews\|comments)` without `--paginate --slurp` |
| Self-contained documentation (no "as discussed", "Option A", session refs) | [`rules/self-contained-docs.md`](../rules/self-contained-docs.md) | PostToolUse Write hook scanning new `.md` content for conversational refs |
| Temp file cleanup at end of task | [`rules/cleanup-temp-files.md`](../rules/cleanup-temp-files.md) | Stop hook scanning for files Claude created and did not delete |
| No credentials committed to git | [`rules/git-workflow.md`](../rules/git-workflow.md) | PreToolUse Bash hook on `git commit` scanning staged diff for high-entropy strings, `.env` patterns, and known credential file extensions |
| Per-module DI hooks (`_test_hooks.py` sibling) instead of `if TESTING:` branching | [`skills/code/SKILL.md`](../skills/code/SKILL.md) §4 | New `check_test_hooks_sibling()` — when a module imports a side-effect dependency and a test exists, require a `<module>_test_hooks.py` sibling exposing the injection points |
| 100% statement + branch coverage with zero mocks | [`skills/code/SKILL.md`](../skills/code/SKILL.md) §3 | CI check (not write-time) — `pytest --cov-branch --cov-fail-under=100` on touched packages; covers only what the diff added |
| `TypedDict` `_decode_*` calls `require_*` on every field | [`skills/code/SKILL.md`](../skills/code/SKILL.md) §6 | Extend `check_typed_dict_encode_decode` (B2) — when the decoder is present, AST-verify every TypedDict field appears as a `require_*` call before the return |
| `Protocol` signatures match the real implementation exactly | [`skills/code/SKILL.md`](../skills/code/SKILL.md) Gotchas | mypy `--strict` over the protocol module catches this; promotion = add `[tool.mypy] strict = true` per-module override in `pyproject.toml` for files declaring `Protocol` subclasses |

---

## QUICK CHECKLIST

```
Before ANY code:
[ ] Searched existing configs?
[ ] Importing from centralized config?

Hook will enforce:
[⚡] No NEW comments (existing comments NEVER removed)
[⚡] No magic values
[⚡] Imports at top
[⚡] Logging format args
[ ] File length reasonable (advisory at 400, strong nudge at 1000 — see §6.5)
[⚡] Constants in config/
[⚡] No banned identifiers (ctx, cfg, msg, btn, idx, cnt, tmp, elem, val)
[⚡] No banned function prefixes (handle_, process_, manage_, do_)
[⚡] No type escape hatches (Any imports, cast(), inline Any)
[⚡] No bare except / except Exception / except BaseException
[⚡] No Any in function signatures or class attributes (boundary types)
[⚡] No stub bodies (pass / ... / raise NotImplementedError) outside abstract methods
[⚡] TypedDict has companion _encode_*/_decode_* in same module
[⚡] No test-mode branching in production (TESTING / PYTEST_CURRENT_TEST)
[⚡] No thin wrapper modules (imports only, optionally with __all__, outside __init__.py)
[⚡] Public functions have Google-style Args:/Returns:/Raises: when warranted

Manual check:
[ ] No abbreviations?
[ ] Complete type hints?
[ ] Self-contained components?
[ ] SRP holds (one reason to change per function/class/module)?
[ ] OCP/LSP/ISP/DIP only applied where abstractions already earn their keep (see §7.5)?
[ ] No backwards-compatibility shims (§9.6)?
[ ] No fallback/best-effort wrappers (§9.7)?
[ ] Readability: /check
```
