Audit [REPO/ARTIFACT] [TARGET_ID] for **Category J only** (CODE_RULES.md compliance). Skip A–I, K–N. Sub-bucket forced-exhaustion mode: Category J is decomposed into 12 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA]
- Artifact: [PR title / commit subject / file set / patch series]
- Head SHA / Revision: [SHA or revision identifier]
- Scope: [files / line ranges / packages in scope]
- Languages in scope: [e.g., Python, PowerShell, TypeScript]
- Production vs test split: [explicit list of which files are production and which are test files; test files are exempt from most J sub-buckets]

ID prefix: `find`.

## Source material

Inline the artifact (full diff or full file contents) under a clearly delimited block below this section. Use the chunking guide in [`../source-material-section-types.md`](../source-material-section-types.md) to choose the right Source-material section type (full-diff, file-set, patch-series, or excerpt-with-context). Mark every line range that is in scope; mark explicitly which files are test files (exempt) and which are production.

Replace this paragraph with the chunked source material before issuing the prompt.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**J1. Magic values in production function bodies**
- Walk every numeric or non-trivial literal other than `0`, `1`, `-1` inside production function bodies.
- Test files are exempt. Module-level declarations are J3-scope, not J1-scope.
- For each literal found, decide: structural value that belongs in `config/` (flag) vs. truly local arithmetic constant tied to the line's logic (defendable).
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

**J4. File-global use-count**
- For every file-global constant outside `config/`, count references in the same file. Single ref → move to `config/`. Zero refs → delete.
- The rule applies to *constants*, not functions, classes, or imports.
- Adversarial probes: (a) is any imported constant referenced only once in the importing file (suggesting the import itself is gratuitous)? (b) is any helper function defined in a production file but never called from inside the same file (separate dead-code concern, surfaced here for completeness)? (c) does any constant in `config/` get imported from zero call sites across the repo?

**J5. Abbreviations**
- Walk every parameter, local, and attribute name in production code. Flag: `ctx`, `cfg`, `msg`, `btn`, `idx`, `cnt`, `elem`, `val`, `tmp`, `str`, `num`, `arr`, `obj`, `fn`, `cb`, `req`, `res`. Loop counters `i`/`j`/`k` and `e` for exceptions are exempt.
- Test files are exempt.
- Adversarial probes: (a) is there a borderline name (e.g., `removed`, `arguments`) that someone might mis-classify as an abbreviation but is actually a full English word? Confirm. (b) does any callback / parameter / attribute use a short variant of a domain term that is technically a full word but conventionally abbreviates a longer one? (c) does any variable in a comprehension or lambda use a single letter outside the `i`/`j`/`k`/`e` exemption?

**J6. Vague names**
- Flag any name from the vague list: `result`, `data`, `output`, `response`, `value`, `item`, `temp`, `info`, `stuff`, `thing`. Vague verb prefixes for function names: `handle`, `process`, `manage`, `do`.
- Test files are exempt.
- Adversarial probes: (a) does any local variable use a domain-adjacent name that is actually on the vague list (e.g., `result` from a parser, `data` from a fetch)? (b) does any newly-introduced function name start with a vague prefix? (c) does any public attribute / dict key use a vague label that the call site has to disambiguate by surrounding context?

**J7. Type hints**
- Walk every function in production files. Verify parameter and return types are present, no `Any`, no `# type: ignore`.
- Test files are exempt.
- Adversarial probes: (a) does any production function rely on inferred return type from a single `return` path? (b) does any parameter use a string-quoted forward reference that masks `Any`? (c) is there a `# type: ignore` anywhere? Grep the diff explicitly.

