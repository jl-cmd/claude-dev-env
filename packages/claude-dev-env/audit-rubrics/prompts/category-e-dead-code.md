Audit [REPO/ARTIFACT] [TARGET_ID] for **Category E only** (dead code and unused imports). Skip A–D, F–P. Sub-bucket forced-exhaustion mode: Category E is decomposed into 9 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA]
- Repo / artifact: [REPO_OR_ARTIFACT_NAME]
- Target ID: [PR_NUMBER / COMMIT_SHA / FILE_SET / TICKET_ID]
- Title / summary: [SHORT_DESCRIPTION]
- Head SHA / revision: [REVISION_IDENTIFIER]
- Languages in scope: [PYTHON / TYPESCRIPT / POWERSHELL / GO / ...]

ID prefix: `find`.

## Source material

Inline the artifact under this section using the section types defined in the chunking guide (`../source-material-section-types.md`). For Category E, every line of the artifact that introduces or modifies imports, function definitions, control-flow exits, conditionals, parameter lists, or test fixtures must be in scope. Mark out-of-scope blocks (vendored code, generated files, third-party snapshots) explicitly so the audit walk does not flag them.

[INLINE THE DIFF / FILE BODIES / SNIPPET HERE — one fenced block per file or per logical unit, with file path and line numbers preserved.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**E1. New imports without references**
- Walk every `import` line introduced or modified by the artifact. For each, locate at least one body reference in the same file (function call, attribute access, type annotation, decorator, default-argument expression).
- Confirm `__all__` re-exports: if the file declares `__all__`, an import that appears only in `__all__` still counts as referenced; if no `__all__` is declared, the exemption is inert and must be stated as such.
- Confirm changed `# noqa` directives are removed or resolved. Leave directives on untouched lines outside the change scope.
- Confirm `TYPE_CHECKING` blocks: imports inside `if TYPE_CHECKING:` are referenced only by string-form annotations or runtime `typing.get_type_hints` consumers; verify at least one such consumer or mark the exemption inert.
- Constants-only or re-export-only files (no imports of their own) — state explicitly that there is nothing to sweep.

**E2. Functions / methods defined but never called**
- For every function, method, or callable defined or modified by the artifact, enumerate call sites: direct calls, callback registrations (`onerror=`, `key=`, signal handlers), decorator applications, `__main__` guards, framework-driven discovery (pytest collection, Django URL resolution, FastAPI route decorators, Click groups), and string-form references resolved at runtime (`getattr`, dispatch tables).
- Leading-underscore names: a single internal call site is enough; explicitly verify nothing outside the file imports the underscore-prefixed name.
- Public names: confirm at least one call site inside or outside the file, or confirm the function is part of a documented public API.
- Framework-discovered callables (test functions, route handlers, CLI commands): state which collector picks them up and confirm the artifact's path matches that collector's pattern.

**E3. Code after unconditional return / raise / exit**
- For every `return`, `raise`, `sys.exit`, `os._exit`, PowerShell `exit`, `throw`, Go `panic`, JavaScript `throw` introduced or modified by the artifact, verify nothing executable follows at the same indentation / brace level.
- Confirm `for ... else` and `while ... else` clauses: an `else` after a loop runs only when the loop completes without `break`; verify the absence-or-presence is intentional.
- Confirm `try / except / finally` flow: code after a fully-exhaustive `try` whose every branch returns or raises is unreachable.
- Module-scope tail: nothing should follow `if __name__ == "__main__": main()` at module scope.
- Adversarial probes for proof-of-absence: (a) any statement at module scope after the `__main__` guard? (b) any statement after a `pass` or `continue` that could only run if the exception handler fell through? (c) any loop with an `else:` clause that was not intended?

**E4. Always-true / always-false conditions**
- Walk every `if`, `elif`, `while`, ternary, and short-circuit expression introduced or modified by the artifact.
- Intentional infinite loops (`while True:` watch loops, event loops) are NOT dead by E4 standards; flag the pattern explicitly so a reader understands why it is exempt.
- Runtime-bound conditions (parameter values, `os.path.isdir`, `Test-Path`, environment lookups) are not constant; state the runtime source.
- Adversarial probes for proof-of-absence: (a) any `if 1:` / `if 0:` / `if True:` / `if False:` literals in the diff? (b) any condition of the form `if x:` where `x` was just assigned a literal in the line above? (c) any `assert True` / `assert False` in test bodies? (d) any short-circuit like `x or DEFAULT` where `x` was just constructed and is statically truthy?

**E5. Unused parameters and locals**
- For every function or method introduced or modified by the artifact, verify each declared parameter is read at least once in the body (including in default-argument expressions for inner functions, in closures, or in type guards).
- For every function or method introduced or modified by the artifact, verify each local variable assigned in the body is read at least once afterward in the same scope; an assignment whose value is never read is a dead local.
- Tuple-unpack discards (`for path, _, _ in os.walk(...)`) are out of scope — E5 specifically scopes "function parameters never read"; state this exclusion explicitly.
- `*args` / `**kwargs` / TypeScript rest spreads: confirm at least one consumer (forwarded to another call, iterated, indexed) or mark the parameter unused.
- Cross-language parameter declarations (PowerShell `param(...)`, shell positional `$1..$N`, Bash `getopts`): confirm each named parameter has at least one body reference.
- Adversarial probes for proof-of-absence: (a) any test fixture parameter (e.g., `def test_x(tmp_path):`) declared but never used? (b) any non-Python script parameter declared but never referenced? (c) any CLI flag parsed by argparse / Click / Cobra but unreachable on every invocation path the artifact uses?

**E6. Removed-but-not-deleted symbol references**
- If the artifact deletes or renames a symbol, confirm every import, call site, string reference, and docstring/comment mentioning the old name has been updated or removed.
- If the artifact is purely additive (no `-` lines outside new files), state this explicitly so the sub-bucket is provably empty rather than skipped.
- Forward references inside the same artifact (file A imports a symbol that the same artifact introduces in file B) are NOT stale; flag the pair so a reader can verify the resolution.
- Adversarial probes for proof-of-absence: (a) does any string literal name a symbol from another module that no longer exists? (b) does any docstring or comment reference a deprecated function? (c) does any external manifest (entry points, route tables, fixture lists) reference a removed symbol?

**E7. Test fixtures / helpers defined but never used**
- For every test file in scope, enumerate `@pytest.fixture`, `@pytest.fixture(scope=...)`, `setUp` / `tearDown` methods, factory helpers, mock builders, and module-level test constants. Verify each has at least one consumer test.
- Module-level constants in test files: each must be referenced by at least two callers, OR by exactly one test plus one helper that the tests call.
- Helpers defined inside a single test body that are never called within that body are dead.
- Adversarial probes for proof-of-absence: (a) any test that defines a local helper (e.g., `def make_dir(...):`) and never calls it? (b) any imported test name from the production module that no test exercises? (c) any module-level constant whose call graph collapses to zero references after the diff?

**E8. Stub / placeholder code without tracking**
- Distinguish real-behavior `pass` / `continue` / empty-handler bodies (intentional swallowing of expected exceptions, no-op branches that exist to satisfy a contract) from scaffolding stubs.
- Real-behavior bodies need no source-code marker; the audit must state the rationale (e.g., "rmdir race with concurrent writer is intentionally swallowed").
- Scaffolding bodies (`pass`, `...`, `raise NotImplementedError`, empty `else { }`, single-statement `return None` placeholders) are Category E findings. Judge the stub itself; track follow-up work outside source code.
- Adversarial probes for proof-of-absence: (a) any empty brace block in PowerShell / TypeScript / Go (`{ }` with no statements)? (b) any function whose entire body is `pass` / `return` / `return None`? (c) any branch that exits cleanly only because the surrounding loop is no-op for an empty input — is the no-op intentional or a placeholder?

**E9. Constants-module exports with no importer**
- For every module-level `UPPER_SNAKE` constant the artifact adds to a `*_constants.py` or `config/` module, grep the whole repo for the constant name and locate at least one importer (`from <module> import <NAME>`) or in-file reference.
- Every name a constants module exports carries zero in-file references by design and no write-time check reads such a module, so a dead export reaches the audit untouched; this sub-bucket is the audit-time backstop.
- A sibling that a consumer module imports is live; a constant that no `from ... import` line and no in-file reference names anywhere in the repo is dead and must be removed (CODE_RULES 9.8).
- Constants reached only by string-form lookup (`getattr(config, name)`, settings registries) are live; name the dynamic consumer when you mark such a constant referenced.
- Adversarial probes for proof-of-absence: (a) does the artifact add any constant to a `*_constants.py` / `config/` module whose name returns zero hits outside its own definition line? (b) is any newly added constant shadowed by a same-named constant in a sibling module so the importer resolves the other one? (c) does any constant exist only as an `__all__` re-export with no downstream importer of that re-export?

## Cross-bucket questions to answer at the end

Q1: Are there imports unused locally but consumed by a re-export pattern in another file? Cite the cross-file pair if found, or state the hypothesis "none — neither file declares `__all__`" with the supporting evidence.

Q2: What is the worst unused-code hazard introduced by this artifact? Cite `<file>:<line>`. Evaluate candidates by (a) whether the dead branch is unreachable on every code path, (b) whether the dead branch is unreachable only on the dominant invocation path but reachable elsewhere, and (c) whether the symbol is parsed but never consumed. Decide P1 vs P2 explicitly.

Q3: Which symbol most likely will *become* dead code after a near-future refactor? Identify call-graph leaves with a single consumer where the consumer is itself volatile (single-call-site helpers, constants whose only consumer is a flag the team is debating removing, callbacks tied to a library API that may be replaced).

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket E1-E9, produce Shape A or Shape B (with at least 3 probes). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Report every finding you reach, including uncertain ones and P2 ones, and give each finding a confidence level (high, medium, or low) beside its severity so a later pass can rank and filter them. Open Questions section for ambiguities. Read-only. No edits, no commits.

Note: most Category E findings are P2 (style / cleanup) unless the dead code masks a bug.
