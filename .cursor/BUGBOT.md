<!-- SYNC-HEADER-START -->
<!--
AUTO-GENERATED — DO NOT EDIT.
Source of truth: jl-cmd/claude-code-config/.github/copilot-instructions.md
Synced by: .github/workflows/sync-ai-rules.yml
Source commit: unknown
Synced at: 2026-04-21T18:03:36.355236+00:00
-->
<!-- SYNC-HEADER-END -->

# GitHub Copilot and automated PR review

This file is the **canonical** instruction set for:

- **Copilot** when it reviews pull requests in this repository.
- **BugBot** and any other automation that is configured to follow the same standards (for example synced copies such as `.cursor/BUGBOT.md` elsewhere—those files are downstream; edit **here** first).

Part 1 is the **static rubric** (what to flag on the diff). Part 2 is the **end-to-end audit–fix loop**: always drive toward **convergence** (zero actionable findings on the current PR head)—run checks, audit the PR scope, fix what is real, repeat until converged or a safety cap. Use **one orchestrator** and **serial** audit and fix passes so each audit starts from fresh context.

---

## Part 1 — Review rubric (diff-only)

Review every change against these rules. Flag each violation with its rule name. Treat rules as mandatory standards; honor file-level exception markers where they appear.

### Comments

- Flag every new inline comment (`#` or `//`) added to modified **production** code; require self-documenting names.
- Preserve every existing comment as-is; treat comments in the surrounding file as sacred.
- Allow docstrings on new functions, methods, classes, or modules (including module-level docstrings).
- **Test files (`test_*.py`, `*_test.py`, `*.test.*`, `*.spec.*`) are fully exempt** — comments and docstrings inside test functions are allowed.
- Exempt markers: shebangs, `# type:`, `# noqa`, `# pylint:`, `# pragma:`, `// @ts-...`, `// eslint-...`, `// prettier-...`, and `/// ` triple-slash reference directives.

### Naming

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

### Magic values & configuration

- Require named constants for numeric, string, and boolean literals in **production** function bodies; exempt `0`, `1`, `-1`, empty string, and `True`/`False` where the meaning is obvious.
- **Test files are exempt** — inline literals in test functions and test-local constants are allowed.
- Treat structural fragments inside f-strings (paths, URLs, query patterns, regex) as magic values in production code; require extraction to a named constant.
- Require `UPPER_SNAKE_CASE` constants in **production code** to live in `config/` (`config/timing.py`, `config/constants.py`, `config/selectors.py`); flag definitions located elsewhere unless the file path matches one of these exemptions. Treat paths as case-insensitive, normalize backslashes to forward slashes, then check whether each pattern below appears anywhere in the path as a substring:
  - Django migrations: path contains `/migrations/`
  - Workflow registries: path contains the substring `/workflow/`, `_tab.py`, `/states.py`, or `/modules.py` (a file named literally `states.py` at repo root is not exempt; `pkg/states.py` is)
  - Test files: path or filename matches common test layout signals (`test_`, `_test.`, `.spec.`, `conftest`, `/tests/`, etc.); test files may define local constants without using `config/`
- Require a search of existing `config/` files for reuse before adding any new production constant.

#### File-global constants

This rule extends the `constants-location` rule defined in `~/.claude/docs/CODE_RULES.md` — see the ⚡ automation-enforced rules table, Constants location row.

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

### Types

- Require type hints on all function parameters and return values; flag missing hints.
- Flag `Any`, `any`, and `# type: ignore` when the diff lacks a justifying note.
- Flag bare `object` used as an escape hatch in place of a proper type.

### Structure

- File length is an advisory smell signal only, not a hard gate by itself: note files above ~400 lines as a soft concern and files above ~1000 lines as a stronger concern. Long files are acceptable when the file's role justifies it (migrations, generated code, registries, large fixtures).
- Flag functions longer than 30 lines.
- Require top-level function spacing to follow the language and existing file convention; for Python, require the standard 2 blank lines between top-level functions, and do not flag 1-vs-2 blank-line differences in other file types unless the surrounding file clearly establishes a convention.
- Require all `import` statements at the top of the file; flag imports inside function bodies.
- Require logging calls for application/runtime output; flag `print()` there, but allow `print()` in CLI tools and automation entrypoints when stdout is the integration contract (for example `print(json.dumps(...))`).
- Require `%`-style arguments inside `log_*` / `logger.*` calls (`logger.info("msg %s", value)`); flag f-strings inside logging calls.

