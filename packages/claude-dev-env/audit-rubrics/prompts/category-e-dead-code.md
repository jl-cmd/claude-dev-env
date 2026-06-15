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
- Confirm `# noqa` markers: every `# noqa` on an import line must be justified by a specific lint code (e.g., `E402` for module-level imports following a `sys.path` mutation). State the justification.
- Confirm `TYPE_CHECKING` blocks: imports inside `if TYPE_CHECKING:` are referenced only by string-form annotations or runtime `typing.get_type_hints` consumers; verify at least one such consumer or mark the exemption inert.
- Constants-only or re-export-only files (no imports of their own) — state explicitly that there is nothing to sweep.

**E2. Functions / methods defined but never called**
- For every function, method, or callable defined or modified by the artifact, enumerate call sites: direct calls, callback registrations (`onerror=`, `key=`, signal handlers), decorator applications, `__main__` guards, framework-driven discovery (pytest collection, Django URL resolution, FastAPI route decorators, Click groups), and string-form references resolved at runtime (`getattr`, dispatch tables).
- Leading-underscore names: a single internal call site is sufficient; explicitly verify nothing outside the file imports the underscore-prefixed name.
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
- Adversarial probes for proof-of-absence: (a) any test fixture parameter (e.g., `def test_x(tmp_path):`) declared but never used? (b) any non-Python script parameter declared but never referenced? (c) any CLI flag parsed by argparse / Click / Cobra but unreachable on every invocation path the artifact actually uses?

**E6. Removed-but-not-deleted symbol references**
- If the artifact deletes or renames a symbol, confirm every import, call site, string reference, and docstring/comment mentioning the old name has been updated or removed.
- If the artifact is purely additive (no `-` lines outside new files), state this explicitly so the sub-bucket is provably empty rather than skipped.
- Forward references inside the same artifact (file A imports a symbol that the same artifact introduces in file B) are NOT stale; flag the pair so a reader can verify the resolution.
- Adversarial probes for proof-of-absence: (a) does any string literal name a symbol from another module that no longer exists? (b) does any docstring or comment reference a deprecated function? (c) does any external manifest (entry points, route tables, fixture lists) reference a removed symbol?

**E7. Test fixtures / helpers defined but never used**
- For every test file in scope, enumerate `@pytest.fixture`, `@pytest.fixture(scope=...)`, `setUp` / `tearDown` methods, factory helpers, mock builders, and module-level test constants. Verify each has at least one consumer test.
- Module-level constants in test files: each must satisfy the file-global-constants use-count rule (≥2 references) OR be referenced by exactly one test plus one helper that the tests call.
- Helpers defined inside a single test body that are never called within that body are dead.
- Adversarial probes for proof-of-absence: (a) any test that defines a local helper (e.g., `def make_dir(...):`) and never calls it? (b) any imported test name from the production module that no test exercises? (c) any module-level constant whose call graph collapses to zero references after the diff?

**E8. Stub / placeholder code without TODO**
- Distinguish real-behavior `pass` / `continue` / empty-handler bodies (intentional swallowing of expected exceptions, no-op branches that exist to satisfy a contract) from scaffolding stubs.
- Real-behavior bodies do NOT require a TODO; the audit must state the rationale (e.g., "rmdir race with concurrent writer is intentionally swallowed").
- Scaffolding bodies (`pass`, `...`, `raise NotImplementedError`, empty `else { }`, single-statement `return None` placeholders) without a `# TODO` comment ARE Category E findings under the project's "Document Temporary Code" rule.
- Adversarial probes for proof-of-absence: (a) any empty brace block in PowerShell / TypeScript / Go (`{ }` with no statements)? (b) any function whose entire body is `pass` / `return` / `return None`? (c) any branch that exits cleanly only because the surrounding loop is no-op for an empty input — is the no-op intentional or a placeholder?

