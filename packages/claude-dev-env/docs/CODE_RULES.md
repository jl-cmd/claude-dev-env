# Code Rules Reference

Compact reference for agents. Hook-enforced rules marked with ⚡.

---

## COMMENT PRESERVATION (ABSOLUTE RULE)

**NEVER remove existing comments.** If you are not adding or removing code on a line, do not touch its comments.

- Existing comments are SACRED — never delete, rewrite, or "clean up" existing comments
- New inline comments are not needed — write self-documenting code instead
- Docstrings for new files/methods/classes are allowed
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

These rules are automatically enforced by `code-rules-enforcer.py`. Violations block Write/Edit.

| Rule | What's Checked |
|------|----------------|
| No NEW comments | `#` / `//` in new code only (existing comments NEVER removed; shebangs, type:, noqa, eslint, docstrings exempt) |
| Imports at top | No `import` inside function bodies |
| Logging format args | No `log_*(f"...")` - use `log_*("...", arg)` |
| File line count | Max 400 lines per file |
| Magic values | No literals in function bodies (0, 1, -1 exempt). Includes string templates — if you strip the interpolations from an f-string and the remaining literal text is structural (paths, URLs, patterns), those fragments are magic values that belong in config |
| Constants location | No `UPPER_SNAKE =` outside `config/` |

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

**Extended naming rules** (from readability-review rubric):
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

## 7. RIGHT-SIZED ENGINEERING

**Simple > Clever. Functions > Classes. Concrete > Abstract.**

Never: ABC for single impl, DI frameworks, factory for single type
Always: Functions when no state, concrete classes, simple imports

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
[⚡] File under 400 lines
[⚡] Constants in config/

Manual check:
[ ] No abbreviations?
[ ] Complete type hints?
[ ] Self-contained components?
[ ] Readability: /check or /readability-review
```
