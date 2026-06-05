Audit [REPO/ARTIFACT] [TARGET_ID] for **Category I only** (concurrency hazards). Skip A–H, J–N. Sub-bucket forced-exhaustion mode: Category I is decomposed into [N] sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA — including: is this code single-threaded, threaded, asyncio, multiprocessing, or mixed? Name the runtime (CPython 3.x, Node, Go, JVM, .NET, PowerShell runspace, browser JS), the concurrency primitives actually present (`threading`, `asyncio`, `multiprocessing`, `concurrent.futures`, `Thread`, `goroutine`, `Promise`, `Task`, `Start-ThreadJob`, `ForEach-Object -Parallel`, etc.), and the inter-process surface (shared filesystem, shared DB, shared cache, shared queue, signals). State explicitly which primitives are absent so each sub-bucket has a Shape B basis.]

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
- Adversarial probes: (a) does any single statement compile to multiple bytecodes (e.g., `obj.attr += 1`) that the GIL does not protect? (b) is there a JSON config rewritten by `json.dump(open(path, 'w'))` — non-atomic; concurrent reader sees a truncated file mid-write? (c) does a "transactional" wrapper actually start a transaction, or just open a connection?

**I6. Thread-local / async-local context bleed**
- `threading.local()` instances surviving thread-pool reuse (the same OS thread services many tasks; the `local` is keyed to the OS thread, not the logical task).
- `contextvars.ContextVar` set without `Context.run(...)` — propagation across `asyncio.create_task` is automatic but copying-on-create; mutations after task creation do not propagate.
- Request-scoped state stored on a module global (Flask `g`, Django thread-local request) leaking when the framework's scoping does not match the actual concurrency model.
- ORM session-per-request that is reused across requests due to a misconfigured scope.
- `asyncio` task-local state inside an executor (`run_in_executor` runs in a thread, not a coroutine — `contextvars` may or may not propagate depending on Python version and library version).
- Adversarial probes: (a) does any helper called from both sync and async paths assume the same context-storage primitive? (b) is there a pool-warmup that pre-populates `threading.local` and assumes it stays populated forever? (c) does logging context (correlation ID) propagate across `loop.run_in_executor`?

**I7. Cancellation handling**
- Every `await` inside an `async def` is a cancellation point. Cleanup code that follows `await` may be skipped on `CancelledError`.
- `asyncio.shield(...)` to protect critical cleanup; verify that what is shielded is genuinely critical and not just convenient.
- `try/except Exception:` swallowing `CancelledError` — `CancelledError` inherits from `BaseException` in 3.8+ but the codebase may run on older Python.
- Synchronous cancellation: `KeyboardInterrupt` landing between two syscalls; `SIGTERM` arriving mid-cleanup.
- `asyncio.timeout()` (3.11+) vs `asyncio.wait_for(...)` semantics — both raise `CancelledError`, both can race with the wrapped task completing.
- Adversarial probes: (a) does any `finally` block contain an `await` that could itself be cancelled, leaving cleanup half-done? (b) does the code rely on `__aexit__` running to release a resource, and does the cancellation path actually invoke `__aexit__`? (c) is there a `task.cancel()` call without `await task` afterward to surface the cancellation result?

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

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket I1–I8, produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1–Q3 answers after the per-sub-bucket walk. **Adversarial second pass (P1 quota):** "assume your first pass missed at least 3 P1 race conditions across these 8 sub-buckets — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

---

# Worked example: jl-cmd/claude-code-config PR #394

Audit jl-cmd/claude-code-config PR #394 for **Category I only** (concurrency hazards). Skip A–H, J–N. Sub-bucket forced-exhaustion mode: Category I is decomposed into 8 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

PR: feat(scripts): add sweep-empty-dirs utility and scheduled-task installer
Head SHA: 62c9c169ee7a44824e5da25c4cf8b74fdca08a53
ID prefix: `find`.

## ARTIFACT METADATA — concurrency model

