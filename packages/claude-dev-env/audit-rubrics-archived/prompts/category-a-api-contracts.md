Audit [REPO/ARTIFACT] [TARGET_ID] for **Category A only** (API contract verification). Skip B–P. Sub-bucket forced-exhaustion mode: Category A is decomposed into 9 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA: title / change description / head SHA or revision identifier / scope summary]
ID prefix: `find`.

## Source material ([N] files/sections, all lines in scope)

[INLINE THE FULL ARTIFACT HERE — see ../source-material-section-types.md for chunking guidance.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**A1. Function/method signatures vs internal call sites**
- Enumerate every defined function or method's parameter list: count, names, defaults, kw-only barriers (Python `*`), positional-only barriers (`/`), variadic markers (`*args`, `**kwargs`).
- For every internal call within the artifact, verify the binding matches the callee's signature: positional count, keyword names, required-vs-optional, default fall-through.
- Flag positional arguments passed to keyword-only parameters and vice versa.
- Flag calls that omit a required parameter relying on a default that does not exist on the current branch.
- Verify decorators (`@staticmethod`, `@classmethod`, `@property`) do not silently shift the parameter binding (e.g., `self` / `cls` insertion).
- Confirm sync-vs-async (is the symbol `async def`?), the exact access path a caller uses (free function vs instance method via an object attribute vs import path), and that a keyword-only parameter with no default is required — omitting it raises `TypeError`.
- When a call passes a config value as an argument, confirm the value's documented role matches the parameter's role (poll interval vs timeout vs budget). A poll interval such as `PollingIntervals.resume_check` handed to a `progress_check_timeout` parameter type-checks but carries the wrong meaning.

**A2. Return-type annotation vs every code path**
- For each annotated function, walk every code path: explicit `return X`, fall-through to implicit `None`, exception-handler exit, generator `yield` paths, async coroutine return value.
- Verify each path's return value is assignable to the declared annotation; flag `-> bool` functions that can return `None`, `-> list[T]` functions that can return `None` on an early exit, etc.
- For functions that raise instead of returning on some path, confirm the annotation does not promise a value the caller will dereference.
- Inspect `try/except/finally` chains for paths that return from `finally` and override `try`/`except` returns.
- For async functions, confirm the annotation refers to the awaited type, not the coroutine wrapper.
- The full failure contract is the return value AND every exception raised — list each `raise` in the body and the docstring `Raises:`; a `-> bool` that can also raise is not fully described as "returns bool".

**A3. CLI/argument-parser declaration → downstream Namespace contract**
- For every `add_argument(...)` (or equivalent CLI declaration), verify the auto-derived or explicit `dest=` matches the attribute name accessed downstream on the parsed namespace.
- Verify `type=` (or schema coercion) matches every downstream consumer's expectation — e.g., a value handed to a function requiring `int` is declared `type=int`, not the default `str`.
- Switch flags (`action="store_true"` / `store_false`) produce booleans; non-switch arguments produce typed values; flag the mismatch where a switch is treated as a value or vice versa.
- Default values resolve correctly when the flag is omitted; flag any code path that assumes the user supplied the argument.
- Required-vs-optional declaration matches the downstream code's null-handling.

**A4. Stdlib/library callback contracts**
- Identify every callback handed to a library function (e.g., `os.walk(onerror=...)`, sort `key=`, `filter`, `map`, `re.sub(repl=callable)`, signal handlers, threading callbacks). Verify each callback's signature matches what the library calls it with — arity, positional-vs-keyword, return type the library consumes.
- For every stdlib function the artifact calls, verify argument types and exception contracts: which exceptions can each call raise, and is each caller prepared (or deliberately not prepared) for them.
- Verify kwargs to stdlib functions are spelled correctly for the targeted runtime version (deprecated/renamed kwargs, version-introduced kwargs).
- Catch-site precision — for any "catches X" claim confirm the exact catch site and scope (an `except` around only a rollback inside `finally` does not catch the same error from the `with` body).
- Flag callbacks whose return value the library consumes but the implementation returns `None` (or vice versa).
- Confirm callback exception behavior: which exceptions in the callback bubble out, which are swallowed by the library, which terminate iteration.

**A5. Subprocess / external-process invocation contract**
- For every `subprocess.run` / `subprocess.Popen` / equivalent call, verify the `args` shape: list-of-strings vs single string vs `shell=True` semantics.
- Verify kwargs are valid for the targeted runtime version (`capture_output`, `text`, `encoding`, `check`, `timeout`); flag combinations that conflict (`stdout=PIPE` + `capture_output=True`).
- Exception contract under `check=True` (raises `CalledProcessError` on non-zero exit) — verify callers either propagate or handle, with no silent swallow that masks failure.
- Verify quoting/escaping of arguments crossing the subprocess boundary, especially when interpolating untrusted strings.
- Verify the resolved executable path exists on the target platform, not assumed (`which` / `Get-Command` failure paths).

**A6. Shell/host-language cmdlet or function parameter sets and binding**
- For every shell or host-language function/cmdlet declaration with parameter sets (PowerShell `param(...)` with `ParameterSetName=`, Bash `getopts`, etc.), verify the declaration matches every invocation pattern. Confirm a default parameter set is declared if no-arg invocation is reachable.
- For every cmdlet/builtin invocation, verify the parameter combination is valid per the cmdlet's documented parameter sets — flag combinations that mix flags from disjoint parameter sets.
- Flag missing `-ErrorAction` (or equivalent) declarations on calls whose null-checks downstream assume swallowed errors.
- Verify each cmdlet/builtin argument's type coercion at the boundary matches what the cmdlet expects.
- Confirm pipeline-bound parameters (`ValueFromPipeline`, `ValueFromPipelineByPropertyName`) match what upstream emits.

**A7. Cross-language / cross-process argv and serialization boundary**
- Trace every value crossing a language or process boundary (shell argv → Python `sys.argv`, environment variables, JSON/IPC payloads, file-format round-trips). Verify the producer's serialization matches the consumer's parser.
- Flag trailing-backslash, embedded-space, embedded-quote, and Unicode hazards on Windows argv composition (Microsoft C-runtime argv parser rules) and POSIX shell word-splitting.
- Verify argument-order conventions match across the boundary — e.g., flag order, positional placement, separator handling (`--`).
- Cross-language default-value drift: a default declared on one side that differs from the default on the other side; verify either both are sourced from a single config or both are intentionally mirrored.
- Cross-language type drift: integer width, signed/unsigned, floating-point precision, string encoding (UTF-8 vs UTF-16), null/empty-string semantics.

**A8. Documented API/tool calls vs official API documentation**
- For every API call, MCP tool invocation, CLI command, or SDK method call documented in the source material, identify the provider.
- Look up the official documentation for that API (Context7 MCP for libraries/SDKs, API reference docs for REST endpoints, tool definitions in session for MCP calls, `--help` for CLI tools).
- Verify the documented parameter names, types, and required-ness match the official API signature.
- For read-only API calls, execute one safe invocation to confirm the documented shape succeeds in practice.
- For write calls, verify the signature against the provider's own published API contract — their REST reference docs, OpenAPI spec, SDK source code, or `--help` output. When a read endpoint exposes the same state, call it to confirm the write contract.
- Flag every call where documented parameters, types, or behavior diverge from the official API contract.

**A9. Intra-module sibling-helper API parity**
- Did the diff add a new check / validator / parser / handler alongside existing sibling helpers in the same module? Verify the new one matches the sibling cohort's signature — every parameter the peer checks accept (e.g., `all_changed_lines` for diff-line filtering).
- Verify the new helper's scoping semantics match the cohort: whole-file vs fragment content surface, diff-line filtering, and `defer_scope_to_caller` handling.
- Verify the new helper's result-shape contract matches: where the result cap is applied (pre-scope vs post-scope), whether `defer_scope_to_caller=True` is honored, and the return type.
- When the new helper omits a sibling-accepted parameter, runs on a different content surface than its siblings, or applies the result cap at a different point in the pipeline, name it as an A9 finding. Cite the new helper and the sibling it diverges from as the pair.
- For a pure-code artifact with no new sibling helper, A9 is one line of proof-of-absence (the diff adds no helper alongside an existing cohort).

### Documentation as contract (when the artifact asserts facts about the code)

When the artifact is documentation that asserts facts about the codebase (symbol names, signatures, return types, exceptions, file paths), run all seven documentation-as-contract checks below; each yields a confirmation or a finding. For a pure-code artifact, this section is one line of proof-of-absence (the artifact asserts no code facts).

- Full failure contract — the failure signals of a function are its return value AND every exception it raises; trace the body and the docstring `Raises:` for every `raise`. _Example:_ a docs PR says a UI helper "returns `bool`", but it also raises a custom not-found error, so "returns bool" understates the contract.
- Call shape — required versus optional parameters (a keyword-only parameter with NO default is required; omitting it raises `TypeError`), sync versus async, and the exact access path (free function versus instance method reached through an object attribute versus import path). _Example:_ a doc presents a helper as a free function, but it is an `async` instance method reached through an object attribute, so the doc's call example would raise `TypeError`.
- Reuse-first — before a doc endorses a hand-written snippet, search for a dedicated helper that already does it. _Example:_ a doc endorses hand-composing `normalize(name).lower()` inline while a dedicated `normalize_for_matching()` helper already does exactly that.
- Path resolution — every file or directory path a doc cites resolves from the repository root. _Example:_ a doc cites a bare `snapshots/` directory as if it sat at the repo root, but the tree lives under `subsystem/snapshots/`.
- Cross-entry consistency — scan parallel rows, sections, and table entries for claims that contradict each other. _Example:_ two adjacent table rows map the same subsystem to two different exception base classes.
- Catch-site precision — when a doc claims code "catches X", confirm the exact site and scope of the catch. _Example:_ a doc says a context manager catches a driver error, but the `except` wraps only the rollback inside `finally`, so an error raised in the `with` body propagates uncaught.
- Citation freshness — re-derive every `file:line` claim against the current code; never trust a prior "verified" assertion or wording borrowed from a comment. _Example:_ an attribute name carried over from a review comment names a member the class does not define; the current code exposes it under a different name.

## Cross-bucket questions to answer at the end

Q1: Are there any contracts that span two sub-buckets that single-bucket analysis would miss?
Q2: What is the worst contract-drift hazard introduced by this artifact? Cite file:line.
Q3: Where would a future refactor most likely break a cross-bucket or cross-language contract? Name the line(s) most fragile.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket A1-A9, produce Shape A or Shape B (with at least 3 adversarial probes). Documentation-as-contract: when the artifact asserts code facts, walk all seven checks and report each as a finding or a confirmation; for a pure-code artifact, one line of proof-of-absence. Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Report every finding you reach, including uncertain ones and P2 ones, and give each finding a confidence level (high, medium, or low) beside its severity so a later pass can rank and filter them. Open Questions section for ambiguities. Read-only. No edits, no commits.
