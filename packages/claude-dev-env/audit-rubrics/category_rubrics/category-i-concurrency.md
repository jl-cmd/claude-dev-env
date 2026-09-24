# Category I — Concurrency hazards

**What this category audits:** race conditions, missing awaits, shared mutable state, lock ordering, atomicity of compound operations, cancellation handling, thread-local / async-local context bleed, signal handling in multi-threaded code.

**Examples of Category I findings:**
- Two coroutines append to the same list without synchronization.
- An `await` is missing on a critical-section operation, allowing other tasks to interleave.
- A lock is acquired in different orders on two code paths (deadlock potential).
- TOCTOU between `os.path.exists` and `os.open` in a directory another process can modify.
- A `threading.local` value leaking across thread-pool reuse.

**Companion reference:** see `../source-material-section-types.md`.

---

## Sub-bucket decomposition (Category I)

| ID | Axis name | Concrete checks |
|---|---|---|
| I1 | Shared mutable state without synchronization | Module-level lists/dicts/sets mutated from multiple threads or coroutines. |
| I2 | Missing await on async operations | `coro()` discarded without `await`; functions returning coroutines never awaited. |
| I3 | Lock ordering / deadlock potential | Multiple locks acquired in different orders on different code paths. |
| I4 | Race conditions / TOCTOU | Check-then-use patterns with a window where state can change. |
| I5 | Atomicity of compound operations | Read-modify-write sequences without atomic primitives. |
| I6 | Thread-local / async-local context bleed | `threading.local` in pools; `contextvars` propagation across `asyncio.create_task`. |
| I7 | Cancellation handling | `asyncio.CancelledError` propagation; cleanup on cancel. |
| I8 | Signal handling in multi-threaded code | Signals always go to main thread in Python; assumptions about handler thread. |

---

## Sample prompt

The reusable Variant C template for Category I is in [`../prompts/category-i-concurrency.md`](../prompts/category-i-concurrency.md). Inline your artifact under `## Source material` and adapt the sub-bucket bullets to your project's concurrency model.
