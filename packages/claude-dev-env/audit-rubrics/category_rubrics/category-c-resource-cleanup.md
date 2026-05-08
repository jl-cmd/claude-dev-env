# Category C — Resource cleanup and lifecycle

**What this category audits:** file handles, network connections, subprocess processes, locks, semaphores, temporary files, subscriptions, event listeners, background tasks — anything acquired that must be released, and anything that must be released on every code path including error and exception paths.

**Examples of Category C findings:**
- A file is opened in a function that returns before reaching `close()` or a `with` block.
- A database connection is acquired without a release path on every error branch.
- A background asyncio task is started without a cancellation hook on shutdown.
- A `subprocess.Popen` is spawned without `wait()` / `communicate()` and the process becomes a zombie.
- A `tempfile.TemporaryDirectory` is constructed manually (without `with`) and leaks on exception.

**Companion reference:** see `../source-material-section-types.md`.

---

## Sub-bucket decomposition (Category C)

| ID | Axis name | Concrete checks |
|---|---|---|
| C1 | File handles / file objects | `open()` without `with`; explicit `close()` reachable on every path; `os.fdopen` lifetime. |
| C2 | Subprocess / child processes | `Popen` without `wait` / `communicate`; `subprocess.run` is fine; signal handling on parent exit. |
| C3 | Temporary files and directories | `tempfile.NamedTemporaryFile` without `delete=` semantics understood; `TemporaryDirectory` cleanup on exception. |
| C4 | Network connections | Sockets, HTTP clients, DB connections — closed on every path; connection pooling lifecycle. |
| C5 | Locks, semaphores, mutexes | Acquired in one place, released on every exit path; `threading.Lock` vs `asyncio.Lock` mixing. |
| C6 | Subscriptions / event listeners / signal handlers | Registered → unregistered pairs; teardown on object destruction. |
| C7 | Background threads / async tasks | Cancellation propagated; `asyncio.gather` exception handling; thread `join` on shutdown. |
| C8 | OS-level resources | File descriptors / handles; named pipes; shared memory; mmap regions. |

---

## Sample prompt

The reusable Variant C template for Category C is in [`../prompts/category-c-resource-cleanup.md`](../prompts/category-c-resource-cleanup.md). Inline your artifact under `## Source material` and adapt the sub-bucket bullets to your project's resource lifecycle.

For a literal worked example using PR #394 inlined verbatim, see [`category-a-api-contracts.md`](category-a-api-contracts.md). The Category C–relevant pieces of that diff are C2 (the `subprocess.run` in the test helper — naturally bounded), C3 (the `tempfile.TemporaryDirectory()` calls — all use `with`, verified clean), and C7 (the `while True: sleep` watch loop in `main()` — has no shutdown hook beyond `KeyboardInterrupt`).
