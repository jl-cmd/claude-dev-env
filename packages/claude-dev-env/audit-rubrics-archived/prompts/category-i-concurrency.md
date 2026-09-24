Audit [REPO/ARTIFACT] [TARGET_ID] for **Category I only** (concurrency hazards). Skip A–H, J–P. Sub-bucket forced-exhaustion mode: Category I is decomposed into 8 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA — including: is this code single-threaded, threaded, asyncio, multiprocessing, or mixed? Name the runtime (CPython 3.x, Node, Go, JVM, .NET, PowerShell runspace, browser JS), the concurrency primitives present (`threading`, `asyncio`, `multiprocessing`, `concurrent.futures`, `Thread`, `goroutine`, `Promise`, `Task`, `Start-ThreadJob`, `ForEach-Object -Parallel`, etc.), and the inter-process surface (shared filesystem, shared DB, shared cache, shared queue, signals). State explicitly which primitives are absent so each sub-bucket has a Shape B basis.]

ID prefix: `find`.

## Source material

Inline the artifact under audit below this section. Chunking guidance — pick the chunk size that lets findings cite `[section name]:[line/paragraph N]` unambiguously: see [`../source-material-section-types.md`](../source-material-section-types.md). For a code PR, one section = one file in the diff. For a long module audited standalone, one section = one function or class. For a design doc, one section = one named heading.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**I1. Shared mutable state without synchronization**
- Identify every module-level / class-level / closure-captured mutable container (lists, dicts, sets, deques, mutable dataclass fields, ORM session singletons, in-process caches). For each, state who writes it and who reads it, and whether any writer/reader pair runs in different threads, coroutines, or processes.
- Identify function-local accumulators that escape the function (returned, yielded, stored on `self`, passed to a callback) and check whether the caller exposes them to concurrent access.
- Mutable default arguments (`def f(x=[]):`) — these are shared across calls and are an I1 hazard the moment two callers coexist.
- Class-level attributes initialized once at class-body evaluation that are then mutated on instances (mutable class-default trap).
- Adversarial probes (apply if Shape B): (a) does any imported library install a module-level singleton (e.g., a global cache, a logger handler list) that this code mutates? (b) is there a `nonlocal` or closure capture that pins a mutable across an `async`/`spawn`/`submit` boundary? (c) does serialization (pickle, JSON round-trip) hide a shared reference that survives the boundary?