**J8. New inline comments**
- Every `#` or `//` comment line **added** by this diff in production code — flag, except for exempt markers (shebangs, `# type:`, `# noqa`, `# pylint:`, `# pragma:`, `// @ts-`, `// eslint-`, `// prettier-`, `/// `).
- Module/function/class docstrings are always allowed.
- Existing comments are NEVER removed (Comment Preservation rule); if the diff removes an existing comment, that is a separate violation outside J8 (also blocked by the hook).
- Test files are exempt.
- Adversarial probes: (a) is there any `# type:` or marker comment that is actually inert prose rather than a real type-checker / linter directive? (b) is any docstring carrying inline-comment content (line-level explanations rather than module/function description)? (c) does any newly-added blank line between code stanzas function as a comment substitute, suggesting the author wanted to add a comment but couldn't?

**J9. Logging format**
- Walk every `log_*(...)` call. Must be `log_*("template with {}", arg)`, not `log_*(f"...")`.
- The rule applies to the project's structured `log_*` family, not stdlib `print`. `print` f-strings are J2-scope (string-template magic), not J9-scope.
- Test files are exempt.
- Adversarial probes: (a) is there any imported `log_*` function in production code that uses an f-string? (b) is there a logger-equivalent call (e.g., `logger.info(f"...")` from `logging` stdlib) that should be subject to the same rule? (c) does any non-Python logger family (e.g., `console.log`, `Write-Host`, structured-log helpers) appear with a template-string pattern that mirrors the J9 anti-pattern?

**J10. Imports inside functions**
- Every `import` / `from ... import ...` statement — verify at module scope.
- Test files: deferred imports after a `sys.path.insert(0, ...)` guard at module scope are allowed (documented circular-import-style workaround).
- Adversarial probes: (a) is there any lazy `import` inside a production function body? (b) does any conditional `import` (e.g., inside `if TYPE_CHECKING:`) escape into runtime accidentally? (c) does any non-Python language analog (e.g., `require(...)` inside a JS function, `Import-Module` inside a PowerShell `if` branch) appear in production code?

**J11. sys.path.insert dedup**
- Every `sys.path.insert(0, X)` must be guarded by `if X not in sys.path:` (or equivalent membership test).
- Test files are explicitly in scope for J11 (the rule that always applies even to test files).
- Adversarial probes: (a) is the guard expression semantically equivalent to `if X not in sys.path:` where `X` is exactly the value being inserted (no string/Path mismatch)? (b) is there a second `sys.path` mutation elsewhere in the file that is not guarded? (c) would importing the module twice (e.g., via test collection re-runs) re-trigger the insert?

**J12. Hardcoded user paths**
- Any string literal containing `C:/Users/<name>/...`, `/Users/<name>/...`, `/home/<name>/...` in production code? Use `pathlib.Path.home()` or `os.path.expanduser('~')`.
- Exempt: test files, `config/` files, workflow registry paths (`/workflow/`, `_tab.py`, `/states.py`, `/modules.py`), Django migrations (`/migrations/`), and hook infrastructure.
- Adversarial probes: (a) does any error message, help string, or docstring example embed a `C:/Users/...`, `/home/...`, or `/Users/...` example? Grep the diff. (b) does any scheduled-task / launcher / installer artifact hardcode a path that should be derived from `$PSCommandPath`, `__file__`, or `os.getcwd()`? (c) does any docstring example show a user-specific home, even if the runtime code itself is path-clean?

## Cross-bucket questions to answer at the end

Q1: Are there literals or names that span two sub-buckets (e.g., a magic value in J1 that also appears inside an f-string scrutinized by J2; an UPPER_SNAKE in J3 that also fails the use-count test in J4)? Cite the literal/name and both sub-bucket IDs.

Q2: What is the worst CODE_RULES drift introduced by this artifact? Cite `<file>:<line>`. (Common candidates: cross-language duplicates, stale help text mirroring a config constant, abbreviations in a public API surface, bare `Any` annotations, hardcoded user paths in installer scripts.)