### Design

- Favor functions over classes when state is absent; favor concrete classes over abstract base classes for single implementations; flag dependency-injection frameworks, single-type factories, and multi-level inheritance hierarchies.
- Add optional parameters only when a caller actually varies the value (YAGNI).
- Require construction logic (paths, URLs, formatting, transformations) to live inside model methods; flag the same string-building pattern duplicated across call sites.
- Require self-contained components: each component owns its own state, modals, overlays, and toasts; parents render `<Child />` alone.
- Reuse in-scope data; flag redundant fetches of the same record.
- Require a `TODO:` comment on scaffolding or placeholder code explaining what replaces it and why.

### Tests

- Require a paired test in the same PR for every new production code path (BDD: agree behaviors first, then failing specification before production code).
- Require mocks to include every field the code under test reads; flag partial mocks.
- Flag tests that only assert a constant equals itself or that a symbol exists.

### Scope of review

- Apply these rules only to lines the PR adds or modifies; leave unrelated code alone.

---

## Part 2 — Audit–fix loop

**Convergence is always the goal:** keep auditing and fixing until the latest audit reports **no actionable** `P0` / `P1` / `P2` findings on the current PR head, or until a **safety cap** stops the loop (below). Use **one orchestrator** and **serial** audit and fix passes so each audit uses fresh reasoning against the **current** diff and tree.

### Installing the reference scripts (public upstream)

**Hard requirement — you MUST use these scripts.** Do not re-implement preflight or the code-rules gate by hand, substitute ad hoc shell, or approximate their behavior with a one-off prompt. The only compliant preflight step is executing `bugteam_preflight.py`; the only compliant gate step is executing `bugteam_code_rules_gate.py` from an upstream checkout as below.

Rationale (normative for tool authors, not a loophole): Anthropic’s Agent Skills guidance treats **utility scripts** as the durable mechanism and **Solve, don’t punt** as *“When writing scripts for Skills, handle error conditions rather than punting to Claude.”* See [Agent Skills — Best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) (*Provide utility scripts*, *Solve, don’t punt*).

