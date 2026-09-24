Audit [REPO/ARTIFACT] [TARGET_ID] for **Category J only** (CODE_RULES.md compliance). Skip A-I, K-P. Sub-bucket forced-exhaustion mode: Category J is decomposed into 11 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA]
- Artifact: [PR title / commit subject / file set / patch series]
- Head SHA / Revision: [SHA or revision identifier]
- Scope: [files / line ranges / packages in scope]
- Languages in scope: [e.g., Python, PowerShell, TypeScript]
- Production vs test split: [explicit list of which files are production and which are test files; both use the same comment rule]

ID prefix: `find`.

## Source material

Inline the artifact (full diff or full file contents) under a clearly delimited block below this section. Use the chunking guide in [`../source-material-section-types.md`](../source-material-section-types.md) to choose the right Source-material section type (full-diff, file-set, patch-series, or excerpt-with-context). Mark every line range that is in scope; mark explicitly which files are test files and which are production.

Replace this paragraph with the chunked source material before issuing the prompt.

## Write-time exemptions do not scope this audit

When a change touches code that an existing comment describes or is attached to, remove that comment in the same change and carry its meaning through clear names and structure. Leave comments tied to untouched code unchanged. Keep comment cleanup inside the requested task.
Production and tests follow one rule. Changed directive, TODO, FIXME, HACK, XXX, and type-ignore comments are removed rather than added or justified.

The write-time hook skips several rules on test files and on `.mjs` / `.js` files; comment changes use one rule for production and tests. This audit does not skip the other listed rules. Apply these rules to every changed line — production, test, and JavaScript files alike:

- Naming (J5, J6) — banned identifiers and banned function prefixes; boolean names prefixed `is_` / `has_` / `should_` / `can_` / `was_` / `did_`.
- Logging format (J9) — the format string and its arguments pass as separate parameters, never an f-string.
- Type annotations (J7) — every changed parameter and return is typed; no `Any`, no `# type: ignore` directives.
- Unused imports — a module-level import a changed file does not read.
- Function length — a changed function past the length threshold splits into named helpers.

A `test_*.py` name or a `.mjs` extension takes the line out of the write-time gate, not out of this audit. J1 (magic values) and J3 (constants location) keep their test-file exemption; the five rules above do not.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**J1. Magic values in production function bodies**
- Walk every numeric or non-trivial literal other than `0`, `1`, `-1` inside production function bodies.
- Test files are exempt. Module-level declarations belong to J3.
- For each literal found, decide: structural value that belongs in `config/` (flag) vs. local arithmetic constant tied to the line's logic (defendable).
- Adversarial probes must each verify a distinct angle: (a) does the literal duplicate an existing value already centralized in `config/`? (b) does the literal silently couple two languages (e.g., a Python config value and a hand-typed PowerShell / shell mirror)? (c) does the literal appear in user-facing help/doc text in a way that would silently lie if the canonical value changed?

**J2. String-template magic**
- Walk every f-string / template string in production code. Strip the `{...}` interpolations and inspect the remaining literal residue.
- Flag only when the residue is **structural** (paths, URLs, regex, command patterns, query DSL fragments). Descriptive output / log prefixes / human-readable help text are not J2-scope by themselves.
- Adversarial probes: (a) does any f-string concatenate a path, URL, or pattern fragment that should be sourced from `config/`? (b) does any literal repeat across two languages or two files in a way that belongs in shared config? (c) does the literal include an embedded number that mirrors a `config/` constant and would drift if the constant changed?

**J3. Constants location**
- Walk every module-level `UPPER_SNAKE = ...` declaration in production files.
- Exempt path families: `config/*`, `/migrations/`, `/workflow/`, `_tab.py`, `/states.py`, `/modules.py`, and all test files. Anywhere else, an UPPER_SNAKE module-level constant must move to `config/`.
- Distinguish *imports* (`from config.X import FOO`) from *declarations* — imports are not J3-scope.
- Adversarial probes: (a) does any module-level constant masquerade as an "import" via a re-export pattern? (b) is there a `_PRIVATE_UPPER` declaration that escapes the visual UPPER_SNAKE filter but is still module-level? (c) does any test file declare a constant that *would* be flagged if it were in production, indicating the constant probably belongs in `config/` even if test-exempt?

**J5. Abbreviations**
- Walk every parameter, local, and attribute name across production, test, and JavaScript changed lines. Flag: `ctx`, `cfg`, `msg`, `btn`, `idx`, `cnt`, `elem`, `val`, `tmp`, `str`, `num`, `arr`, `obj`, `fn`, `cb`, `req`, `res`. Loop counters `i`/`j`/`k` and `e` for exceptions are exempt.
- This audit walks changed test-file and `.mjs` / `.js` lines for this rule, even though the write-time hook skips them.
- Adversarial probes: (a) is there a borderline name (e.g., `removed`, `arguments`) that someone might mis-classify as an abbreviation but is a full English word? Confirm. (b) does any callback / parameter / attribute use a short variant of a domain term that is technically a full word but conventionally abbreviates a longer one? (c) does any variable in a comprehension or lambda use a single letter outside the `i`/`j`/`k`/`e` exemption?