**E9. Constants-module exports with no importer**
- For every module-level `UPPER_SNAKE` constant the artifact adds to a `*_constants.py` or `config/` module, grep the whole repo for the constant name and locate at least one importer (`from <module> import <NAME>`) or in-file reference.
- The file-global use-count gate exempts a constants module because every name it exports carries zero in-file references by design, so a genuinely dead export slips past the write-time gate; this sub-bucket is the audit-time backstop for that exemption.
- A sibling that a consumer module imports is live; a constant that no `from ... import` line and no in-file reference names anywhere in the repo is dead and must be removed (CODE_RULES 9.8).
- Constants reached only by string-form lookup (`getattr(config, name)`, settings registries) are live; name the dynamic consumer when you mark such a constant referenced.
- Adversarial probes for proof-of-absence: (a) does the artifact add any constant to a `*_constants.py` / `config/` module whose name returns zero hits outside its own definition line? (b) is any newly added constant shadowed by a same-named constant in a sibling module so the importer resolves the other one? (c) does any constant exist only as an `__all__` re-export with no downstream importer of that re-export?

## Cross-bucket questions to answer at the end

Q1: Are there imports unused locally but consumed by a re-export pattern in another file? Cite the cross-file pair if found, or state the hypothesis "none — neither file declares `__all__`" with the supporting evidence.

Q2: What is the worst unused-code hazard introduced by this artifact? Cite `<file>:<line>`. Evaluate candidates by (a) whether the dead branch is unreachable on every code path, (b) whether the dead branch is unreachable only on the dominant invocation path but reachable elsewhere, and (c) whether the symbol is parsed but never consumed. Decide P1 vs P2 explicitly.

Q3: Which symbol most likely will *become* dead code after a near-future refactor? Identify call-graph leaves with a single consumer where the consumer is itself volatile (single-call-site helpers, constants whose only consumer is a flag the team is debating removing, callbacks tied to a library API that may be replaced).

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket E1-E9, produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P2 dead-code instances across these 9 sub-buckets — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

Note: most Category E findings are P2 (style / cleanup) unless the dead code masks an actual bug; the adversarial-pass quota uses P2 here.

---

# Worked example: jl-cmd/claude-code-config PR #394

Audit jl-cmd/claude-code-config PR #394 for **Category E only** (dead code and unused imports). Skip A–D, F–N. Sub-bucket forced-exhaustion mode: Category E is decomposed into 9 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

PR: feat(scripts): add sweep-empty-dirs utility and scheduled-task installer
Head SHA: 62c9c169ee7a44824e5da25c4cf8b74fdca08a53
ID prefix: `find`.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**E1. New imports without references**
- Walk every `import` line introduced by this PR.
- `sweep_empty_dirs.py` imports: `argparse` (line 5), `os` (line 6), `sys` (line 7), `time` (line 8), `from config.sweep_config import DEFAULT_AGE_SECONDS` (line 10), `from config.sweep_config import DEFAULT_POLL_INTERVAL` (line 11). For each, locate at least one body reference: `argparse.ArgumentParser` in `_build_parser`; `os.walk` / `os.path.getctime` / `os.rmdir` / `os.path.isdir` in `sweep` and `main`; `sys.stderr` / `sys.exit` in `_log_walk_error` and `main`; `time.time()` in `sweep` and `time.sleep` in `main`; `DEFAULT_AGE_SECONDS` and `DEFAULT_POLL_INTERVAL` in `_build_parser`'s `default=` kwargs.
- `test_sweep_empty_dirs.py` imports: `datetime` (line 5), `os` (line 6), `subprocess` (line 7), `sys` (line 8), `tempfile` (line 9), `time` (line 10), `from pathlib import Path` (line 11), `from sweep_empty_dirs import sweep` (line 16). For each, locate at least one body reference: `datetime.datetime.fromtimestamp` and `datetime.timezone.utc` in `_set_creation_time_windows`; `os.path.join` / `os.mkdir` / `os.makedirs` / `os.path.isdir` across all five tests; `subprocess.run` in `_set_creation_time_windows`; `sys.path.insert` at lines 13-14; `tempfile.TemporaryDirectory` across all five tests; `time.time()` across multiple tests; `Path(...).write_text` in `test_skips_nonempty_dir` and `Path(__file__)` at line 12; `sweep` across all five tests.
- `__all__` re-exports — neither file defines `__all__`; this exemption is inert.
- `# noqa` markers — exactly one: `from sweep_empty_dirs import sweep  # noqa: E402` (line 16 of test file). Verify the marker is justified by the preceding `sys.path.insert` block (it is — E402 covers module-level import not at top of file, which is exactly what this is).
- `TYPE_CHECKING` blocks — none in either file; exemption inert.
- `config/sweep_config.py` declares two module-level constants and no imports — nothing to sweep here.