**Source repository (public):** [github.com/jl-cmd/claude-code-config](https://github.com/jl-cmd/claude-code-config)

1. **MUST obtain** a checkout of `packages/claude-dev-env` from that repository—clone the full repo or copy only that subtree (for example into `vendor/claude-dev-env` in your project). The gate loads `hooks/blocking/code_rules_enforcer.py` relative to the script path; **MUST** preserve this layout under one `claude-dev-env` directory: `skills/bugteam/scripts/*.py` and `hooks/blocking/` (including the enforcer and its dependencies).

2. **MUST** set a root for invocations (example environment variable): `CLAUDE_DEV_ENV_ROOT=/absolute/path/to/packages/claude-dev-env` (the directory that directly contains `hooks/` and `skills/`).

3. **MUST** run every preflight and gate invocation with **current working directory** = the **repository under review** (PR clone root with `.git`), never with `cwd` inside the `claude-code-config` tool checkout alone.

4. **Preflight (once per run) — required command:**

   ```bash
   python "${CLAUDE_DEV_ENV_ROOT}/skills/bugteam/scripts/bugteam_preflight.py"
   ```

   You MAY append `--pre-commit` when `.pre-commit-config.yaml` exists in the repo under review.

5. **Gate (before each audit) — required command:**

   ```bash
   python "${CLAUDE_DEV_ENV_ROOT}/skills/bugteam/scripts/bugteam_code_rules_gate.py" --base origin/<baseBranchName>
   ```

   Use the PR’s base branch (often `main`). The script defaults to `origin/main` when `--base` matches your remote.

Sections §2.3 and §2.4 are **reference documentation only** of what those two executables do. They do not authorize running pytest, `git diff`, or linters **in place of** the scripts. If the scripts cannot be run, stop and fix the installation—do not substitute §2.3 or §2.4 as a manual workflow.

### 2.1 Goal and exit conditions

- **Goal:** Address actionable findings until the latest audit reports none remaining on the current head.
- **Converged:** Last audit pass reports zero actionable findings (you may still list verified-clean categories).
- **Cap reached:** You completed **25** audit iterations for this PR without converging.
- **Error:** Preconditions fail (no PR, no diff, unrecoverable tool failure), or the **gate phase** (§2.4) still fails after **25** consecutive fix rounds in that phase—report the failing command output and stop.

### 2.2 Preconditions

- **Diff scope:** Audits apply to **lines added or modified** relative to the merge base with `base`; unchanged lines are out of scope for new findings.

### 2.3 Preflight (before the first gate)

**Execution:** See **Installing the reference scripts** — you MUST run `bugteam_preflight.py` exactly once at the start of the loop; the subsections below describe its internal behavior **for reference and tooling audits only**, not as an alternative implementation.

**Working directory:** Resolve a **repository root** by walking upward from the process current working directory until a directory contains `.git` or `pytest.ini` (or pass an explicit root if your runner supports it). All subprocesses below use that root as `cwd`.

1. **Optional skip:** If `BUGTEAM_PREFLIGHT_SKIP=1` is set, print a skip notice to stderr, exit preflight with status **0**, and skip steps 2–4.
2. **Pytest:** If `pytest.ini` exists **or** `pyproject.toml` contains a `[tool.pytest` section, and at least one test file is discoverable under the repo root (`test_*.py` or `*_test.py`, excluding `venv`, `.venv`, `node_modules`, `site-packages`), run:

   `python -m pytest` (add `-q` unless you need verbose output)

   with `cwd` = repository root. Treat pytest exit code **5** (no tests collected) as **success**. Any other non-zero exit is a **failed** preflight.
3. **If no pytest configuration** is present, skip pytest and continue (optionally log that pytest was skipped).
4. **Optional pre-commit:** When preflight is configured to include it **and** `.pre-commit-config.yaml` exists at the repository root, run:

   `pre-commit run --all-files`

   with `cwd` = repository root. Non-zero exit is a **failed** preflight.

Resolve every failed step before continuing into §2.4.

### 2.4 Code-rules gate (before every audit)

**Execution:** See **Installing the reference scripts** — you MUST run `bugteam_code_rules_gate.py` before every audit pass; the numbered steps below describe its internal behavior **for reference and tooling audits only**, not as an alternative implementation.

**Working directory:** Use the same **repository root** as §2.3 (`cwd` for all `git` invocations).

1. **Merge base:** Compute `MERGE_BASE = git merge-base HEAD <BASE_REF>`. Default `<BASE_REF>` is `origin/main` unless the PR uses another base (then use `origin/<baseBranchName>` or the ref your automation uses).
2. **Changed files:** List paths with:

   `git diff --name-only <MERGE_BASE>..HEAD`

   (Alternative mode used by some workflows: scope only to **staged** changes via `git diff --cached` and line-parsing rules for staged adds—match your CI if it gates on staged files.)
3. **Scope to code files:** Keep paths whose extension is one of `.py`, `.js`, `.ts`, `.tsx`, `.jsx` (or extend per project policy).
4. **Line scope:** For each changed file, determine **added or modified line numbers** in the working tree relative to `MERGE_BASE` using the unified diff (`git diff <MERGE_BASE>..HEAD -- <path>`). The gate applies **Part 1** only to those lines; for **new** files, apply Part 1 to every line in the file.
5. **Validation:** Apply **Part 1** to the scoped lines only (and new files in full per Part 1). **Blocking** violations on those scopes fail the gate.
6. **Exit status:** Exit **0** when no blocking violations remain on scoped lines; exit **non-zero** when any blocking violation remains. Stderr should list file, line, and rule.

**Explicit file mode (optional):** If the gate is invoked with explicit file paths instead of merge-base diff, validate those files in full or per project policy.

- A **passing** gate means the scoped lines satisfy Part 1 for that check; proceed to **§2.5** (audit).
- When the gate **fails**, run a **standards-fix** pass: apply edits that clear the reported violations, commit once, push, and re-run the **same** gate command. Repeat up to **25** times in this gate phase. If the gate still fails after **25** fix rounds, stop with **error** and include the gate command and stderr (or summary) in the final report. The next audit (§2.5) follows only after a **passing** gate run.

### 2.5 Audit pass (clean-room)

Base each audit only on the **current PR diff** and **current** tree state—treat earlier audit text as history, not as a source of new findings.

- **Capture scope:** Save the PR diff (for example via `gh pr diff <N>`) for the audit.
- **Rubric:** Apply **Part 1** to changed lines, and explicitly walk **categories A–J** (minimum checklist):

  - **A** API contracts (signatures, types, async correctness)
  - **B** Selectors / queries / engine compatibility
  - **C** Resource cleanup and lifecycle
  - **D** Scoping, ordering, unbound references
  - **E** Dead code and unused imports
  - **F** Silent failures and error propagation
  - **G** Off-by-one, bounds, overflow
  - **H** Security boundaries (injection, path traversal, auth, secrets)
  - **I** Concurrency (races, missing awaits, shared mutable state)
  - **J** Magic values and configuration drift

  **Depth for A–J:** Use this repository’s own docs when they define category detail (for example `docs/CODE_RULES.md`, `CONTRIBUTING.md`, or a security review checklist). Where no extra doc exists, the one-line labels above are the minimum; for each category, return either a finding or a **verified-clean** line with brief evidence.

- **Severity:** Assign each finding `P0`, `P1`, or `P2`. Only report **actionable** items when you can cite **file:line**, a causal explanation, and a concrete fix direction aligned with the PR’s purpose.
- **Uncertainty:** If something might be wrong but context is insufficient, open a **needs-user-review** thread (non-blocking for other fixes) listing missing evidence and the decision needed.

### 2.6 GitHub review shape (one review per loop)

After each audit, publish **one** pull request review for that loop:

- **Review body:** Header line `## <loop label> audit: <P0>P0 / <P1>P1 / <P2>P2` (include `→ clean` when counts are zero).
- **Anchored findings:** For each finding whose line appears on the PR diff, add a **review comment** on that line (`path`, `line`, `side: RIGHT`).
- **Unanchored findings:** List lines not on the diff under **Findings without a diff anchor** in the review body (no line-level anchor for those).
- **POST failure:** If the review API fails, post **one issue comment** on the PR with the full loop content.

### 2.7 Fix pass (targeted)

When the last audit had actionable findings:

- **Input:** Only the **last** audit’s findings (not older loops).
- **Edits:** Touch only what is needed to fix those findings; avoid drive-by refactors.
- **Commit:** **One** commit per loop; push to update the PR branch.
- **Verify:** Re-run the validations this repo requires for touched files before finishing the commit.
- **Replies:** On each finding thread, reply with `Fixed in <full-sha>` or `Could not address this loop: <reason>`.

### 2.8 Loop and cap

- After a successful fix push, return to **§2.4** (gate) then **§2.5** (audit).
- Increment the **audit loop** counter when you **complete** an audit (the **25** cap counts **audit loops**, not individual gate retries inside §2.4).
- **Maximum 25 audit loops** per PR. If you reach **25** audits without convergence, stop and report **cap reached**.

### 2.9 Finalization

- **PR description:** Update the PR body for **human readers** (what changed, why, how to validate). Match house style if the repo documents one.
- **Report:** Emit the same **final report shape** you would use for a normal completed run, plus explicit notes when the run ended on a cap or error:

  - Exit: `converged` | `cap reached` | `error`
  - Loops: total audit loops completed
  - Starting commit / final commit (short SHAs)
  - Net change summary if useful (files, +/- lines)
  - **Loop log:** One line per loop, e.g. `N audit: <P0>P0 <P1>P1 <P2>P2` (and fix summary when applicable), same style as a standard loop transcript
  - **When `cap reached`:** Add a closing line such as `Stopped after 25 audit loops (cap) without convergence.`
  - **When `error`:** Add a closing line such as `Stopped in gate phase after 25 fix rounds;` plus the gate command and failure summary.
  - **When `converged`:** End with `converged` and the final audit line showing zero actionable findings.

### 2.10 Single audit stream

Run **one** audit pass per loop with a clean context. If the platform allows parallel reviews, still merge results into **one** review per loop so the PR thread stays one coherent cycle.
