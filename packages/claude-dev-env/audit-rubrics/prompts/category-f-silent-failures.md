Audit [REPO/ARTIFACT] [TARGET_ID] for **Category F only** (silent failures). Skip A–E, G–P. Sub-bucket forced-exhaustion mode: Category F is decomposed into 10 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA]
- Title / short description: [TITLE]
- Revision identifier (commit SHA, doc version, transcript date, etc.): [REVISION_ID]
- Scope note (what is in vs out of scope): [SCOPE_NOTE]

ID prefix: `find`.

## Source material

Inline the artifact under audit here, broken into named sections. A "section" is the natural chunk you'd quote and reference back to when reporting a finding — pick the chunk size that lets a finding cite `[section name]:[line/paragraph N]` unambiguously. See the chunking guide at `../source-material-section-types.md` for the lookup table (code PR → one file per section; long module → one function per section; design doc → one heading per section; etc.) and the rule of thumb for monolithic artifacts ("impose your own breaks at logical hinge points and label them: `### lines 1–40 (parameter parsing)`").

Use one `###` header per section so each chunk is independently citable:

```
### [section identifier — e.g. relative file path, function name, heading title, clause number]
[content of that section, in a fenced block when it is code/config]
```

Repeat for every section in scope.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**F1. Catch-all except clauses**
- Locate every bare `except:`, `except Exception:`, `except BaseException:` (and language-equivalents: PowerShell `try { } catch { }` with no type filter, JS `catch (e) {}`, Go `_ = err`, Rust `let _ = result`).
- For each, classify the body: `pass` / `continue` / log-only / re-raise. Only re-raise (or a documented benign-case-with-trace) is compliant.
- For the swallowing variants, enumerate which exception subclasses the protected call raises and identify which are failures vs benign known cases (e.g., for `os.rmdir`: `FileNotFoundError`, `PermissionError`, `NotADirectoryError`, `OSError(ENOTEMPTY)`, `OSError(EBUSY)` — only `ENOTEMPTY` is benign).
- Check for asymmetry: do two error handlers in the same module disagree on whether to log? A handler that logs to stderr next to one that silently swallows is a Category F smell even when each is locally defensible.
- Check for double-swallow: does an outer callback (e.g. `os.walk(..., onerror=...)`) already report errors that an inner `except` then swallows again?