**J6. Vague names**
- Flag any name from the vague list: `result`, `data`, `output`, `response`, `value`, `item`, `temp`, `info`, `stuff`, `thing`. Vague verb prefixes for function names: `handle`, `process`, `manage`, `do`.
- This audit walks changed test-file and `.mjs` / `.js` lines for this rule, even though the write-time hook skips them.
- Adversarial probes: (a) does any local variable use a domain-adjacent name that is on the vague list (e.g., `result` from a parser, `data` from a fetch)? (b) does any newly-introduced function name start with a vague prefix? (c) does any public attribute / dict key use a vague label that the call site has to disambiguate by surrounding context?

**J7. Type hints**
- Walk every function across production, test, and JavaScript changed lines. Verify parameter and return types are present, no `Any`, no `# type: ignore`.
- This audit walks changed test-file and `.mjs` / `.js` lines for this rule, even though the write-time hook skips them.
- Adversarial probes: (a) does any production function rely on inferred return type from a single `return` path? (b) does any parameter use a string-quoted forward reference that masks `Any`? (c) is there a `# type: ignore` anywhere? Grep the diff explicitly.

**J8. New inline comments**
- Every `#` or `//` comment line **added** by this diff in any code — flag.
- Module/function/class docstrings are always allowed.
- Comments tied to untouched code remain unchanged; a changed comment is removed with the code it describes.
- Test files follow the same no-new-comment policy.
- Changed directive, TODO, FIXME, HACK, XXX, and type-ignore comments are removed rather than added or justified.
- Adversarial probes: (a) is there any `# type:` or marker comment that is inert prose rather than a type-checker / linter directive? (b) is any docstring carrying inline-comment content (line-level explanations rather than module/function description)? (c) does any newly-added blank line between code stanzas function as a comment substitute, suggesting the author wanted to add a comment but couldn't?

**J9. Logging format**
- Walk every `log_*(...)` call. Must be `log_*("template with {}", arg)`, not `log_*(f"...")`.
- The rule applies to the project's structured `log_*` family, not stdlib `print`. `print` f-strings are J2-scope (string-template magic), not J9-scope.
- This audit walks changed test-file and `.mjs` / `.js` lines for this rule, even though the write-time hook skips them.
- Adversarial probes: (a) is there any imported `log_*` function in production code that uses an f-string? (b) is there a logger-equivalent call (e.g., `logger.info(f"...")` from `logging` stdlib) that should be subject to the same rule? (c) does any non-Python logger family (e.g., `console.log`, `Write-Host`, structured-log helpers) appear with a template-string pattern that mirrors the J9 anti-pattern?

**J10. Imports inside functions**
- Every `import` / `from ... import ...` statement — verify at module scope.
- A test file may hold a deferred import at module scope after a guarded `sys.path.insert(0, ...)` block.
- Adversarial probes: (a) is there any lazy `import` inside a production function body? (b) does any conditional `import` (e.g., inside `if TYPE_CHECKING:`) escape into runtime accidentally? (c) does any non-Python language analog (e.g., `require(...)` inside a JS function, `Import-Module` inside a PowerShell `if` branch) appear in production code?

**J11. sys.path.insert dedup**
- Every `sys.path.insert(0, X)` must be guarded by `if X not in sys.path:` (or equivalent membership test).
- Test files are explicitly in scope for J11 (the rule that always applies even to test files).
- Adversarial probes: (a) is the guard expression semantically equivalent to `if X not in sys.path:` where `X` is exactly the value being inserted (no string/Path mismatch)? (b) is there a second `sys.path` mutation elsewhere in the file that is not guarded? (c) would importing the module twice (e.g., via test collection re-runs) re-trigger the insert?

**J12. Hardcoded user paths**
- Any string literal containing a user-specific home path in production code? Use `pathlib.Path.home()` or `os.path.expanduser('~')`.
- Exempt: test files, `config/` files, workflow registry paths (`/workflow/`, `_tab.py`, `/states.py`, `/modules.py`), Django migrations (`/migrations/`), and hook infrastructure.
- Adversarial probes: (a) does any error message, help string, or docstring example embed a user-specific home path? Grep the diff. (b) does any scheduled-task / launcher / installer artifact hardcode a path that should be derived from `$PSCommandPath`, `__file__`, or `os.getcwd()`? (c) does any docstring example show a user-specific home, even if the runtime code itself is path-clean?

## Cross-bucket questions to answer at the end

Q1: Are there literals or names that span two sub-buckets (e.g., a magic value in J1 that also appears inside an f-string scrutinized by J2; an UPPER_SNAKE in J3 that is also an abbreviation under J5)? Cite the literal/name and both sub-bucket IDs.

Q2: What is the worst CODE_RULES drift introduced by this artifact? Cite `<file>:<line>`. (Common candidates: cross-language duplicates, stale help text mirroring a config constant, abbreviations in a public API surface, bare `Any` annotations, hardcoded user paths in installer scripts.)

Q3: Which findings would the code-rules lint (`code_rules_enforcer.py`, run by the staged policy lint and CI) report, and which would only the audit catch because they slip past the lint's patterns? Cite `<file>:<line>` for any audit-only finding so the lint can be tightened later.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket J1-J3 and J5-J12, produce Shape A or Shape B (with at least 3 probes). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Report every finding you reach, including uncertain ones and P2 ones, and give each finding a confidence level (high, medium, or low) beside its severity so a later pass can rank and filter them. Open Questions section for ambiguities. Read-only. No edits, no commits.

Note: most Category J findings are P2 (style / cleanup) since they don't affect runtime behavior.