**E2. Functions / methods defined but never called**
- `_log_walk_error(os_error: OSError) -> None` (line 14 of `sweep_empty_dirs.py`) — passed as `onerror=` to `os.walk` at line 21. The leading underscore is the only signal that this is a callback rather than a public API; verify no other call sites exist.
- `sweep(root: str, min_age_seconds: int) -> list[str]` (line 18) — called by `main` (line 60, 66) and by every one of the five test functions in `test_sweep_empty_dirs.py`.
- `_build_parser() -> argparse.ArgumentParser` (line 39) — called by `main` at line 51. Single call site; verify nothing in the broader codebase imports `_build_parser` (the leading underscore signals private-by-convention).
- `main() -> None` (line 50) — called by the `if __name__ == "__main__":` block at lines 71-72.
- `_set_creation_time_windows(path: str, timestamp: float) -> None` (line 19 of test file) — called from `test_deletes_empty_dir_older_than_threshold` (line 30), `test_deletes_nested_empty_dirs` (lines 49-51), and `test_empty_root_does_not_crash` (line 60). Three call sites; not dead.
- Each of the five `test_*` functions — called by pytest's collector; verify the file's path matches the project's pytest collection pattern (`scripts/tests/test_*.py`).

**E3. Code after unconditional return / raise / exit**
- `sweep_empty_dirs.py` line 60: `sys.exit(1)` is followed by no statements at the same indentation level inside `main`'s `if not os.path.isdir(...)` block — the `if` body ends and execution flows to the `if arguments.once:` check.
- `sweep_empty_dirs.py` line 64: `return` inside `if arguments.once:` is the last statement of that branch.
- `sweep_empty_dirs.py` line 70: `print("\nstopped.")` is the last statement of the `except KeyboardInterrupt` handler — verify nothing follows at the `try` block's indentation level.
- `sweep_empty_dirs.py` line 72: `main()` is the last statement at module scope after the `if __name__ == "__main__":` guard — nothing follows.
- `Install-SweepEmptyDirs.ps1` lines 27, 44, 53, 62, 69: every `exit 1` and every `return` (lines 38, 44, 49) — verify nothing executable follows at the same scope.
- Adversarial probes for proof-of-absence: (a) is there any `print` or assignment at module scope after `if __name__ == "__main__": main()`? (b) inside `sweep`, after the `except OSError: pass` block at line 30, is there a statement that could only run if the exception handler fell through? (c) the `for` loop at line 21 has no `else:` clause — confirm none was intended.

**E4. Always-true / always-false conditions**
- `sweep_empty_dirs.py` line 67: `while True:` — intentional infinite loop, exited only via `KeyboardInterrupt`. Not dead by E4 standards (it is the canonical watch-loop pattern).
- `sweep_empty_dirs.py` line 26: `if now - created >= min_age_seconds:` — both operands are runtime values; no constant reduction.
- `sweep_empty_dirs.py` line 53: `if not os.path.isdir(arguments.root):` — runtime check, not constant.
- `sweep_empty_dirs.py` line 57: `if arguments.once:` — bound to `--once` switch; runtime.
- `Install-SweepEmptyDirs.ps1` lines 14, 25, 31, 36, 41, 46: each `if (...)` checks a parameter or a `Test-Path` result; none reduces to a constant.
- `test_sweep_empty_dirs.py` line 13: `if str(_SCRIPTS_DIR) not in sys.path:` — runtime membership test; not constant.
- Adversarial probes for proof-of-absence: (a) does the diff introduce any `if 1:` / `if 0:` / `if True:` / `if False:` literals? grep the diff text. (b) any condition of the form `if x:` where `x` was just assigned a literal in the line above? (c) any `assert True` or `assert False` in test bodies? (none — verify).

