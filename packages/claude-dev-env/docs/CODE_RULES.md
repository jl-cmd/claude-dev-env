# Code Rules Reference

Compact reference for agents. ⚡ marks rules enforced by `code_rules_enforcer.py` — the hook blocks the Write/Edit and returns the corrective detail at violation time, so this document lists those rules by name only.

---

## COMMENT PRESERVATION (ABSOLUTE RULE)

**NEVER remove existing comments.** Existing comments are SACRED. Only evaluate comments on lines you are actively changing. Do not add new inline comments in production code — write self-documenting code. Docstrings (module/class/function) are always allowed. Test files are exempt. The hook enforces both directions: it blocks new inline comments AND blocks deletion of existing ones.

---

## CORE PRINCIPLES

- **Self-documenting code** — naming over comments. Full 8-dimension rubric: `~/.claude/skills/readability-review/SKILL.md` (`/check` for parallel team review, `/readability-review` standalone).
- **Centralized configuration** — every constant lives in ONE place (`config/`).
- **Reuse before create** — search first, import second, create last.
- **Encapsulation enables cleaner naming** — `isMaxLevel(level)` > `level >= MAXIMUM_LEVEL`.

---

## ⚡ HOOK-ENFORCED RULES

`code_rules_enforcer.py` blocks each of these at Write/Edit and explains the specific violation when it fires; exact patterns and exemption lists live in the hook:

no new comments · imports at top · logging format args (`log_*("...", arg)`) · no magic values in production bodies (0, 1, -1 exempt) · UPPER_SNAKE constants only in `config/` (exempt: `config/*`, `/migrations/`, workflow registries `/workflow/` + `_tab.py` + `/states.py` + `/modules.py`, test files) · no hardcoded user home paths · guarded `sys.path.insert` · no unused module-level imports · banned identifiers (`ctx`, `cfg`, `msg`, `btn`, `idx`, `cnt`, `tmp`, `elem`, `val`) · banned function prefixes (`handle_`, `process_`, `manage_`, `do_`) · no type escape hatches (`Any` import, `cast()`, inline `Any`) outside boundary files · no bare/broad `except` · no `Any` in signatures or class attributes · no stub bodies (`pass`/`...`/`raise NotImplementedError`) outside abstract/Protocol · TypedDict `_encode_*`/`_decode_*` companions in the same module · no test-mode branching in production (use dependency injection) · no thin wrapper modules · Google-style docstrings on public functions with `Args:` matching the signature · boolean names prefixed `is_`/`has_`/`should_`/`can_`/`was_`/`did_` (assignments AND bool-typed parameters) · must-check returns (`find_and_click`, `write_outcome`) assigned and checked · known pytest fixture parameters in test files annotated with their single documented type (`tmp_path: Path`, `monkeypatch: pytest.MonkeyPatch`, `capsys`, `caplog`, `request`, …) · known pytest fixture parameters a test function declares but never reads (drop the unused parameter — pytest still pays its setup cost)

Test files are exempt from most checks. The one annotation the test-file exemption does NOT cover is a known pytest builtin fixture parameter: `tmp_path`, `monkeypatch`, `capsys`, `capfd`, `caplog`, `request`, and `tmp_path_factory` each have a single documented injected type, so the gate requires that annotation (`tmp_path: Path`) even inside a test file. The same set of fixtures is also subject to a use check: a pytest-collected test function that declares one of these parameters and never references it in its body fails the gate, because pytest materializes the fixture's setup (the temp directory, the monkeypatch context, the output capture) on every run whether or not the body reads the value — drop the unused parameter. A `@pytest.fixture`-decorated function is exempt from the use check, since injecting one fixture into another purely to order its setup is intentional. Ordinary test parameters stay exempt from both checks. See also the file-global constants use-count rule: [`rules/file-global-constants.md`](../rules/file-global-constants.md).

---

## 3. REUSE CONSTANTS / 4. CONFIG LOCATIONS

Before writing ANY constant: search `config/` for the exact value → semantic match → add to the existing config file → create new (rare). Locations: timeouts/delays/retries → `config/timing.py`; ports/URLs/thresholds → `config/constants.py`; CSS selectors → `config/selectors.py`.

---

## 5. NO ABBREVIATIONS

