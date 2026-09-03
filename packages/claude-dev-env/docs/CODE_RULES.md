# Code Rules Reference

The canonical review-criteria instruction set for every AI agent that audits pull requests in this repository, loaded on demand. [`.cursor/BUGBOT.md`](../../../.cursor/BUGBOT.md) is the checked-in pointer file Cursor BugBot reads; it points here.

⚡ marks rules enforced by hand-maintained `code_rules_enforcer.py` — the hook blocks the Write/Edit and returns the corrective detail at violation time, so this document lists those rules by name only. Session policy (question routing, task tracking) lives in `rules/*.md`; see [`code-standards.md`](../rules/code-standards.md).

---

## COMMENT PRESERVATION

Do not add code comments. Preserve existing comments. Docstrings remain allowed.

When a change touches code that an existing comment describes or is attached to, remove that comment in the same change and carry its meaning through clear names and structure. Leave comments tied to untouched code unchanged. Keep comment cleanup inside the requested task.
Production and tests follow one rule. Changed directive, TODO, FIXME, HACK, XXX, and type-ignore comments are removed rather than added or justified.

---

## CORE PRINCIPLES

- **Self-documenting code** — naming over comments. Full 8-dimension rubric: `~/.claude/skills/readability-review/SKILL.md` (`/check` for parallel team review, `/readability-review` standalone).
- **Centralized configuration** — every constant lives in ONE place (`config/`).
- **Reuse before create** — search first, import second, create last.
- **Encapsulation enables cleaner naming** — `isMaxLevel(level)` > `level >= MAXIMUM_LEVEL`.
- **Construction logic lives in the model** — path/URL building, formatting, and transformations belong on the model or service that owns the data; a string pattern built at two or more call sites moves to a method there.

---

## ⚡ HOOK-ENFORCED RULES

`code_rules_enforcer.py` blocks each of these at Write/Edit and explains the specific violation when it fires; exact patterns and exemption lists live in the hook:

no new comments · imports at top · logging format args (`log_*("...", arg)`) · no `%s`/`%d` printf tokens in a `str.format`-logger message (`log_*` imported from `automation_logging`; `str.format` drops the args — use `{}`) · no magic values in production bodies (0, 1, -1 exempt) · UPPER_SNAKE constants only in `config/` (exempt: `config/*`; `/migrations/`; Workflow registries: path contains any of these substrings — `/workflow/`, `_tab.py`, `/states.py`, or `/modules.py`, each matching independently as a substring, so `pkg/states.py` qualifies while a top-level `states.py` follows the standard `config/` rule; test files — path or filename matches `test_`, `_test.`, `.spec.`, `conftest`, or `/tests/`) · no hardcoded user home paths · guarded `sys.path.insert` · banned identifiers (`ctx`, `cfg`, `msg`, `btn`, `idx`, `cnt`, `tmp`, `elem`, `val`) · banned function prefixes (`handle_`, `process_`, `manage_`, `do_`) · no type escape hatches (`Any` import, `cast()`, inline `Any`, a parameter typed bare `object` whose body reads `param.attribute`) outside boundary files · no bare/broad `except` · no `Any` in signatures or class attributes · no stub bodies (`pass`/`...`/`raise NotImplementedError`) outside abstract/Protocol · TypedDict `_encode_*`/`_decode_*` companions in the same module · no test-mode branching in production (use dependency injection) · no thin wrapper modules · Google-style docstrings on public functions with `Args:` matching the signature · boolean names prefixed `is_`/`has_`/`should_`/`can_`/`was_`/`did_` (assignments AND bool-typed parameters) · must-check returns (`find_and_click`, `write_outcome`) assigned and checked · known pytest fixture parameters in test files annotated with their single documented type (`tmp_path: Path`, `monkeypatch: pytest.MonkeyPatch`, `capsys`, `caplog`, `request`, …) · known pytest fixture parameters a test function declares but never references (drop the unused parameter — pytest still pays its setup cost) · JavaScript/TypeScript boolean declarations (`const`/`let`/`var` bound to a boolean literal or negation) and `@param {boolean}` JSDoc names prefixed `is`/`has`/`should`/`can`/`was`/`did` (camelCase forms) · banned identifiers as `.mjs`/`.js` declaration names (`result`, `data`, `ctx`, `msg`, …), scoped to changed lines · in test files, banned identifiers fire on changed lines, and pytest-collectable `test_*` functions need a return annotation · unused module-level imports and unsorted import blocks are ruff's job (F401, isort I001), not this hook's · a `hooks/blocking/` command classifier anchors its multi-word command regex to the command start (`^`/`\A`) or tokenizes the first word (`shlex.split`), never matching a command as a bare substring

