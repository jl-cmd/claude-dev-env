Audit [REPO/ARTIFACT] [TARGET_ID] for **Category D only** (variable scoping, ordering, and unbound references). Skip A–C, E–P. Sub-bucket forced-exhaustion mode: Category D is decomposed into 8 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA]
- Repo / artifact: [REPO_OR_ARTIFACT]
- Target ID: [TARGET_ID] (e.g., PR number, commit SHA, file path, document name)
- Head SHA / revision: [HEAD_SHA_OR_REVISION]
- Title / summary: [TITLE]
- Files / sections in scope: [LIST_OF_PATHS_OR_SECTIONS]

ID prefix: `find`.

Line-number convention: every `:N` reference points to the file-relative line number of the file inlined in `## Source material` further down. A line citation is verifiable iff the cited number is present in the corresponding file fence below.

## Source material

Inline the artifact under audit using one `###` header per section. Pick the chunk size per the [chunking guide](../source-material-section-types.md): one file per section for code PRs, one function/class per section for long single-module audits, one named heading per section for design docs, etc. Keep section anchors stable and copy-pasteable so findings can cite `<section>:<line>` unambiguously.

```
## Source material ([N] sections, all lines in scope)

### [section-1-anchor]
```[language]
[content]
```

### [section-2-anchor]
```[language]
[content]
```
```

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**D1. Variable referenced before assignment on a branch**
- Identify every name that is assigned on only some branches of an `if`/`elif`/`else`, `try`/`except`/`else`/`finally`, or `match` block, then read after the block. Cite each binding site and each read site by `<section>:<line>`.
- For each `try:` block whose `except` arm uses `continue` / `return` / `raise` / `sys.exit` to short-circuit, prove the read site is unreachable on the failure path. Replace `continue` mentally with `pass` and check whether the next read becomes unbound — that is the adversarial probe.
- Walk every loop, comprehension, and generator and confirm names that are only bound conditionally inside the loop body are not read after the loop terminates with zero iterations (e.g., `for x in xs: ...` followed by `return x` when `xs` may be empty).
- Confirm parameters and locals introduced at the top of a function are bound on every code path that reaches their first read (early-return guards, exception handlers, parser-driven `SystemExit`).

**D2. Loop closure capture (by-ref vs by-value)**
- Walk every `for` / `while` loop body and list any `lambda`, nested `def`, list/dict/set/generator comprehension that defers evaluation, `functools.partial`, `asyncio.create_task`, `threading.Thread`, `multiprocessing` worker, or `concurrent.futures.submit` that closes over the loop variable.
- For language-specific late-binding hazards (Python `lambda` capturing by reference, JavaScript `var` in a `for` loop, PowerShell `ForEach-Object { ... }` script blocks vs `foreach` statement), state which language semantics apply and probe whether the captured name is consumed in the same iteration or stored for later.
- Confirm callbacks registered with event loops, signal handlers, or scheduler hooks do not retain stale references to per-iteration state.

**D3. Name shadowing of outer-scope symbols**
- Enumerate every parameter and local name introduced in each function, then check it against (a) language builtins, (b) module-level imports, (c) class-level attributes still in use within the function. Cite each candidate by `<section>:<line>`.
- For names that are intentionally similar to imported modules (e.g., a parameter named `path` in a file that also imports `pathlib.Path`), confirm the function body resolves the imported symbol correctly at every call site.
- Probe loop / comprehension variables that share a name with an outer-scope symbol the surrounding function still relies on after the loop.
- For shell / scripting languages with implicit pipeline variables (PowerShell `$_`, Bash `$_`, `$@`), verify locally introduced names do not collide with those automatic variables.

**D4. Conditional definition leaving a symbol undefined**
- Find every `try: import X / except ImportError:` block, `if sys.platform == "..."` guard, version-conditional fallback, or feature-flag gate that binds a symbol on only some configurations. For each, cite the binding line and every read site that may execute when the guard is false.
- For installer / orchestration scripts that define variables only on one parameter-set branch (e.g., PowerShell `param(...)` sets, argparse subcommands), confirm every read site is reachable only from a branch where the variable was bound. Trace from each early `return` / `exit` upward.
- Confirm there are no platform-conditional `def` statements that leave a function name unbound on the non-matching platform.

**D5. Mutable default arguments**
- Walk every `def` (and language-equivalent: JavaScript default parameters with object/array literals, Ruby keyword defaults, etc.) and confirm no parameter has a mutable literal as its default — `[]`, `{}`, `set()`, `OrderedDict()`, `dict()` with no args, custom dataclass instances.
- For each `def` with a default argument, state whether the default is immutable (numeric, string, `None`, `tuple()`, `frozenset()`) or potentially mutable. Cite each by `<section>:<line>`.
- Probe-of-absence: state the count "0 across all [N] sections" and list every `def` walked.

**D6. Module-level circular imports / load order**
- For each module imported by the artifact under audit, confirm the import graph has no cycle that could leave a symbol partially bound. Cite every `from X import Y` line.
- Check for runtime `sys.path` mutations or `importlib` calls that occur after a top-level `from ... import`. Confirm the sequence cannot leave a name unbound (the `from` either succeeds and binds the name or raises and aborts module load).
- Identify any import-time side effects (top-level function calls, decorator-driven registration, `__init_subclass__` hooks) that depend on partial-module state.

**D7. Async/sync ordering of side effects**
- Scan the entire artifact for `async def`, `await`, `asyncio.gather` / `asyncio.create_task` / `asyncio.run`, JavaScript `async` / `await` / `Promise.all`, or any other deferred-execution primitive. If any are present, walk the ordering of side effects.
- For each `await` site, identify whether a side effect that should have happened *before* the suspension point is flushed before yielding control. Probe what an interleaved coroutine could observe.
- For purely synchronous artifacts, cite proof-of-absence with explicit keyword counts ("0 occurrences of `async`, `await`, `asyncio` across all [N] sections").

**D8. Class-attribute vs instance-attribute confusion**
- For every `class` definition, list each attribute introduced in the class body (class attribute) versus inside `__init__` / `__post_init__` / a factory classmethod (instance attribute). Cite each by `<section>:<line>`.
- For each method, walk every `cls.x` and `self.x` access and confirm the access kind matches the attribute's binding site. Probe whether mutation of a class-level mutable (e.g., `cls.cache = {}` shared across instances) is intended or accidental.
- For artifacts with no `class` definitions, cite proof-of-absence by scanning every section for the `class ` keyword and stating the count.

## Cross-bucket questions to answer at the end

Q1: Is there any sub-bucket overlap — i.e., a single line that triggers more than one of D1–D8 simultaneously (e.g., a name that is both shadowed AND only conditionally bound)? Cite every overlapping site by `<section>:<line>` for each bucket it implicates.

Q2: What is the worst unbound-reference hazard a future refactor could introduce by editing the highest-risk loop or branch in the artifact? Name the specific line and the minimal one-token change (e.g., replacing `continue` with `pass`, moving a check above its `try:`, extracting a nested helper) that would convert a currently-clean call into an unbound-name error.

Q3: Among all variables read in the artifact's main entry point or top-level function, which one's binding context is most fragile to the addition of a new flag, parameter, or conditional branch — i.e., which one would silently become read-before-assigned if a maintainer wrapped its assignment in a new `if`? Name the line and the hypothetical branch.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket D1-D8, produce Shape A or Shape B (with at least 3 probes). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Report every finding you reach, including uncertain ones and P2 ones, and give each finding a confidence level (high, medium, or low) beside its severity so a later pass can rank and filter them. Open Questions section for ambiguities. Read-only. No edits, no commits.