This PR ships a single-threaded synchronous Python script and a single-threaded PowerShell installer. There is **no `asyncio`, no `threading`, no `multiprocessing`, no `concurrent.futures`** anywhere in the diff. The only concurrency surface is **inter-process** — another process on the same filesystem can mutate (delete, repopulate, re-attribute) a directory between the moment the script enumerates it and the moment the script acts on it. The interesting Category I surfaces are therefore:

- **TOCTOU windows** between `os.walk` enumeration and the per-entry `os.path.getctime` / `os.rmdir` calls inside `sweep()`.
- **TOCTOU windows** between PowerShell `Test-Path $Target` and the subsequent `Register-ScheduledTask` call.
- Whatever in-process state the Python `sweep()` function carries across iterations of its `for ... in os.walk(...)` loop (the local `removed: list[str]` accumulator).

Treat the protective `try/except OSError` blocks at sweep_empty_dirs.py:26-29 (the `getctime` block) and sweep_empty_dirs.py:31-36 (the `rmdir` block) as **race-handling protective code, not silent-failure observability defects**. Their Category F framing (silent-failure observability) is out of scope here; their Category I role is to absorb a TOCTOU race correctly. Evaluate whether they do absorb the race correctly — that is the I4 question, not "should they log louder."

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**I1. Shared mutable state without synchronization**
- `removed: list[str]` is declared at sweep_empty_dirs.py:21 inside `sweep()`'s body. Verify it is a function-local (re-allocated on every call), not a module-level or class-level binding that could be mutated from a second caller.
- Module-level state in `sweep_empty_dirs.py`: `DEFAULT_AGE_SECONDS` and `DEFAULT_POLL_INTERVAL` are imported at sweep_empty_dirs.py:9-10 from `config/sweep_config.py`. Verify these are read-only `int` rebinds — never mutated.
- The `main()` watch-loop at sweep_empty_dirs.py:127-129 calls `sweep(...)` repeatedly in a single thread; verify no closure or default-argument captures a mutable container that persists across iterations.
- Class-level mutable defaults: there are no classes in the diff. Verify by scanning for `class ` in the inlined source.

**I2. Missing await on async operations**
- There are zero `async def` definitions in the diff. Verify by scanning the inlined source of all four files for `async`, `await`, `asyncio`, `coroutine`.
- `subprocess.run(...)` at the test file (`test_sweep_empty_dirs.py`) is the synchronous form; verify the test never accidentally imports `asyncio.subprocess` or `subprocess.Popen` and forgets to wait.
- `time.sleep(arguments.interval)` at sweep_empty_dirs.py:129 is the synchronous blocking sleep; verify it is not paired with any cooperative scheduling primitive that would require an await.

**I3. Lock ordering / deadlock potential**
- There are zero `threading.Lock`, `threading.RLock`, `asyncio.Lock`, `multiprocessing.Lock`, or `with ... :` lock-context-manager usages in the diff. Verify by scanning the inlined source.
- The PowerShell installer takes no lock on the scheduled-task store; `Register-ScheduledTask -Force` at Install-SweepEmptyDirs.ps1:90 is the only writer. Verify there is no `Get-ScheduledTask` followed by a conditional `Register-ScheduledTask` whose interleaving with another administrator's edit could deadlock the Task Scheduler service.
- Filesystem-level locking (`msvcrt.locking`, `fcntl.flock`) is not used. Verify by scanning.

**I4. Race conditions / TOCTOU** ⭐ canonical I case for this PR
This is the highest-signal sub-bucket. There are TWO concrete TOCTOU windows in the diff. Cite both explicitly.