Test files follow the comment policy above; other test-specific exemptions are listed here. The one annotation the test-file exemption does NOT cover is a known pytest builtin fixture parameter: `tmp_path`, `monkeypatch`, `capsys`, `capfd`, `caplog`, `request`, and `tmp_path_factory` each have a single documented injected type, so the gate requires that annotation (`tmp_path: Path`) even inside a test file. The same set of fixtures is also subject to a use check: a pytest-collected test function that declares one of these parameters and never references it in its body fails the gate, because pytest materializes the fixture's setup (the temp directory, the monkeypatch context, the output capture) on every run whether or not the body reads the value — drop the unused parameter. A parameter counts as referenced when its name is read, augmented-assigned, or deleted anywhere in the body, including inside a nested function or comprehension. Only pytest-collectable functions are inspected — those at module top level or defined directly in a class body; a function nested inside another function's body is a local helper pytest never collects, so its fixture-named parameter is exempt. A `@pytest.fixture`-decorated function is exempt from the use check, since injecting one fixture into another purely to order its setup is intentional. Ordinary test parameters stay exempt from both checks. See also the file-global constants use-count rule: [`rules/file-global-constants.md`](../rules/file-global-constants.md).

---

## 3. REUSE CONSTANTS / 4. CONFIG LOCATIONS

Before writing ANY constant: search `config/` for the exact value → semantic match → add to the existing config file → create new (rare). Locations: timeouts/delays/retries → `config/timing.py`; ports/URLs/thresholds → `config/constants.py`; CSS selectors → `config/selectors.py`.

---

## 5. NO ABBREVIATIONS

Full words only (`context`, not `ctx`). Exceptions: `i`/`j`/`k` in loops, `e` for exception. Naming patterns: loop vars `each_*`; booleans `is_/has_/should_/can_/was_/did_`; collections `all_*`; maps `X_by_Y`; preposition params (`from_path=`, `to=`, `into=`). Banned names: `result`, `data`, `output`, `response`, `value`, `item`, `temp`. Banned prefixes: `handle`, `process`, `manage`, `do`. Name a component for what it IS — `Overlay`, `Validator`, `InvoicePreview`.

### Public compatibility definitions

The banned-noun check applies to public function definitions, parameters, and body bindings. Use clear names instead of a directive marker.

---

## 6. COMPLETE TYPE HINTS

ALL parameters typed, ALL returns typed. No `Any`. Avoid `# type: ignore`; remove it and use a typed boundary or real type. Prefer fixing the type over an ignore when a real annotation is available.

## 6.5 FILE LENGTH GUIDANCE

Advisory only, never blocking: emit a stderr advisory at >= 400 lines and a stronger stderr advisory at >= 1000 (pylint / SonarQube defaults). Split on cohesion (SRP, "Large Class" smell), not line count — run the readability rubric when an advisory fires.

---

## 7. RIGHT-SIZED ENGINEERING

**Simple > Clever. Functions > Classes. Concrete > Abstract.**
Never: ABC for single impl, DI frameworks, factory for single type. Always: functions when no state, concrete classes, simple imports.
Parameters follow YAGNI: add an optional parameter when a caller varies the value; when every call site passes the same value, make it required or inline the constant. Remove parameters no caller passes and no body reads.

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

**A per-member boundary records each member outcome.** In a batch loop, a `try`/`except` inside the loop body catches a declared `*ItemBlocked` type, records the failure with its reason, and continues to the next member — the failure reaches the run report by name. The boundary preserves the blast radius: escalations re-raise first so a `*RunFatal` passes through directly, while `except Exception` triggers the rule. Types, boundary shape, and the parked-member report: [`rules/failure-blast-radius.md`](../rules/failure-blast-radius.md).

## 9.8 REMOVE CODE YOU ORPHAN (Dead Code Elimination)