**E5. Unused parameters and locals**
- `_log_walk_error(os_error: OSError) -> None` (line 14) — parameter `os_error` is read twice in the body (`os_error.filename`, `os_error.strerror`). Used.
- `sweep(root: str, min_age_seconds: int) -> list[str]` (line 18) — `root` is passed to `os.walk` (line 21); `min_age_seconds` is read at line 26. Both used.
- `_build_parser() -> argparse.ArgumentParser` (line 39) — zero parameters; nothing to verify.
- `main() -> None` (line 50) — zero parameters; nothing to verify.
- `_set_creation_time_windows(path: str, timestamp: float) -> None` (line 19 of test file) — `path` interpolated into the PowerShell command (line 22); `timestamp` used at line 20. Both used.
- The `for each_directory_path, _, _ in os.walk(...)` tuple unpack at line 21 of `sweep_empty_dirs.py` — the two `_` placeholders discard `dirnames` and `filenames` from the `os.walk` 3-tuple. This is the standard Python idiom for "this loop only cares about the directory path", not an unused-parameter finding. **E5 specifically scopes "function parameters never read"; tuple-unpack discards are out of scope.**
- No function in this PR accepts `*args` or `**kwargs`.
- Adversarial probes for proof-of-absence: (a) does any test function declare a fixture parameter (e.g., `def test_x(tmp_path):`) that is never used? — none of the five tests use pytest fixtures; they each construct their own `tempfile.TemporaryDirectory()`. (b) does the PowerShell script declare any `param(...)` entry that is never referenced in the body? — `$Target` (used at lines 41-44, 53), `$IntervalMinutes` (used at line 51, 53), `$AgeSeconds` (used at line 50, 53), `$Remove` (used at line 25), `$Status` (used at line 14). All five used. (c) does `New-ScheduledTaskAction -Argument "$ScriptPath --once --age $AgeSeconds ""$Target"""` consume every flag? — `--once`, `--age $AgeSeconds`, and the positional `$Target` map to argparse `args.once`, `args.age`, `args.root` respectively; `args.interval` is NOT passed because `--once` exits before the loop starts. `args.interval` is therefore parsed-but-ignored when invoked through the scheduled task, but it IS used on the manual `python sweep_empty_dirs.py <root>` watch path (line 65, 68). Not dead — used by the non-task code path.

**E6. Removed-but-not-deleted symbol references**
- This PR adds 4 new files; it removes nothing. There is no rename, no deletion, no shim left behind.
- Verify by scanning the diff for any `-` line in any file outside the four new files — the PR's diff scope is purely additive at the file level (every change is `+` against `/dev/null`).
- `from sweep_empty_dirs import sweep` at line 16 of the test file is a forward reference to a symbol the same PR introduces — not a stale reference.
- `from config.sweep_config import DEFAULT_AGE_SECONDS` and `DEFAULT_POLL_INTERVAL` at lines 10-11 of the main script are forward references to symbols this same PR introduces in `config/sweep_config.py` — not stale.
- Adversarial probes for proof-of-absence: (a) does any string in the four files name a symbol from another module that no longer exists? — the only cross-file string references are the import paths above, both of which resolve. (b) does any docstring or comment reference a deprecated function? — no. (c) does the PowerShell `New-ScheduledTaskAction -Execute $PythonPath` reference a python that may not exist? — that is a runtime / installer concern, not a Category E removed-symbol concern; out of scope here.

**E7. Test fixtures / helpers defined but never used**
- `test_sweep_empty_dirs.py` defines no `@pytest.fixture` decorators. Nothing to flag under "fixture with no consumers".
- `_set_creation_time_windows` is the only test helper; it has three call sites (E2 above). Used.
- `_SCRIPTS_DIR` (line 12) is a module-level constant used at line 13 (`if str(_SCRIPTS_DIR) not in sys.path:`) and line 14 (`sys.path.insert(0, str(_SCRIPTS_DIR))`). Two references; satisfies the file-global-constants use-count rule.
- No test data builders or mock factories are defined in this PR.
- Adversarial probes for proof-of-absence: (a) does any of the five tests define a local helper inside its body that is then never called? (e.g., a `def make_dir(...):` defined but unused) — scan each test body. (b) does any test import a name from `sweep_empty_dirs` that it never uses? — only `sweep` is imported, and every test calls it. (c) does the `_SCRIPTS_DIR` block survive if pytest is invoked with `sweep_empty_dirs.py` already on `sys.path`? — yes, the membership-test guards the insert, so the constant is still meaningfully consumed even on the second run.