Full words only (`context`, not `ctx`). Exceptions: `i`/`j`/`k` in loops, `e` for exception. Naming patterns: loop vars `each_*`; booleans `is_/has_/should_/can_/was_/did_`; collections `all_*`; maps `X_by_Y`; preposition params (`from_path=`, `to=`, `into=`). Banned names: `result`, `data`, `output`, `response`, `value`, `item`, `temp`. Banned prefixes: `handle`, `process`, `manage`, `do`.

---

## 6. COMPLETE TYPE HINTS

ALL parameters typed, ALL returns typed. No `Any`, no `# type: ignore` (also enforced by the mypy_validator.py hook).

## 6.5 FILE LENGTH GUIDANCE

Advisory only, never blocking: soft advisory at >= 400 lines, strong nudge at >= 1000 (pylint / SonarQube defaults). Split on cohesion (SRP, "Large Class" smell), not line count — run the readability rubric when an advisory fires.

---

## 7. RIGHT-SIZED ENGINEERING

**Simple > Clever. Functions > Classes. Concrete > Abstract.**
Never: ABC for single impl, DI frameworks, factory for single type. Always: functions when no state, concrete classes, simple imports.

## 7.5 SOLID PRINCIPLES

**SRP always applies** — one reason to change per function/class/module. **OCP, LSP, ISP, DIP apply only where two or more concrete implementations already share a contract**; with a single concretion §7 wins (concrete classes, direct imports, YAGNI — introduce the abstraction at the commit that adds the second concretion). Misapplication signals: interface/ABC with exactly one implementation, SRP-splitting a cohesive class by size alone, abstract factories for one product, DI containers where every injected type has one concretion.

---

## 8. TDD PROCESS

1. **RED** — failing test first. 2. **GREEN** — minimum code to pass. 3. **REFACTOR** — only if valuable.

## 9. SELF-CONTAINED COMPONENTS

Components own their complete feature (state, modals, overlays, toasts). Parents just render `<Child />`.

## 9.5 NO THIN WRAPPER MODULES

A non-`__init__.py` module whose body is only imports (optionally `__all__`) is indirection without payload — callers import the real module. `__init__.py` is the canonical re-export surface and is exempt.

## 9.6 NO BACKWARDS-COMPATIBILITY SHIMS

Removed code is removed: no renamed re-export aliases, no `_old_*` aliases, no keep-alive wrapper modules, no tombstone comment markers. When a symbol's name or signature changes, update the call sites in the same commit. Git history records change; the codebase records what exists.

## 9.7 NO FALLBACK / BEST-EFFORT WRAPPERS

Never swallow a failure into a default unless the caller explicitly opted in at the boundary. Name the specific exception (`except KeyError:`) and propagate the rest — collapsing every error class to `None` masks programming errors and makes debugging impossible.

## 9.8 REMOVE CODE YOU ORPHAN (Dead Code Elimination)

An edit that deletes or rewrites code also removes everything it makes dead: unread variables, uncalled functions, unpassed parameters, dead branches, unused imports, helper files whose only consumer that edit deleted. Prove unreachability first: Serena `find_referencing_symbols` plus a text search for dynamic lookups (`getattr`, entry-point names). A symbol is live only when a reference chain reaches a live entry point (CLI command, route, public API, test); a self-referential dead cluster is removed together in the same commit. **When liveness is uncertain (public API, plugin hook, reflective dispatch), do NOT delete — surface the ambiguity via AskUserQuestion.** Source links: [`references/dead-code-elimination.md`](references/dead-code-elimination.md).

## 10. NO REDUNDANT DATA FETCHES

If you already have the data, don't fetch it again.

---

## 11. ENFORCEMENT SURFACES

⚡ **Hooks** block pattern-matchable violations at Write/Edit time. 🤖 **Prompt context** carries judgment principles (SRP, Right-Sized Engineering, conservative-action, BDD discovery, docstring-prose-matches-implementation; the `/code` skill prepends strict mode for a session: no `Any`/`cast()`, immutable TypedDicts with `_encode_*`/`_decode_*` + `require_*` validation, per-module `_test_hooks.py` DI, 100% statement + branch coverage, zero mocks). 👥 **Audit rubrics** (`/check`, `packages/claude-dev-env/audit-rubrics/` categories A–P) cover cross-file architectural concerns. Rules with documented-but-pending hook coverage live in `~/.claude/rules/*.md` and `skills/code/SKILL.md`; each names its own promotion path. The docstring-prose standard (free-form enumerations match the body) lives in `packages/claude-dev-env/rules/docstring-prose-matches-implementation.md`, enforced via Category O6 audit.
