Audit [REPO/ARTIFACT] [TARGET_ID] for **Category M only** (producer/consumer cardinality vs collection-type contract). Skip A–L, N–P. Sub-bucket forced-exhaustion mode: Category M is decomposed into 8 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA — include both producer signature and every consumer call site so cardinality contracts can be compared end-to-end]

- Title / one-line summary: [TITLE]
- Head ref / SHA at audit time: [HEAD_SHA]
- Producer functions (file + line range + symbol name + return type annotation): [PRODUCER_FUNCTIONS]
- Consumer call sites (every site that receives the producer's return value, with file:line and the operation applied to the value): [CONSUMER_CALL_SITES]
- Subprocess invocations the producer depends on (when M1 is in play): [SUBPROCESS_CALLS]
- Stated intent of the producer (what set-semantics or list-semantics the author claims): [INTENT]

ID prefix: `find`.

[ONE-PARAGRAPH FRAME: name each producer function under audit, state its declared return type (`list[X]`, `Sequence[X]`, `Iterable[X]`, `frozenset[X]`, `dict[K, V]`), and name every consumer call site that receives the producer's return value. State the audit goal: for each producer/consumer pair, verify that the consumer's cardinality assumption matches the producer's emission contract — specifically, that no consumer treats a duplicate-possible producer as a set, and no consumer that requires order receives a set.]

## Source material ([N] files/sections, all lines in scope)

[INLINE the producer function source. INLINE every consumer call site with enough context to show what the consumer does with the producer's return value (subscript, iterate, build a dict, build a set, INSERT into a database, accumulate, etc.).]

[ALSO INCLUDE the producer's tests so the audit can verify whether tests exercise the duplicate-emission case.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**M1. Subprocess-stdout parsers** ⭐ canonical M case
- For every producer that walks the stdout of `subprocess.run` / `subprocess.Popen` / external CLI invocation, verify the return type is `frozenset[X]`, `dict.fromkeys`-deduplicated `list[X]`, or carries explicit "duplicates preserved" docstring text.
- Subprocess stdout is the canonical duplicate source: tools like `es.exe` (Everything), `find`, `git log --follow`, `grep -r` can emit the same path or row on multiple lines because of internal walk paths, symlinks, or alternate-data streams.
- Adversarial probes when the producer returns `list[X]` from a subprocess: (a) does the subprocess man page or behavior documentation state that output is unique? (b) does any test exercise the producer against a fixture stdout containing the same value on two lines? (c) does the consumer build a dict / set from the result — if yes, this is an M3 partner finding.

**M2. Database / registry queries**
- For every producer that builds a `list[Row]` from a SQL query, ORM call, or registry lookup, verify whether the underlying query carries `DISTINCT`, `GROUP BY`, or a unique-index constraint.
- Producers without query-level uniqueness MUST dedup in Python before returning, OR carry "all rows returned, including duplicates" docstring text, OR have a consumer that explicitly tolerates duplicates.
- Adversarial probes: (a) does the query JOIN against a one-to-many relation without aggregation? (b) does the schema lack a unique index on the SELECT'd columns? (c) does the consumer's downstream operation (writeback, upsert, INSERT) fail on duplicates?

**M3. Consumer-expects-set anti-pattern**
- For every consumer that calls `set(producer())`, `dict.fromkeys(producer())`, `dict((k, v) for k, v in producer())`, `INSERT ... ON CONFLICT`, or `pandas.DataFrame.set_index`, walk back to the producer: should the producer have returned the set/dict directly?
- The anti-pattern is a sign that the producer's `list[X]` return type lied about cardinality — the consumer is paying for the deduplication that the producer should have done.
- Adversarial probes: (a) does any test mock the producer with a list containing duplicates — does the consumer's set-conversion silently drop them? (b) does the consumer's set / dict size differ from the producer's list length in production logs? (c) does the consumer raise `RuntimeError: duplicate key` on production inputs?

**M4. `extend(...)` into list consumers (acceptable)**
- For every consumer whose only operation is `accumulator.extend(producer())` into a list, verify the accumulator's downstream consumers tolerate duplicates.
- This sub-bucket is the canonical "M passes" pattern: a recursive walker accumulating intermediate results into a list, where the final caller dedup once at the top level, is correct.
- Adversarial probes: (a) does the accumulator's downstream consumer dedup eventually? (b) does any branch of the accumulator's flow build a set from the accumulated list — if yes, the producer's cardinality contract is still ambiguous; (c) does the recursion depth ever cause the same item to be appended through two paths?

**M5. "Duplicates preserved" docstring (acceptable)**
- For every producer that returns `list[X]` from a duplicate-possible source AND carries docstring text stating duplicates are part of the contract, verify the docstring text is explicit and machine-grep-able (e.g., `"Returns all matching rows, including duplicates."` or `"Order preserved; duplicates retained for audit-trail purposes."`).
- This sub-bucket passes only when the contract is documented; absent the docstring text, the producer falls back to M1 / M2 / M3 audits.

**M6. Producer signature widening**
- Did the producer's return type widen across the diff (`list[X]` → `Sequence[X]`, `Sequence[X]` → `Iterable[X]`)? Widening relaxes cardinality and iteration guarantees the consumer may rely on.
- Adversarial probes: (a) any consumer that does `len(producer())` — `Iterable[X]` does not support `len()`; (b) any consumer that subscripts `producer()[0]` — `Iterable[X]` is not subscriptable; (c) any consumer that iterates the producer twice — `Iterable[X]` may be a generator exhausted after the first pass.

**M7. Recursive / cycle-prone walkers**
- For every producer that walks a graph, directory tree, or DAG, verify dedup happens at the walker boundary, not at every consumer.
- The canonical bug: a recursive walker that re-enters the same node via two paths (symlink, hardlink, DAG edge) appends the node twice; the consumer's first dedup hides the bug from one test, but a second consumer downstream is unprotected.
- Adversarial probes: (a) does the walker carry a `visited: set[X]` accumulator that gates re-entry? (b) does the test corpus include a fixture with a cycle / symlink / DAG edge that should trigger re-entry? (c) does the walker's return type promise uniqueness via `frozenset[X]` or `dict.fromkeys`?

**M8. Stream-fold accumulators**
- For every generator / `yield`-based producer consumed by `list(...)` / `collections.Counter` / `sum`, verify the consumer's cardinality expectation matches the producer's emission frequency.
- Adversarial probes: (a) does any consumer call `Counter(producer())` and read a count — duplicates inflate the count; (b) does any consumer call `sum(1 for x in producer())` — duplicates inflate the sum; (c) does any consumer call `list(producer())[-1]` — if the producer emits duplicates, the last item may be a duplicate of an earlier one.

## Cross-bucket questions to answer at the end

Q1: Is there a producer in the diff whose return type lies about cardinality — claiming `list[X]` while emitting from a source that can produce duplicates AND being consumed by a set-builder? Cite both the producer file:line and the consumer file:line.

Q2: What's the worst cardinality drift introduced by the diff? Evaluate by (a) whether the consumer raises on duplicates (M3 → RuntimeError), (b) whether the consumer silently drops duplicates (set-coercion masks the bug), or (c) whether the duplicates accumulate as wasted work (writeback applied twice).

Q3: Which consumer most likely will *start* failing once the producer's underlying source begins emitting duplicates? Identify consumers whose cardinality assumption is implicit and undocumented — these are the time bombs.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket M1-M8, produce Shape A or Shape B (with at least 3 probes). Each Shape A finding must cite BOTH the producer file:line AND the consumer file:line that the cardinality contract spans. Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Report every finding you reach, including uncertain ones and P2 ones, and give each finding a confidence level (high, medium, or low) beside its severity so a later pass can rank and filter them. Open Questions section for ambiguities. Read-only. No edits, no commits.