Q3: Which findings would `code_rules_enforcer.py` block at write time, vs. which would only be caught by audit (slipping past the hook's pattern)? Cite `<file>:<line>` for any audit-only finding so the hook can be tightened later.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket J1–J12, produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1–Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P2 CODE_RULES violations across these 12 sub-buckets — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

Note: most Category J findings are P2 (style / cleanup) since they don't affect runtime behavior; the adversarial-pass quota uses P2 here.

---

# Worked example: jl-cmd/claude-code-config PR #394

Audit jl-cmd/claude-code-config PR #394 for **Category J only** (CODE_RULES.md compliance). Skip A–I, K–N. Sub-bucket forced-exhaustion mode: Category J is decomposed into 12 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

PR: feat(scripts): add sweep-empty-dirs utility and scheduled-task installer
Head SHA: 62c9c169ee7a44824e5da25c4cf8b74fdca08a53
ID prefix: `find`.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**J1. Magic values in production function bodies**
- Walk every numeric literal other than `0`, `1`, `-1` in production function bodies in `sweep_empty_dirs.py` (lines 73-135) and `Install-SweepEmptyDirs.ps1` (lines 227-302). Test file lines 147-223 are exempt.
- Python side: `sweep(...)` body (lines 80-98) and `main()` body (lines 113-131) — the visible numbers `0` (in tuple unpacking `for each_directory_path, _, _`) and `1` (in `sys.exit(1)`) are exempt by the `0`, `1`, `-1` rule. Assert no other numeric literal appears.
- PowerShell side: `Install-SweepEmptyDirs.ps1` line 233 (`[int]$IntervalMinutes = 5`), line 236 (`[int]$AgeSeconds = 120`), line 297 (`-Daily -At "00:00"` — string but the `5` and `120` defaults are numeric). Both `5` and `120` are bare literals in the param block. Note: `120` is already centralized as `DEFAULT_AGE_SECONDS` in `config/sweep_config.py` (line 142) — flag the PowerShell duplicate as J1 magic-value, with the cross-language drift framed in Category K.
- Adversarial probes: (a) is `5` (line 233) the same value as any constant in `config/sweep_config.py`? (b) is `00:00` a structural literal that belongs in config? (c) is `120` (line 236) duplicated against `DEFAULT_AGE_SECONDS` (sweep_config.py:142)?

**J2. String-template magic**
- Walk every f-string in `sweep_empty_dirs.py`. Strip the `{...}` interpolations and inspect the remaining literal text. Flag only when the residue is structural (paths, URLs, regex, command patterns).
- Line 74 — `f"warning: cannot scan {os_error.filename} — {os_error.strerror}"` → residue `"warning: cannot scan  — "` is descriptive output, not structural. Not flagged.
- Line 93 — `f"deleted: {each_directory_path}"` → residue `"deleted: "` is a log prefix, not structural. Not flagged.
- Line 105 — `f"Minimum age in seconds (default: {DEFAULT_AGE_SECONDS} = 2 minutes)"` → residue `"Minimum age in seconds (default:  = 2 minutes)"` is help text, not structural. Not flagged. (However: the embedded number `2` in `"= 2 minutes"` is a magic-numeric-literal-inside-help-text — adversarial probe candidate.)
- Line 109 — `f"Poll interval in seconds when looping (default: {DEFAULT_POLL_INTERVAL})"` → residue is help text, not structural. Not flagged.
- Line 118 — `f"error: not a directory: {arguments.root}"` → residue is descriptive, not structural. Not flagged.
- Line 125 — `f"watching {arguments.root} every {arguments.interval}s (age threshold: {arguments.age}s)"` → residue is descriptive, not structural. Not flagged.
- Adversarial probes: (a) is the `"= 2 minutes"` substring in line 105 a hidden duplicate of `DEFAULT_AGE_SECONDS = 120`? If a future change makes the default 180s, the help text will silently lie. (b) does any f-string concatenate a path that should come from config? (c) does any literal repeat across both Python and PowerShell that would belong in shared config?

**J3. Constants location**
- Walk every module-level `UPPER_SNAKE = ...` declaration in production files.
- `sweep_empty_dirs.py` (lines 61-136) — no module-level UPPER_SNAKE declarations. Both `DEFAULT_AGE_SECONDS` (line 69) and `DEFAULT_POLL_INTERVAL` (line 70) are *imports*, not declarations; the canonical home is `config/sweep_config.py:142-143`. Verified clean.
- `config/sweep_config.py` (lines 138-144) — `DEFAULT_AGE_SECONDS: int = 120` (line 142) and `DEFAULT_POLL_INTERVAL: int = 30` (line 143) live in `config/`. Exempt by the `config/*` path family.
- Test file `test_sweep_empty_dirs.py` line 160 — `_SCRIPTS_DIR = Path(__file__).resolve().parent.parent` is *not* UPPER_SNAKE (leading underscore + mixed case); even if it were UPPER_SNAKE, test files are exempt by the rule.
- `Install-SweepEmptyDirs.ps1` line 245 — `$TaskName = "SweepEmptyDirs"` is a PowerShell variable; J3 enforces Python module-level UPPER_SNAKE outside `config/`. PowerShell out of scope for J3.
- Adversarial probes: (a) does any module-level constant in `sweep_empty_dirs.py` masquerade as an "import"? (b) is there any `_PRIVATE_UPPER` declaration that escapes the visual UPPER_SNAKE filter? (c) does the test file accidentally declare a constant that *would* be flagged if it were in production?

**J4. File-global use-count**
- For every file-global constant outside `config/`, count references in the same file. Single ref → move to `config/`. Zero refs → delete.
- `sweep_empty_dirs.py` — no file-global constants declared (`DEFAULT_AGE_SECONDS` and `DEFAULT_POLL_INTERVAL` are imports). Imports follow standard import-usage rules, not the file-global use-count rule.
- `config/sweep_config.py:142-143` — `DEFAULT_AGE_SECONDS` and `DEFAULT_POLL_INTERVAL` live in `config/`, exempt by location.
- Test file `_SCRIPTS_DIR` — test files exempt.
- Adversarial probes: (a) is any imported constant in `sweep_empty_dirs.py` referenced only once (line 104 for `DEFAULT_AGE_SECONDS`, line 108 for `DEFAULT_POLL_INTERVAL`) — wait, `DEFAULT_AGE_SECONDS` is referenced TWICE on line 104 (`default=DEFAULT_AGE_SECONDS`) and line 105 (`f"...default: {DEFAULT_AGE_SECONDS} = 2 minutes"`); `DEFAULT_POLL_INTERVAL` is referenced TWICE on line 108 and line 109. Both meet the ≥2-references threshold (note: file-global use-count technically applies to declarations, not imports — listed here for completeness). (b) is any helper function in `sweep_empty_dirs.py` defined but never called from inside the file? `_log_walk_error` (line 73) is referenced once at line 84; `_build_parser` (line 101) is referenced once at line 114. The use-count rule applies to *constants*, not functions, so neither is flagged. (c) does any constant in `config/sweep_config.py` get imported from zero call sites?

**J5. Abbreviations**
- Walk every parameter, local, and attribute name in `sweep_empty_dirs.py`.
- `_log_walk_error(os_error: OSError)` — `os_error` is full word, not `e` (exception loop var allowed but not required). Verified clean.
- `sweep(root: str, min_age_seconds: int) -> list[str]` — `root` is a domain term, `min_age_seconds` is fully spelled. Not abbreviated. Verified clean.
- Loop var `each_directory_path` (line 83) — follows the `each_` prefix convention. Not abbreviated.
- `_, _` in tuple unpacking (line 83) — discard names, exempt.
- `removed: list[str]` (line 81) — full word. Not abbreviated.
- `_build_parser() -> argparse.ArgumentParser` — `parser` is full word, not `p`. Verified clean.
- `main()` parameter `parser` (line 114), `arguments` (line 115) — full word `arguments`, not `args`. Verified clean.
- Test file `test_sweep_empty_dirs.py` — exempt (test files).
- Adversarial probes: (a) does `removed` count as the abbreviation list? `removed` is a past-participle verb, not on the abbreviation list. (b) does `tmp` (test file line 178) count? Test files exempt. (c) does `dt` (test file line 168) count as `datetime` abbreviation? Test files exempt.

**J6. Vague names**
- Flag any name from the vague list: `result`, `data`, `output`, `response`, `value`, `item`, `temp`, `info`, `stuff`, `thing`. Vague verb prefixes: `handle`, `process`, `manage`, `do`.
- `sweep_empty_dirs.py` — variable `removed: list[str]` (line 81) is domain-specific (what was removed from disk), not vague. `now` (line 80) is a time concept, not on the vague list. `created` (line 87) is a domain timestamp, not vague.
- Function names: `sweep`, `_log_walk_error`, `_build_parser`, `main` — none use the vague verb prefixes (`handle`, `process`, `manage`, `do`). `sweep` is concrete domain action.
- Test file — exempt.
- Adversarial probes: (a) does `removed` (line 81) overlap with the vague-name list? It does not — the list is `result`, `data`, `output`, etc., and `removed` is none of those. (b) is `arguments` (line 115) on any vague list? No — `arguments` is the argparse-namespace canonical name. (c) does any callback parameter use a vague name? `_log_walk_error(os_error)` — `os_error` is concrete. Clean.

**J7. Type hints**
- Walk every function in production files. Verify parameter and return types are present, no `Any`, no `# type: ignore`.
- `_log_walk_error(os_error: OSError) -> None` (line 73) — parameter typed, return typed. Clean.
- `sweep(root: str, min_age_seconds: int) -> list[str]` (line 77) — both parameters typed, return typed. Clean.
- `_build_parser() -> argparse.ArgumentParser` (line 101) — no parameters, return typed. Clean.
- `main() -> None` (line 113) — no parameters, return typed. Clean.
- `config/sweep_config.py:142-143` — `DEFAULT_AGE_SECONDS: int = 120`, `DEFAULT_POLL_INTERVAL: int = 30`. Both annotated. Clean.
- Test file `test_sweep_empty_dirs.py` — exempt by test-file rule (the helper `_set_creation_time_windows(path: str, timestamp: float) -> None` at line 167 is annotated anyway, and `test_*() -> None` functions are all annotated).
- Adversarial probes: (a) does any production function rely on inferred return type from a single `return` path? All four production functions have explicit return annotations. (b) does any parameter use a string-quoted forward reference that masks `Any`? No — all annotations are direct. (c) is there a `# type: ignore` anywhere? Grep the diff: no occurrences.

**J8. New inline comments**
- Every `#` comment line added by this diff in production code — flag, except for exempt markers (shebangs, `# type:`, `# noqa`, `# pylint:`, `# pragma:`).
- `sweep_empty_dirs.py` — line 61 (`#!/usr/bin/env python3`) is a shebang, exempt. Line 62 is a module-level docstring, allowed. Lines 78 and 102 are function docstrings, allowed. No inline `#` comments. Clean.
- `config/sweep_config.py` — line 140 is a module-level docstring. No inline comments. Clean.
- Test file — exempt.
- `Install-SweepEmptyDirs.ps1` — line 227 (`#!/usr/bin/env pwsh`) is a shebang, exempt. No inline `#` comments added in the PowerShell file. Clean.
- Adversarial probes: (a) is there any `# type:` comment that is actually inert noise rather than a type-checker directive? No occurrences in the diff. (b) is any docstring carrying inline-comment content as line-level explanations rather than module/function description? Module docstring on line 62 is one line ("Delete empty directories older than 2 minutes under a given root."); function docstrings on 78 and 102 are one-liners. Clean. (c) does any newly-added blank line between code stanzas function as a comment substitute? Visual whitespace is allowed.

**J9. Logging format**
- Walk every `log_*(...)` call. Must be `log_*("template with {}", arg)`, not `log_*(f"...")`.
- `sweep_empty_dirs.py` uses `print()`, not a logger. The rule applies to `log_*` (the project's structured logger), not stdlib `print`. The print f-strings on lines 74, 93, 118, 125, 131 are J2-scope (string-template magic), not J9-scope.
- Test file — exempt.
- Adversarial probes: (a) is there any imported `log_*` function in `sweep_empty_dirs.py` that uses an f-string? No — no logger import in the diff. (b) is `print(..., file=sys.stderr)` (lines 74, 118) a logger-equivalent call that should be subject to J9? No — `print` is stdlib stdout/stderr, not the structured-logger family. (c) does the PowerShell `Write-Host` / `Write-Error` family count? J9 is Python-specific (`log_*` callable convention).

**J10. Imports inside functions**
- Every `import` / `from ... import ...` statement — verify at module scope.
- `sweep_empty_dirs.py` lines 64-70 — all imports at module top. Function bodies (lines 73-135) contain no `import` statements. Clean.
- `config/sweep_config.py` — no imports. Clean.
- Test file — exempt; nevertheless lines 152-158 are all module-scope imports, line 164 is a deferred import (`from sweep_empty_dirs import sweep  # noqa: E402`) at module scope after the `sys.path.insert` guard. Documented circular-import-style workaround pattern; allowed.
- Adversarial probes: (a) is there any lazy `import` inside `sweep`, `main`, or `_build_parser` body? No occurrences. (b) is `argparse.ArgumentParser` accessed via `argparse.ArgumentParser` (line 102) using the module-scope import on line 64? Yes. (c) does the PowerShell file have any `Import-Module` calls inside `if` branches? No — the script imports nothing.

**J11. sys.path.insert dedup**
- Every `sys.path.insert(0, X)` must be guarded by `if X not in sys.path:`. Test files exempt by general-rule but J11 is the rule that explicitly applies to test files.
- `test_sweep_empty_dirs.py` lines 160-162 — `_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / if str(_SCRIPTS_DIR) not in sys.path: / sys.path.insert(0, str(_SCRIPTS_DIR))`. Guarded. Clean.
- No `sys.path.insert` calls in production files.
- Adversarial probes: (a) is the guard expression `if str(_SCRIPTS_DIR) not in sys.path:` semantically equivalent to `if X not in sys.path:` where `X` is exactly the value being inserted? Yes — both use `str(_SCRIPTS_DIR)`. (b) is there a second `sys.path` mutation elsewhere in the test file that's not guarded? No — only one occurrence at line 162. (c) would importing the test module twice (e.g., via pytest's collection re-runs) re-trigger the insert? The guard prevents it. Clean.

**J12. Hardcoded user paths**
- Any string literal containing `C:/Users/<name>/...`, `/Users/<name>/...`, `/home/<name>/...`?
- `sweep_empty_dirs.py` — no hardcoded user paths. The `arguments.root` value is supplied at runtime via argparse positional argument (line 103). Clean.
- `config/sweep_config.py` — no paths at all. Clean.
- Test file — exempt; uses `tempfile.TemporaryDirectory()` (lines 178, 188, 197, 210, 216) which is the canonical safe pattern. Clean.
- `Install-SweepEmptyDirs.ps1` — `$ScriptDir = Split-Path -Parent $PSCommandPath` (line 272), `$ScriptPath = Join-Path $ScriptDir "sweep_empty_dirs.py"` (line 273). Both derive from `$PSCommandPath` (the script's own path), not a hardcoded user home. Clean. The `$Target` parameter is supplied at install time (line 230); not hardcoded.
- Adversarial probes: (a) does any error message or help string embed a `C:/Users/...` example? Grep the diff for `C:/Users`, `/home/`, `/Users/` — no occurrences. (b) does the scheduled task `-Argument` string at line 296 hardcode a path? It interpolates `$ScriptPath`, `$AgeSeconds`, and `$Target` — all dynamic. Clean. (c) does any docstring example show a user-specific home? Module docstrings on lines 62 and 140 are short and contain no example paths. Clean.

## Cross-bucket questions to answer at the end

Q1: Are there constants that span two sub-buckets (e.g., a magic value J1 inside an f-string J2 — the same literal flagged twice)? Cite the literal and both sub-bucket IDs.
Q2: What's the worst CODE_RULES drift introduced by this PR? Cite `<file>:<line>`. (Hint: cross-language `120` duplication between PowerShell line 236 and Python `config/sweep_config.py:142` is the load-bearing one — it's a J1 magic value on the PowerShell side and a Category K conflict-with-existing-code on the cross-language side.)
Q3: Which finding would `code_rules_enforcer.py` block at write time, vs. which would only be caught by audit (slipping past the hook's pattern)? Cite the file:line for any audit-only finding.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket J1-J12, produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P2 CODE_RULES violations across these 12 sub-buckets — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

Note: most Category J findings are P2 (style / cleanup) since they don't affect runtime behavior; the adversarial-pass quota uses P2 here.

## Diff (4 new files, all lines in scope)

### packages/claude-dev-env/scripts/sweep_empty_dirs.py
```python
#!/usr/bin/env python3
"""Delete empty directories older than 2 minutes under a given root."""

import argparse
import os
import sys
import time

from config.sweep_config import DEFAULT_AGE_SECONDS
from config.sweep_config import DEFAULT_POLL_INTERVAL


def _log_walk_error(os_error: OSError) -> None:
    print(f"warning: cannot scan {os_error.filename} — {os_error.strerror}", file=sys.stderr)


def sweep(root: str, min_age_seconds: int) -> list[str]:
    """Remove empty directories under *root* older than *min_age_seconds*."""

    now = time.time()
    removed: list[str] = []

    for each_directory_path, _, _ in os.walk(
        root, onerror=_log_walk_error, topdown=False
    ):
        try:
            created = os.path.getctime(each_directory_path)
        except OSError:
            continue
        if now - created >= min_age_seconds:
            try:
                os.rmdir(each_directory_path)
                print(f"deleted: {each_directory_path}")
                removed.append(each_directory_path)
            except OSError:
                pass

    return removed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Delete empty directories older than a given age.")
    parser.add_argument("root", help="Root directory to scan")
    parser.add_argument("--age", type=int, default=DEFAULT_AGE_SECONDS,
                        help=f"Minimum age in seconds (default: {DEFAULT_AGE_SECONDS} = 2 minutes)")
    parser.add_argument("--once", action="store_true",
                        help="Single pass and exit instead of watching in a loop")
    parser.add_argument("--interval", type=int, default=DEFAULT_POLL_INTERVAL,
                        help=f"Poll interval in seconds when looping (default: {DEFAULT_POLL_INTERVAL})")
    return parser


def main() -> None:
    parser = _build_parser()
    arguments = parser.parse_args()

    if not os.path.isdir(arguments.root):
        print(f"error: not a directory: {arguments.root}", file=sys.stderr)
        sys.exit(1)

    if arguments.once:
        sweep(arguments.root, arguments.age)
        return

    print(f"watching {arguments.root} every {arguments.interval}s (age threshold: {arguments.age}s)")
    try:
        while True:
            sweep(arguments.root, arguments.age)
            time.sleep(arguments.interval)
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
```

### packages/claude-dev-env/scripts/config/sweep_config.py
```python
"""Centralized timing configuration for sweep_empty_dirs."""

DEFAULT_AGE_SECONDS: int = 120
DEFAULT_POLL_INTERVAL: int = 30
```

### packages/claude-dev-env/scripts/tests/test_sweep_empty_dirs.py
```python
"""Tests for sweep_empty_dirs.py"""

from __future__ import annotations

import datetime
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from sweep_empty_dirs import sweep  # noqa: E402


def _set_creation_time_windows(path: str, timestamp: float) -> None:
    dt = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
    date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    subprocess.run(
        ["powershell", "-Command",
         f"(Get-Item '{path}').CreationTimeUtc = [DateTime]'{date_str}'"],
        check=True, capture_output=True,
    )


def test_deletes_empty_dir_older_than_threshold() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        empty_dir = os.path.join(tmp, "old_empty")
        os.mkdir(empty_dir)
        _set_creation_time_windows(empty_dir, time.time() - 300)
        removed = sweep(tmp, min_age_seconds=120)
        assert empty_dir in removed
        assert not os.path.isdir(empty_dir)


def test_skips_empty_dir_newer_than_threshold() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        fresh_dir = os.path.join(tmp, "fresh_empty")
        os.mkdir(fresh_dir)
        removed = sweep(tmp, min_age_seconds=120)
        assert fresh_dir not in removed
        assert os.path.isdir(fresh_dir)


def test_deletes_nested_empty_dirs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        leaf = os.path.join(tmp, "parent", "child", "leaf")
        os.makedirs(leaf)
        _set_creation_time_windows(os.path.join(tmp, "parent"), time.time() - 300)
        _set_creation_time_windows(os.path.join(tmp, "parent", "child"), time.time() - 300)
        _set_creation_time_windows(leaf, time.time() - 300)
        removed = sweep(tmp, min_age_seconds=120)
        assert leaf in removed
        assert os.path.join(tmp, "parent", "child") in removed
        assert os.path.join(tmp, "parent") in removed


def test_empty_root_does_not_crash() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _set_creation_time_windows(tmp, time.time() - 300)
        sweep(tmp, min_age_seconds=120)


def test_skips_nonempty_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        nonempty_dir = os.path.join(tmp, "has_stuff")
        os.mkdir(nonempty_dir)
        Path(nonempty_dir, "keepme.txt").write_text("hello")
        removed = sweep(tmp, min_age_seconds=0)
        assert nonempty_dir not in removed
        assert os.path.isdir(nonempty_dir)
```

### packages/claude-dev-env/scripts/Install-SweepEmptyDirs.ps1
```powershell
#!/usr/bin/env pwsh
param(
    [Parameter(ParameterSetName = "install")]
    [string]$Target,

    [Parameter(ParameterSetName = "install")]
    [int]$IntervalMinutes = 5,

    [Parameter(ParameterSetName = "install")]
    [int]$AgeSeconds = 120,

    [Parameter(ParameterSetName = "remove")]
    [switch]$Remove,

    [Parameter(ParameterSetName = "status")]
    [switch]$Status
)

$TaskName = "SweepEmptyDirs"

if ($Status) {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $task) {
        Write-Host "STATUS: $TaskName is not registered."
        return
    }
    Write-Host "STATUS: $TaskName is registered."
    Write-Host "  State: $($task.State)"
    Write-Host "  Actions:"
    foreach ($action in $task.Actions) {
        Write-Host "    $($action.Execute) $($action.Arguments)"
    }
    Write-Host "  Triggers:"
    foreach ($trigger in $task.Triggers) {
        Write-Host "    $($trigger.Repetition.Interval) (starting $($trigger.StartBoundary))"
    }
    return
}

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "$TaskName removed."
    return
}

$ScriptDir = Split-Path -Parent $PSCommandPath
$ScriptPath = Join-Path $ScriptDir "sweep_empty_dirs.py"

if (-not (Test-Path $ScriptPath)) {
    Write-Error "sweep_empty_dirs.py not found at: $ScriptPath"
    exit 1
}

if (-not $Target) {
    Write-Error "Parameter -Target is required (the directory to watch)."
    exit 1
}

if (-not (Test-Path $Target)) {
    Write-Error "Target directory does not exist: $Target"
    exit 1
}

$_py = Get-Command py -ErrorAction SilentlyContinue
$PythonPath = if ($_py) { $_py.Source } else { (Get-Command python).Source }
if (-not $PythonPath) {
    Write-Error "Cannot find Python (py or python) on PATH."
    exit 1
}
$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument "$ScriptPath --once --age $AgeSeconds ""$Target"""
$Trigger = New-ScheduledTaskTrigger -Daily -At "00:00" -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null
Write-Host "$TaskName registered — runs every ${IntervalMinutes}min against '$Target' (age ≥ ${AgeSeconds}s)."
```
