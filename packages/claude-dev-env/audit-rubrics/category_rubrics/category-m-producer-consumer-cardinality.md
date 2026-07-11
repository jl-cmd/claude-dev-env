# Category M — Producer/consumer cardinality vs collection-type contract

**What this category audits:** functions returning `list[X]`, `Sequence[X]`, or `Iterable[X]` where the producer can emit duplicates but the consumer treats the value as a set. Common when a subprocess-stdout parser walks every output line, when a registry query returns rows with non-unique keys, when a recursive walker re-enters the same node via two paths, or when a stream-fold accumulates without dedup. The bug surfaces downstream as `RuntimeError: duplicate key`, as a UI showing the same item twice, or as a writeback that re-applies the same operation.

**Why this category is its own bucket:** Categories A–K catch failure modes in either the producer or the consumer in isolation. Category M catches the contract drift between them: the producer's return type promises `list[X]` (cardinality unconstrained), but a consumer downstream calls `set(result)`, builds a `dict.fromkeys(result, ...)`, or feeds the result into an `INSERT ... ON CONFLICT` that crashes on duplicates. The producer and consumer each look correct individually; the bug emerges only when their cardinality contracts disagree.

**Examples of Category M findings:**
- `_extract_paths_from_everything_cli_stdout` returns `list[Path]` but the consumer runs one `INSERT` per element against a `UNIQUE(path)` table, raising `sqlite3.IntegrityError: UNIQUE constraint failed` when the subprocess emits the same path twice. (pa#143 F10)
- A database query returns duplicate `content_id` rows; the writeback path submits the same content twice and the second `INSERT` fails with a constraint violation. (pa#136 F30)
- A writeback ignores the `content_id` key and re-applies an `UPDATE` against the same row, masking which row "won". (pa#136 F32)
- A logger flushes every accumulator line without dedup; the same warning appears N times in the user-facing report.

**Companion reference:** see `../source-material-section-types.md`.

---

## Sub-bucket decomposition (Category M)

Decomposition is by the **kind of producer/consumer pair** whose cardinality contracts must agree.

| ID | Axis name | Concrete checks |
|---|---|---|
| M1 | Subprocess-stdout parsers | Functions that walk lines from `subprocess.run(...).stdout` MUST return `frozenset[X]`, `dict.fromkeys`-deduplicated `list[X]`, OR carry explicit "duplicates preserved" docstring text — never bare `list[X]` |
| M2 | Database / registry queries | Functions that build a `list[Row]` from a query MUST dedup by primary key when the consumer treats rows as a set, OR document "all rows returned, including duplicates" |
| M3 | Consumer-expects-set anti-pattern | Consumer calls `set(producer())`, `dict.fromkeys(producer())`, `dict((k, v) for k, v in producer())`, or `INSERT ON CONFLICT` on the producer's output — this is a sign the producer should have returned a `frozenset` / `dict` upstream |
| M4 | `extend(...)` into list consumers (acceptable) | Consumer's only operation is `accumulator.extend(producer())` and the accumulator is itself a list — cardinality is preserved by design, no dedup needed |
| M5 | "Duplicates preserved" docstring (acceptable) | Producer's docstring explicitly states duplicates are part of the contract (e.g., for replay logs, audit trails, ordered streams) — no dedup required |
| M6 | Producer signature widening | `Sequence[X]` widened to `Iterable[X]` (or `list[X]` → `Sequence[X]`) without re-validating each consumer's cardinality assumption |
| M7 | Recursive / cycle-prone walkers | Walkers that traverse a graph or directory tree where a node can be re-entered via two paths MUST dedup at the walker boundary, not at every consumer |
| M8 | Stream-fold accumulators | Generators / `yield`-based producers consumed by `list(...)` or `collections.Counter` — verify the consumer's cardinality expectation matches the producer's emission frequency |

Customize per-artifact: a pure-function producer that returns a single value reduces to "verified clean — no collection involved"; a subprocess parser without a downstream consumer in the same PR may still need M1 satisfied by docstring text.

---

## Sample prompt

The reusable Variant C template for Category M is in [`../prompts/category-m-producer-consumer-cardinality.md`](../prompts/category-m-producer-consumer-cardinality.md). Inline both the producer function and every consumer call site under `## Source material` so the audit can verify each cardinality boundary.

## Why Category M matters as its own bucket

Categories A–K each examine one side of an interface in isolation. Category M examines the cardinality contract spanning two sides: the producer's "can my return value contain duplicates?" question and the consumer's "do I tolerate duplicates?" answer. A reviewer walking only A–K reads the producer, finds it correct on its own terms, and approves it — then reads the consumer separately and finds it also correct on its own terms. The bug emerges only when the two are exercised against the same input together.

The pa#143 F10 case is the canonical worked example: `_extract_paths_from_everything_cli_stdout` returned `list[Path]` by walking the `es.exe` stdout line-by-line. The consumer iterated the list directly and ran one `INSERT INTO watched_dirs(path) VALUES (...)` per element against a table with a `UNIQUE(path)` constraint. When the subprocess emitted the same path on two lines (a real edge case — Everything's stdout can repeat results across drive letters), the list carried the path twice, so the writeback ran the same `INSERT` twice; the second `INSERT` raised `sqlite3.IntegrityError: UNIQUE constraint failed: watched_dirs.path` and the entire watchdog crashed. The fix was to change the producer to `frozenset[Path]`, which deduplicates at the boundary so each path reaches the writeback once; the consumer's per-element `INSERT` loop was already correct. The contract was the bug.