An edit that deletes or rewrites code also removes everything it makes dead: unread variables, uncalled functions, unpassed parameters, dead branches, unused imports, helper files whose only consumer that edit deleted. Prove unreachability first: Serena `find_referencing_symbols` plus a text search for dynamic lookups (`getattr`, entry-point names). A symbol is live only when a reference chain reaches a live entry point (CLI command, route, public API, test); a self-referential dead cluster is removed together in the same commit. **When liveness is uncertain (public API, plugin hook, reflective dispatch), do NOT delete — surface the ambiguity via AskUserQuestion.** Source links: [`references/dead-code-elimination.md`](references/dead-code-elimination.md).

## 10. NO REDUNDANT DATA FETCHES

If you already have the data, don't fetch it again.

---

## 11. ENFORCEMENT SURFACES

⚡ **Hooks** block pattern-matchable violations at Write/Edit time. 🤖 **Prompt context** carries judgment principles (SRP, Right-Sized Engineering, research-first action on ambiguous intent, BDD discovery, docstring-prose-matches-implementation). 👥 **Audit rubrics** (`/check`, `packages/claude-dev-env/audit-rubrics/` categories A–Q) cover cross-file architectural concerns. Rules with documented-but-pending hook coverage live in `~/.claude/rules/*.md`; each names its own promotion path. The docstring-prose standard (free-form enumerations match the body) lives in `packages/claude-dev-env/rules/docstring-prose-matches-implementation.md`, enforced via Category O6 audit. The diagram-first docstring standard (a summary line, then a `::` example or doctest, then a couple of short prose lines) lives in `packages/claude-dev-env/rules/plain-illustrative-docstrings.md`, enforced by the `check_docstring_runon_sentence` and `check_docstring_prose_wall_without_illustration` backstop hooks and Category O9 audit.

## 11.5 VALIDATION-PHASE PRECEDENCE

`code_rules_enforcer.py` decides what a run checks and reports along three independent axes. Each axis filters a narrower scope than the one before it; none widens what the axis before it already decided.

1. **Phase selects the roster.** `EDIT_LANE_PHASE` or `FULL_GATE_PHASE` decides which checks exist in the lane at all. `validate_content_for_phase` takes `phase` keyword-only with no default, so every caller names its lane explicitly.
2. **Target classification filters within a lane.** The hook-infrastructure patterns and the ephemeral-path check decide whether a target is validated, and with which subset. Classification narrows a lane; it never adds a check the phase already excluded.
3. **Changed-line scope filters only the report.** `defer_scope_to_caller` and the changed-line set decide which found violations block. Scope filters findings after every check in the roster already ran; it adds or removes no check.

`hooks/hooks_constants/validation_phase_constants.py` is the single source for all three axes: the phase names (`EDIT_LANE_PHASE`, `FULL_GATE_PHASE`), the full-gate-only roster (`ALL_FULL_GATE_ONLY_CHECK_NAMES`), and the hook-infrastructure edit-lane roster (`ALL_HOOK_INFRASTRUCTURE_EDIT_LANE_CHECK_NAMES`).

## 11.6 LANE ASSIGNMENT IS BY SCOPE

Scope assigns the lane. A check that reads a file other than the target runs on the full gate. Every other check runs on both lanes.

Hook-infrastructure targets run three checks in the edit lane — `check_same_file_inline_duplicate_body`, `check_zero_payload_function_alias`, `check_unanchored_command_dispatch` — and the whole roster on the full gate. `ALL_HOOK_INFRASTRUCTURE_EDIT_LANE_CHECK_NAMES` holds that set.

Three surfaces report on the roster, and each reports a specific thing:

- `hooks/validators/hook_timing_harness.py` builds a `Write` payload against a target that already holds content. `_contents_for_validation` returns `None` for that payload, so the harness times interpreter start and hook dispatch. Time an `Edit` payload against a real file to measure the checks.
- `~/.claude/logs/hook-blocks.log` records the denials raised by fixtures in `test_code_rules_enforcer_*.py` and by the timing harness's default target.
- `hooks/validators/run_all_validators.py` stages the target under a temporary root and rebuilds the shortest path tail that carries every exemption signal. The walk starts at the target's own project root and skips a directory pytest generated for its own scratch tree, so the staged path reads the same wherever `--basetemp` places that tree.
