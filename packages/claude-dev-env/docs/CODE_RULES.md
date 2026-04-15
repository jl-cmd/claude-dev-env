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
| File line count | Advisory only — see [File length guidance](#65-file-length-guidance) |
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

## 8. BDD PROCESS

**Discovery before code.** Follow `~/.claude/rules/bdd.md` and `<behavior_protocol>` in the system prompt.

**Automate (Red / Green / Refactor):**

1. **RED** — Failing specification (test) first
2. **GREEN** — Minimum code to pass
3. **REFACTOR** — Only when it improves clarity

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
[ ] File length reasonable (advisory at 400, strong nudge at 1000 — see §6.5)
[⚡] Constants in config/

Manual check:
[ ] No abbreviations?
[ ] Complete type hints?
[ ] Self-contained components?
[ ] Readability: /check or /readability-review
```