**E8. Stub / placeholder code without TODO**
- `sweep_empty_dirs.py` line 30: `except OSError: pass` — the `pass` is the entire handler body, intentionally swallowing rmdir failures (e.g., directory became non-empty between the walk and the rmdir, race with another writer). This is a real-behavior `pass`, not a stub. No TODO is required because the handler IS the intended behavior.
- `sweep_empty_dirs.py` line 28: the second `except OSError: continue` similarly is intended behavior (skip the directory whose ctime is unreadable), not a stub.
- No `...` literal anywhere in the four files.
- No `raise NotImplementedError` anywhere.
- No `# TODO` markers in the diff — the project's own rule (`code-standards.md` → "Document Temporary Code") requires TODOs only for scaffolding/placeholder code. The two `pass`/`continue` bodies above are production behavior, not scaffolding.
- Adversarial probes for proof-of-absence: (a) does the PowerShell script have an empty `else { }` or empty branch body? — scan lines 14-71 for any `{ }` with no statements between the braces. (b) does any function body consist of a single `pass` or `return` with no work done? — every function body in this PR performs at least one statement. (c) does the `Status` branch (lines 14-31) exit cleanly even when `$task.Triggers` is empty? — the `foreach` loop at line 26 is a no-op for an empty collection, which is correct behavior, not a stub.

**E9. Constants-module exports with no importer**
- `config/sweep_config.py` is the only constants module this PR adds; it declares `DEFAULT_AGE_SECONDS` and `DEFAULT_POLL_INTERVAL` and imports nothing.
- `DEFAULT_AGE_SECONDS` — imported by `sweep_empty_dirs.py` line 10 (`from config.sweep_config import DEFAULT_AGE_SECONDS`) and read in `_build_parser`'s `--age` default. Live.
- `DEFAULT_POLL_INTERVAL` — imported by `sweep_empty_dirs.py` line 11 and read in `_build_parser`'s `--interval` default. Live.
- Adversarial probes for proof-of-absence: (a) does either constant return zero importers when grepped across the repo? — each has exactly one importer (`sweep_empty_dirs.py`), so neither is dead. (b) is either name shadowed by a same-named constant in a sibling module? — `sweep_config.py` is the only module that declares them. (c) does either constant exist only as an `__all__` re-export with no downstream consumer? — `sweep_config.py` declares no `__all__`; both are imported directly.

## Cross-bucket questions to answer at the end

Q1: Are there imports unused locally but consumed by a re-export pattern in another file? Cite the cross-file pair if found. (Hypothesis: none — neither `sweep_empty_dirs.py` nor `test_sweep_empty_dirs.py` defines `__all__`, so re-export is not in play. `config/sweep_config.py` declares two constants that ARE consumed by `sweep_empty_dirs.py` lines 10-11; this is normal cross-file consumption, not a re-export.)
Q2: What's the worst unused-code hazard introduced by this PR? Cite `<file>:<line>`. Candidates to evaluate: `arguments.interval` is parsed but unreachable on the `--once` path (line 57 short-circuits before the watch loop at line 67); the scheduled task always uses `--once`, so the `--interval` argparse declaration at line 45 is dead code on the only invocation path the installer creates. Decide: P2 (style) because the manual watch-mode path still uses it, vs P1 if you treat "the only installer path never exercises this branch" as functionally dead.
Q3: Which symbol most likely will *become* dead code after a near-future refactor? Candidates: `_log_walk_error` (sole call site is the `os.walk(..., onerror=...)` kwarg — if a future refactor switches to `pathlib.Path.rglob` for walking, this helper has no other consumer and silently becomes orphaned); `DEFAULT_POLL_INTERVAL` (sole consumer is `_build_parser`'s `--interval` default — if Q2's hazard is resolved by removing `--interval` from the `--once`-only installer flow, this constant has zero consumers in the script and the file-global-constants use-count rule is broken).

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket E1-E9, produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P2 dead-code instances across these 9 sub-buckets — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

Note: most Category E findings are P2 (style / cleanup) unless the dead code masks an actual bug; the adversarial-pass quota uses P2 here.

## Diff (4 new files, all lines in scope)

### packages/claude-dev-env/scripts/sweep_empty_dirs.py (102 lines)
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

### packages/claude-dev-env/scripts/config/sweep_config.py (11 lines)
```python
"""Centralized timing configuration for sweep_empty_dirs."""

DEFAULT_AGE_SECONDS: int = 120
DEFAULT_POLL_INTERVAL: int = 30
```

### packages/claude-dev-env/scripts/tests/test_sweep_empty_dirs.py (88 lines)
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

### packages/claude-dev-env/scripts/Install-SweepEmptyDirs.ps1 (90 lines)
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