**F2. Errors logged then swallowed**
- Every `logger.error(...)` / `print(..., file=sys.stderr)` / `Write-Warning` / `console.error(...)` followed by `return None` / `return default` / fall-through with no re-raise.
- Verify the caller chain: is the logged error observable to a human? Logs that go to stderr but the caller never inspects exit code or status output are still effectively swallowed at the system boundary.
- Asymmetric narration: is the success path loud (`print("deleted: X")`) and the failure path silent? Either both should narrate or neither should.
- For library callbacks whose return value the stdlib explicitly ignores (e.g. `os.walk`'s `onerror`), trace whether the log-then-return is the only signal upward — if so, downstream status/exit-code reporting must also reflect that errors occurred.

**F3. Default fallback values masking failure**
- `dict.get(key, default)` where the absence of the key is itself a bug.
- Stale-payload-key shape: for each external-input dict (`*_payload`, event, request, parsed-JSON body), list every string-literal key read from it. Check each key against the contract the module's docstring and its other reads set up — a payload whose other reads bind to same-named variables and whose docstring names a key set is an established contract. Flag a lone read of a key outside that contract: it resolves to the `.get` default on every payload and silently records an empty value into the field it feeds. A key consumed inline with a meaningful default (`resolve(payload.get("cwd", "."))`) is legitimate; the flag is the dropped key whose value the consuming field needs but never receives.
- `or default` short-circuits hiding `None` returns from fallible calls.
- `getattr(obj, attr, default)` masking `AttributeError` from the wrong object type.
- argparse `default=...` for values that should fail-loud when absent.
- Loop iterators that return empty on permission/IO errors (e.g. `os.walk` on an unreadable root) and let the function return successfully with no work done — verify the watcher does not silently sweep nothing forever.
- Type coercion that accepts nonsensical values: `[int]$X` accepts `0` and negative numbers silently; absence of `[ValidateRange(...)]` / explicit bounds checking is the F3 hazard.
- Re-validation cadence: if a startup guard (`if not os.path.isdir(root): sys.exit(1)`) runs once but the protected resource can disappear mid-run, the guard's success becomes an F3 fallback for every subsequent iteration.

**F4. Async task error swallowing**
- `asyncio.create_task(...)` without exception observation (no `.add_done_callback`, no later `await`).
- `asyncio.gather(..., return_exceptions=True)` where the returned exceptions are not inspected.
- `Thread(target=...)` with no `join()` or no exception forwarding.
- `multiprocessing.Pool.apply_async` without `.get()` or error callback.
- JS `Promise` not awaited and no `.catch(...)`.
- PowerShell `Start-Job`, `Start-ThreadJob`, `Invoke-Command -AsJob` without `Receive-Job -Wait` or job-state inspection.
- External-async equivalents that count as Shape B candidates: scheduled tasks (Windows Task Scheduler, cron) whose `LastTaskResult` / exit code is never read by an operator-facing tool. Probes for that case: does the installer's `-Status` flow surface `LastTaskResult`? Does the success message lie when the underlying registration emitted a non-terminating warning piped to `Out-Null`? Does the long-running loop body handle SIGTERM / scheduler shutdown distinctly from KeyboardInterrupt?

**F5. Status returns identical on success and failure**
- Functions returning `bool` / `int` / `list` / `Optional[T]` where the same value (`True`, `0`, `[]`, `None`) appears on the happy path AND inside a catch-all error branch.
- Distinguish "no work to do" (legitimate empty) from "work attempted but every step silently failed" (F5 hazard) — if the caller cannot tell these apart from the return value, that is a finding.
- Process-level F5: does the program exit 0 after a long run that silently failed every operation? Compare the exit code on Ctrl+C-after-success vs Ctrl+C-after-all-failures.
- Callback-level F5: stdlib callbacks whose return value is contractually ignored (e.g. `os.walk`'s `onerror` returns `None`) are immune to F5 — book that as a clarification, not a finding.

**F6. Ignored return values from fallible calls**
- `subprocess.run(...)` without `check=True` AND no manual `.returncode` inspection.
- `os.write`, `os.read`, `socket.send`, `socket.recv` whose short-write/short-read return values are discarded.
- File-handle methods (`f.write`) whose returned byte count is not checked when partial writes are possible (Windows pipes, network sockets).
- PowerShell pipelines piped to `| Out-Null` that may be hiding a non-terminating warning.
- Functions that return a status object alongside a side effect — verify the side effect's success is the contract and the discarded return is informational only.
- Exception-only contracts (e.g. `os.rmdir` returns `None`, raises on failure) belong under F1, not F6 — note the cross-reference rather than double-booking.

**F7. PowerShell error-suppression patterns**
- `-ErrorAction SilentlyContinue` followed by `.Property` / `.Method` access on a possibly-`$null` result. Compliant only when an explicit `if ($result)` guard runs before the property access.
- `-ErrorAction Ignore` (stronger than SilentlyContinue — does not even populate `$Error`).
- `2>$null`, `*>$null`, `$ErrorActionPreference = 'SilentlyContinue'` mutations.
- `$?` not consulted after a native-binary call where exit code matters.
- The opposite hazard: a fallback path that drops `-ErrorAction SilentlyContinue` from a `Get-Command` (or similar) call where the `$null` was the entire contract — produces a terminating error on the path that was supposed to be silent-then-handled-by-the-next-line.
- Semantic-success-but-functional-failure: `Get-Command` finds the Microsoft Store stub `python.exe` whose `.Source` resolves but whose execution opens the Store. The cmdlet did not error, but the resolved interpreter cannot run code. Verify whether scripts validate that resolved paths do their job.
- Mismatched user-facing messages: a `-Remove` / `-Uninstall` flow that prints "X removed." regardless of whether anything was unregistered.

**F8. Test-level swallowing**
- `try/except` / `try/catch` inside a test body that catches and logs instead of asserting. Tests must fail loudly when their target raises.
- `pytest.warns` used where `pytest.raises` was the contract.
- Tests asserting only on the success path with no negative-space coverage of the swallowed-error branch.
- Tests whose name encodes an assertion ("does not crash") but whose body asserts nothing — the test passes incidentally and would also pass if the function silently failed every operation.
- Coverage gaps for known F1 / F2 / F6 swallowing branches: if the audited code has `except OSError: pass`, is there a test that exercises that branch and verifies the post-conditions (e.g. directory still present, no log line emitted)?
- Test fixtures using `subprocess.run(..., check=True)` are compliant — the exception path is the contract.

**F9. Gate-validator self-defeat via parse-failure swallow**
- Locate every `ast.parse` / `tokenize` / `json.loads` / `yaml.safe_load` call inside gate / validator / hook code that parses the audited input as code or structured data.
- For each, classify the catch branch: does it return `[]` / `None` / `True` (a clean signal) on parse failure? A clean-signal default masks the gate being broken — the check fires zero findings whenever the parse fails.
- Trace what the dispatcher feeds the check: when the dispatcher passes a partial fragment (e.g., the Edit tool's `new_string` rather than the full file content), the parse fails on every Edit and the check is dead in production while its tests pass against full-file fixtures.
- Adversarial probes: (a) feed the check a syntactically incomplete fragment and confirm whether the catch branch returns a clean signal; (b) compare the content surface the test fixtures use against the content surface the dispatcher supplies at runtime; (c) verify the catch branch distinguishes "input is clean" from "input could not be parsed" — a single clean-signal return for both is an F9 finding.

**F10. Guard helper returns success-default on unverifiable input**
- Locate every guard helper / predicate / classifier that decides whether to allow or block, and inspect the path taken when it cannot validate the input shape (missing positional args, wrong arity, unexpected `None`, malformed payload).
- Flag any guard that short-circuits to `True` / `Ok` / the success sentinel on unverifiable input. Guards must default-deny when they cannot verify; default-allow on unverifiable input lets violations through downstream.
- Adversarial probes: (a) construct an input that fails the guard's shape check and confirm whether the guard returns allow or deny; (b) supply `None` / missing args / wrong arity and trace the return; (c) verify the guard's "cannot verify" branch is distinct from its "verified clean" branch — collapsing both into a success return is an F10 finding.

## Cross-bucket questions to answer at the end

Q1: Are there error paths that span two sub-buckets (e.g., an F1 catch-all whose result feeds into an F5 status-equivalence — same return value regardless of how many silent failures occurred)?
Q2: What's the worst silent-failure hazard introduced by this artifact? Cite `[section]:[line]`. Justify against P0/P1 severity using observable user impact (e.g., a watcher that runs forever and never makes progress because of a permissions issue, with no log line indicating why).
Q3: Where would a future error-handling refactor most likely *introduce* a silent failure? Name the line(s) most fragile — for instance, adding a top-level `try/except` around a long-running loop body to "make it more resilient" can convert the only loud failure (top-level crash) into a silent infinite-loop-of-nothing.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket F1-F10, produce Shape A or Shape B (with at least 3 probes). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Report every finding you reach, including uncertain ones and P2 ones, and give each finding a confidence level (high, medium, or low) beside its severity so a later pass can rank and filter them. Open Questions section for ambiguities. Read-only. No edits, no commits.