*Window 1 — Python sweep() enumeration vs per-entry actions.*
- `os.walk(root, onerror=_log_walk_error, topdown=False)` at sweep_empty_dirs.py:23-25 yields each directory path. Inside the loop body, sweep_empty_dirs.py:27 calls `os.path.getctime(each_directory_path)`, and sweep_empty_dirs.py:32 calls `os.rmdir(each_directory_path)`.
- Between `os.walk` enumerating a path and the in-loop `getctime`/`rmdir`, another process can:
  - Delete the directory entirely → `getctime` raises `FileNotFoundError` (subclass of `OSError`), absorbed by the except at sweep_empty_dirs.py:28-29 (`continue`). Race handled.
  - Repopulate the directory with files → `os.rmdir` raises `OSError` (`ENOTEMPTY`), absorbed by sweep_empty_dirs.py:35-36 (`pass`). Race handled — but `removed.append(...)` at sweep_empty_dirs.py:34 was NOT yet appended (it's inside the same try). Verify the append is correctly gated by successful `rmdir`.
  - Replace the directory with a symlink → `os.rmdir` on a symlink targeting a populated dir behaves OS-dependently; on Windows `os.rmdir` removes a directory symlink without touching the target, on POSIX it raises `ENOTDIR`. Verify the protective except is broad enough.
  - Update creation time on the directory between `getctime` (sweep_empty_dirs.py:27) and the `if` check (sweep_empty_dirs.py:30) → no real window here because the local `created` is already captured; the `now - created` comparison uses the captured value. Verify by re-reading the loop body.
- `topdown=False` means children are visited before parents. Verify that another process creating a file inside a child directory between the child's `rmdir` and the parent's `rmdir` does not cause the parent's `rmdir` to silently spare a now-non-empty parent — and that this is the *intended* behavior (skip parents whose children re-populated).

*Window 2 — PowerShell Test-Path vs Register-ScheduledTask.*
- `Test-Path $Target` at Install-SweepEmptyDirs.ps1:77 returns truthy, the script proceeds, and `Register-ScheduledTask -TaskName $TaskName ... -Force` runs at Install-SweepEmptyDirs.ps1:90.
- Between line 77 and line 90, another process can delete `$Target`. The schedule will still register because `Register-ScheduledTask` does not re-check `$Target`'s existence — the action argument is just a string. Verify whether the Action's path validation is deferred to first execution (low-impact: scheduled task fails on first run with a clear error rather than at install time).
- A second TOCTOU exists between the `$ScriptPath` check at Install-SweepEmptyDirs.ps1:81-84 (`if (-not (Test-Path $ScriptPath)) { ... exit 1 }`) and the `New-ScheduledTaskAction -Execute $PythonPath -Argument "$ScriptPath ..."` at Install-SweepEmptyDirs.ps1:89. If `sweep_empty_dirs.py` is removed between those lines, the registration succeeds with a stale path. Same low-impact pattern.
- A third TOCTOU exists between `Get-Command python` (or `py`) at Install-SweepEmptyDirs.ps1:80 and the `New-ScheduledTaskAction -Execute $PythonPath` at Install-SweepEmptyDirs.ps1:89. If Python is uninstalled between those lines, the registered task captures a stale absolute path.

*Adversarial probes for I4 (apply if no Shape A finding):*
- (a) On Windows, can `os.path.getctime` for a directory be coerced to lie by `SetFileTime` from another process between the directory's creation and the sweep? Cite docs.
- (b) Does `os.walk(topdown=False)` re-stat the parent after walking children, or does it cache the parent's path-string from the original enumeration?
- (c) On a network filesystem (SMB / NFS), what is the lower bound on the TOCTOU window between `os.walk` yielding a path and `os.rmdir` acting on it, and does the protective `OSError` catch handle the wider error surface (e.g., `OSError` with `errno.EREMOTE`)?

**I5. Atomicity of compound operations**
- The `removed.append(each_directory_path)` at sweep_empty_dirs.py:34 is a single-statement append on a function-local list; in CPython, list.append is atomic under the GIL. Verify there is no concurrent reader of `removed` (there isn't — `sweep` is called synchronously and returns `removed`).
- Read-modify-write on filesystem state: the `os.path.getctime → if → os.rmdir` triple at sweep_empty_dirs.py:27, 30, 32 is a non-atomic compound operation. The TOCTOU window between the `getctime` snapshot and the `rmdir` is the I4 case above; the I5 question is whether the operation should have used a single atomic primitive (it cannot — POSIX/Windows do not expose "rmdir if older than X" as one syscall), so a check-then-act is the correct pattern. Verify the protective except handles the non-atomic failure modes.
- The PowerShell installer's `Unregister-ScheduledTask`/`Register-ScheduledTask` pair is NOT used together (only `Register-ScheduledTask -Force` runs on install at Install-SweepEmptyDirs.ps1:90); `-Force` makes the register operation atomic from the caller's perspective (replace-or-create). Verify by reading the Microsoft docs for `Register-ScheduledTask -Force`.

**I6. Thread-local / async-local context bleed**
- There are zero `threading.local()`, `contextvars.ContextVar`, or async-context-manager usages in the diff. Verify by scanning the inlined source.
- The `main()` watch-loop at sweep_empty_dirs.py:126-131 runs in the foreground thread of a single Python process; there is no thread pool, no `concurrent.futures.ThreadPoolExecutor`, no `asyncio.run`. Verify.
- The PowerShell installer runs on a single PowerShell runspace; there is no `Start-ThreadJob`, no `ForEach-Object -Parallel`. Verify.

**I7. Cancellation handling**
- Python `KeyboardInterrupt` is caught at sweep_empty_dirs.py:130 (`except KeyboardInterrupt:`). Verify that:
  - The interrupt landing inside `sweep(...)` (e.g., between `os.path.getctime` and `os.rmdir`) does NOT corrupt filesystem state. `os.rmdir` is atomic at the syscall level; `KeyboardInterrupt` between syscalls is safe.
  - The interrupt landing inside `time.sleep(arguments.interval)` at sweep_empty_dirs.py:129 cleanly unwinds. `time.sleep` is interruptible by `KeyboardInterrupt` on all platforms in current CPython.
  - The `print("\nstopped.")` at sweep_empty_dirs.py:131 runs on every interrupt path; verify the `try/except KeyboardInterrupt` wraps the entire `while True` loop.
- There is no `asyncio.CancelledError` to propagate. Verify by scanning.
- The PowerShell installer has no cancellation surface beyond Ctrl-C at the user's prompt; `Register-ScheduledTask` is not interruptible mid-call from PowerShell.

**I8. Signal handling in multi-threaded code**
- Python's default behavior is that `SIGINT` is delivered to the main thread; the diff installs no custom signal handlers (`signal.signal` is not imported or called). Verify by scanning the inlined source for `signal`.
- Because the script is single-threaded, the "signals always go to main thread" caveat does not bite — there is only one thread to receive them.
- The PowerShell installer does not register signal handlers; PowerShell's host handles Ctrl-C natively.
- Verify there is no future-hostile pattern (e.g., a `signal.signal(signal.SIGINT, handler)` in a place that would silently no-op if `sweep_empty_dirs.py` were ever imported as a module from a non-main thread).

## Cross-bucket questions to answer at the end

Q1: Is there a critical section in `sweep()` that spans I4 (TOCTOU) and I5 (atomicity) such that a future refactor adding concurrency (I1) would silently corrupt the `removed` accumulator? Cite the line range.

Q2: What is the worst race-condition hazard introduced by this artifact in its current single-threaded form? Cite `sweep_empty_dirs.py:<line>` or `Install-SweepEmptyDirs.ps1:<line>` for the windowed pair, and explain the worst-case observable outcome (e.g., spurious deletion, stale registration, missed entry).

Q3: If a future change introduced concurrency (e.g., wrapped `sweep()` in `ThreadPoolExecutor` to walk multiple roots in parallel, or made `main()` async), which line would be the first to break atomicity, and which sub-bucket (I1/I3/I5/I6) would catch it?

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket I1-I8, produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P1 race conditions across these 8 sub-buckets — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

## Diff (4 new files, all lines in scope)

### packages/claude-dev-env/scripts/sweep_empty_dirs.py
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

### packages/claude-dev-env/scripts/config/sweep_config.py
```python
"""Centralized timing configuration for sweep_empty_dirs."""

DEFAULT_AGE_SECONDS: int = 120
DEFAULT_POLL_INTERVAL: int = 30
```

### packages/claude-dev-env/scripts/tests/test_sweep_empty_dirs.py
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

### packages/claude-dev-env/scripts/Install-SweepEmptyDirs.ps1
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