**I2. Missing await on async operations**
- Every call to an `async def` function must be `await`ed, scheduled via `asyncio.create_task`, or wrapped in `asyncio.gather`/`asyncio.ensure_future`. Discarded coroutines are silent no-ops that emit `RuntimeWarning: coroutine ... was never awaited` only at GC time.
- Scan for async-returning APIs whose name does not contain `async` (e.g., `httpx.AsyncClient.get`, `aiofiles.open`, anything decorated with `@asynccontextmanager`).
- Sync-looking calls inside `async def` that secretly return a coroutine (auto-instrumentation, monkeypatched libraries, Django Channels' `database_sync_to_async`).
- `asyncio.create_task` without holding a reference — Python 3.11+ may GC the task before completion.
- Adversarial probes: (a) does any `async def` function have a return path that constructs a coroutine via partial application or factory and discards it? (b) does any test invoke an async function as if it were sync and only checks return type? (c) is `asyncio.run` nested inside another running loop, silently dropping the inner coroutine?

**I3. Lock ordering / deadlock potential**
- Enumerate every lock primitive (`threading.Lock`, `RLock`, `Semaphore`, `Condition`, `Event`, `asyncio.Lock`, `multiprocessing.Lock`, file locks via `fcntl`/`msvcrt`, distributed locks via Redis/DB).
- For each pair of locks, determine the acquisition order on every code path. Two paths acquiring `(A, B)` and `(B, A)` is a textbook deadlock.
- Re-entrant calls into code that re-acquires a non-reentrant lock from the same thread.
- `with lock: await something()` — holding a `threading.Lock` across an `await` boundary blocks the entire event loop.
- External-service waits inside a critical section (HTTP call, DB query, `time.sleep` while holding a lock).
- Adversarial probes: (a) does a registered signal handler or `atexit` callback acquire a lock that the main flow may already hold? (b) does any callback passed to a third-party library (`os.walk(onerror=...)`, `logging.Handler.emit`) acquire a lock the third party also holds? (c) is there a lock acquired in a generator's `__enter__` and released in `__exit__` that a `GeneratorExit` could skip?

**I4. Race conditions / TOCTOU**
- Every check-then-act pair on shared state is a potential race. Enumerate filesystem TOCTOU: `os.path.exists` then `open`, `Test-Path` then `Register-*`, `os.path.getctime` then `os.rmdir`, `stat` then `chmod`, `readdir` then `unlink`.
- Database TOCTOU: `SELECT` then `INSERT` without a unique constraint or `INSERT ... ON CONFLICT`.
- Cache TOCTOU: `cache.get` returning miss, then `compute()`, then `cache.set` — two callers compute twice (cache stampede).
- HTTP TOCTOU: `HEAD` then `GET`, or `GET` then `PUT` without `If-Match`/ETag.
- For each TOCTOU window, identify the protective mechanism (atomic primitive, exception handler, idempotent operation) and verify it correctly absorbs every failure mode of the race, not just the happy-path one.
- Adversarial probes: (a) what is the lower bound on the TOCTOU window on a slow filesystem (NFS, SMB, FUSE)? (b) does the protective `except` clause catch the full error surface (not just `FileNotFoundError` when `OSError` would also include `PermissionError`, `OSError(errno.EREMOTE)`, `OSError(errno.EBUSY)`)? (c) does symlink replacement between check and act bypass the check?

**I5. Atomicity of compound operations**
- Read-modify-write sequences on shared state without an atomic primitive: `counter = counter + 1`, `dict[k] = dict.get(k, 0) + 1`, `list[i] += 1`, `set.add(x)` after `if x not in set`.
- Multi-statement updates that must succeed or fail as a unit but are not wrapped in a transaction / lock / `with` block.
- Compound filesystem ops where no single syscall expresses the intent: "delete if older than X" (must `stat` then `unlink`), "rename if doesn't exist" (must `stat` then `rename` — POSIX `rename` is atomic but overwrites, Windows `rename` fails on overwrite).
- DB compound ops outside a transaction: read-then-update without `SELECT FOR UPDATE`, `UPDATE ... WHERE version = ?` (optimistic locking missing).
- CPython GIL gives some atomicity to single bytecode ops (list.append, dict.__setitem__) but not to `+=` or `dict.setdefault` callbacks.
- Adversarial probes: (a) does any single statement compile to multiple bytecodes (e.g., `obj.attr += 1`) that the GIL does not protect? (b) is there a JSON config rewritten by `json.dump(open(path, 'w'))` — non-atomic; concurrent reader sees a truncated file mid-write? (c) does a "transactional" wrapper start a transaction, or just open a connection?

**I6. Thread-local / async-local context bleed**
- `threading.local()` instances surviving thread-pool reuse (the same OS thread services many tasks; the `local` is keyed to the OS thread, not the logical task).
- `contextvars.ContextVar` set without `Context.run(...)` — propagation across `asyncio.create_task` is automatic but copying-on-create; mutations after task creation do not propagate.
- Request-scoped state stored on a module global (Flask `g`, Django thread-local request) leaking when the framework's scoping does not match the concurrency model.
- ORM session-per-request that is reused across requests due to a misconfigured scope.
- `asyncio` task-local state inside an executor (`run_in_executor` runs in a thread, not a coroutine — `contextvars` may or may not propagate depending on Python version and library version).
- Adversarial probes: (a) does any helper called from both sync and async paths assume the same context-storage primitive? (b) is there a pool-warmup that pre-populates `threading.local` and assumes it stays populated forever? (c) does logging context (correlation ID) propagate across `loop.run_in_executor`?

**I7. Cancellation handling**
- Every `await` inside an `async def` is a cancellation point. Cleanup code that follows `await` may be skipped on `CancelledError`.
- `asyncio.shield(...)` to protect critical cleanup; verify that what is shielded is critical and not just convenient.
- `try/except Exception:` swallowing `CancelledError` — `CancelledError` inherits from `BaseException` in 3.8+ but the codebase may run on older Python.
- Synchronous cancellation: `KeyboardInterrupt` landing between two syscalls; `SIGTERM` arriving mid-cleanup.
- `asyncio.timeout()` (3.11+) vs `asyncio.wait_for(...)` semantics — both raise `CancelledError`, both can race with the wrapped task completing.
- Adversarial probes: (a) does any `finally` block contain an `await` that could itself be cancelled, leaving cleanup half-done? (b) does the code rely on `__aexit__` running to release a resource, and does the cancellation path invoke `__aexit__`? (c) is there a `task.cancel()` call without `await task` afterward to surface the cancellation result?

**I8. Signal handling in multi-threaded code**
- Python: signals are always delivered to the main thread. A custom signal handler installed by `signal.signal(...)` on a non-main thread silently no-ops.
- A long-running computation in a non-main thread cannot be interrupted by `KeyboardInterrupt` directly; the main thread sees the signal but the worker keeps running until it cooperates (yields, returns, blocks).
- `asyncio` and signals: `loop.add_signal_handler` is the correct primitive; `signal.signal` from inside a running loop subverts the loop.
- Re-entrancy: signal handlers can interrupt anything, including a critical section guarded by a lock — handlers must use only async-signal-safe operations.
- C extensions / native code: a long-running C call (NumPy op, gzip decompress) blocks signal delivery until it returns.
- Adversarial probes: (a) does any module install a signal handler at import time that conflicts with the framework's own handler (Django, Celery, gunicorn)? (b) does the code assume `Ctrl-C` reaches a non-main thread when the runtime guarantees otherwise? (c) is there a `signal.signal(SIGTERM, ...)` registered in a place that would silently no-op if the module is ever imported from a non-main thread (worker process, plugin loader)?

## Cross-bucket questions to answer at the end

Q1: Is there a critical section that spans two or more sub-buckets such that a future refactor adding concurrency (I1) would silently corrupt state already racing in I4/I5? Cite the line range.

Q2: What is the worst race-condition hazard introduced by this artifact in its current form (single-threaded or otherwise)? Cite `<file>:<line>` for the windowed pair, and explain the worst-case observable outcome.

Q3: If a future change introduced (or expanded) concurrency — wrapping the hot path in a thread pool, making it async, sharding across processes, or moving state to a shared store — which line would be the first to break atomicity, and which sub-bucket (I1/I3/I5/I6) would catch it?

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket I1-I8, produce Shape A or Shape B (with at least 3 probes). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Report every finding you reach, including uncertain ones and P2 ones, and give each finding a confidence level (high, medium, or low) beside its severity so a later pass can rank and filter them. Open Questions section for ambiguities. Read-only. No edits, no commits.
