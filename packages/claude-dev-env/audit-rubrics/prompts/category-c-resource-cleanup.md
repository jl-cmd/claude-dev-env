Audit [REPO/ARTIFACT] [TARGET_ID] for **Category C only** (resource cleanup and lifecycle). Skip A, B, D–P. Sub-bucket forced-exhaustion mode: Category C is decomposed into 8 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA]
- Repository / artifact: [REPO_OR_ARTIFACT_NAME]
- Target identifier: [PR_NUMBER | COMMIT_SHA | BRANCH | TAG | PATH]
- Head SHA / revision: [HEAD_SHA_OR_REVISION]
- Scope (paths in scope): [PATH_GLOBS_OR_DIR_LIST]
- Languages / runtimes: [LANGS_AND_RUNTIMES]
- Concurrency model: [SYNC | THREADED | ASYNCIO | MULTIPROCESS | EVENT_LOOP | MIXED]
- Deployment model: [CLI | LIBRARY | DAEMON | SCHEDULED_TASK | SERVERLESS | CONTAINER | OTHER]
- ID prefix: `find`.

## Source material

Inline the artifact under review here (full diff, full file bodies, or a faithful excerpt). Use the chunking guide in `../source-material-section-types.md` to decide between full-diff inlining, file-body inlining, or excerpt-with-line-anchors. Every sub-bucket below assumes the auditor can cite the inlined material by path and line number — if a sub-bucket cannot be cited from the inlined material, that is itself a protocol gap and must be flagged in the Output preamble.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**C1. File handles / file objects**
- Enumerate every site that opens a file-like object in production code: `open(...)`, `io.open(...)`, `os.fdopen(...)`, `pathlib.Path.open(...)`, language-equivalent `fopen` / `File::open` / `fs.openSync` / `OpenRead` / `BufferedReader` / `FileStream`.
- For each site, identify the corresponding release: `with`/context manager, `try`/`finally` `close()`, RAII destructor, `using` block, deferred close, explicit `.close()` reachable on every code path including early `return`, raised exception, and `break`/`continue`.
- Single-call helpers that open-write-close internally (e.g. `pathlib.Path.write_text`, `pathlib.Path.read_bytes`, `fs.writeFileSync`) do not return a handle to user code and are not a leak site.
- Distinguish file objects from file descriptors: a wrapped FD (`os.fdopen`) is owned by the file object and closed when the object closes; a raw FD from `os.open` belongs to C8.
- Shape B proof-of-absence requires ≥3 adversarial probes specific to this sub-bucket. Examples: (a) does any code path open a file via stdlib (`open`, `io.open`, `os.fdopen`, `pathlib.Path.open`, language-equivalent)? (b) do any error/exception callbacks (e.g. an `onerror=` handler) ever receive an object carrying an open FD that the callback must close? (c) do any helper APIs that look like single-call helpers return a handle the caller is expected to close?

**C2. Subprocess / child processes**
- Enumerate every site that spawns a child process: `subprocess.run`, `subprocess.Popen`, `os.system`, `os.spawn*`, `multiprocessing.Process`, `child_process.spawn`, `child_process.exec`, `Process.Start`, `os/exec.Command`, shell-out wrappers.
- Synchronous wrappers that block until the child exits and reap automatically (`subprocess.run`, `child_process.execSync`, `Process.WaitForExit` after `Start`) do not require a paired `wait` / `communicate` from the caller.
- Asynchronous spawns (`Popen` without `wait`/`communicate`, `child_process.spawn` without `.on('exit')`) require an explicit reaping path on every exit branch — including the parent crashing or being killed.
- Pipes opened via `stdout=PIPE` / `stderr=PIPE` / `capture_output=True` are owned by the spawning call and closed when it returns; the caller must not retain references that outlive the call.
- Process groups, signal handlers, and `start_new_session` / `preexec_fn` / `detached: true` introduce teardown obligations on parent shutdown.
- Shape B proof-of-absence requires ≥3 adversarial probes. Examples: (a) is there any asynchronous spawn (`Popen` vs `run`, `spawn` vs `execSync`, detached child) anywhere in the diff? (b) does any caller rely on a child's pipe being readable AFTER the synchronous wrapper returns (which would require keeping the pipe open)? (c) if a child can hang (e.g. blocking input read), is there a `timeout=` on the synchronous wrapper so the parent does not block forever, and what is the leak hazard for the parent's process table when the timeout fires?

**C3. Temporary files and directories**
- Enumerate every site that creates a temporary path: `tempfile.NamedTemporaryFile`, `tempfile.TemporaryFile`, `tempfile.TemporaryDirectory`, `tempfile.mkstemp`, `tempfile.mkdtemp`, `os.tmpfile()`, `mkstemp`/`mkdtemp` equivalents, `fs.mkdtempSync`, `Path.GetTempFileName`, application-built scratch dirs under `/tmp` or `%TEMP%`.
- Verify every constructor that yields a context manager is entered with `with` (or language-equivalent `using`/`defer`).
- Manual factories (`mkstemp`, `mkdtemp`) require an explicit cleanup path reachable on every exit branch including raised exceptions.
- Platform-specific gotchas: Windows `NamedTemporaryFile(delete=True)` cannot be reopened while the handle is held; `TemporaryDirectory` cleanup fails if any handle into the directory is still open at exit time.
- Backdating creation/access times of a temporary path does not interfere with cleanup — cleanup uses path-based recursive deletion, not age-based.
- Shape B proof-of-absence requires ≥3 adversarial probes. Examples: (a) does any code exit a `with` block via `return`/`raise` after the temp is populated, leaving inner contents to be reclaimed by the context manager (verify this is supported)? (b) on Windows, if production code holds an open handle to a temp path it just walked or wrote, would the surrounding context manager's `__exit__` fail (e.g. `WinError 32`)? (c) if a helper that mutates the temp directory raises an exception mid-setup, does the surrounding context manager still clean up?

**C4. Network connections**
- Enumerate every site that opens a network resource: `socket.socket`, HTTP clients (`requests.Session`, `httpx.Client`, `urllib.request.urlopen`, `http.client`, `fetch`, `axios.create`), DB drivers (psycopg, pymongo, sqlite3, redis-py, prisma client), message-queue clients, gRPC channels, WebSocket clients, SMTP/IMAP/FTP clients.
- For each site, verify a release path on every exit branch: explicit `close()`, `with` block, connection-pool return, `dispose`/`destroy`, `defer client.Close()`.
- Pooled clients have their own lifecycle: the pool itself must be closed on application shutdown, and individual borrows must be returned even on exception.
- Side-channel connections introduced by libraries (telemetry, metrics, tracing) count too if they are configured by code in the diff.
- Local-only invocations of cmdlets, CLIs, or RPC endpoints should be distinguished from network calls.
- Shape B proof-of-absence requires ≥3 adversarial probes. Examples: (a) does any imported stdlib or third-party module implicitly open a network socket on import, on first use, or at module construction time? (b) do any local cmdlet / CLI invocations reach a remote service (e.g. cloud-provider auth lookup, package-registry resolution, AppX execution-alias) under common configurations? (c) do any name-resolution or service-discovery calls (DNS, mDNS, AppX alias, `Get-Command`) hit network paths under common Windows / macOS / Linux configurations?

**C5. Locks, semaphores, mutexes**
- Enumerate every synchronization primitive constructed: `threading.Lock`, `threading.RLock`, `threading.Semaphore`, `threading.BoundedSemaphore`, `threading.Event`, `threading.Condition`, `multiprocessing.Lock`/`Semaphore`/`Manager` locks, `asyncio.Lock`/`Semaphore`/`Event`/`Condition`, advisory file locks (`fcntl.flock`, `msvcrt.locking`), DB advisory locks, distributed locks.
- For each acquire, verify a release on every exit branch (context manager preferred over manual acquire/release).
- Mixing sync and async primitives (`threading.Lock` inside a coroutine, `asyncio.Lock` in a thread pool) is a hazard even when individual release paths look correct.
- Implicit locks held by OS APIs and library internals (e.g. logging's `_lock`, GIL-adjacent locks) are out of scope unless the diff configures them.
- Shape B proof-of-absence requires ≥3 adversarial probes. Examples: (a) do filesystem mutators (`os.rmdir`, `os.rename`, equivalent) take internal directory locks that could deadlock with concurrent enumerators on the same root? (b) do registration/installation cmdlets take exclusive locks on host databases (e.g. Task Scheduler, service control manager, package registry) that a concurrent invocation would block on, and is there a stale-lock recovery path? (c) does cleanup machinery in temp / cache directories use any internal lock that persists past test or task teardown?

**C6. Subscriptions / event listeners / signal handlers**
- Enumerate every registration of a listener / handler / observer: `signal.signal`, `signal.set_wakeup_fd`, `atexit.register`, `weakref.finalize`, `asyncio.add_signal_handler`, `loop.add_reader`/`add_writer`, observer-pattern `subscribe`/`addEventListener`/`on`, framework lifecycle hooks (`useEffect` cleanup, Django signals, Flask `before_request`/`teardown_request`), Windows `Register-ObjectEvent` / `Register-EngineEvent` / WMI subscriptions, COM event sinks.
- For each registration, verify a paired unregistration on every teardown path, and verify the handler does not leave global state (e.g. signal disposition) altered after the process owning the registration ends.
- Callbacks scoped to a single call (e.g. `os.walk(..., onerror=...)`) are not subscriptions — the registration is bounded by the call.
- Persistent OS-level event subscriptions (scheduled tasks, COM event sinks, systemd units) require explicit teardown via the corresponding unregistration command and must not be assumed to vanish on parent exit.
- Shape B proof-of-absence requires ≥3 adversarial probes. Examples: (a) does any signal-handling path leave a non-default signal disposition in place for the next process invoked by the same shell or for child processes inheriting the disposition? (b) when an installer or registration step succeeds, does it install any persistent subscription that a future uninstall step must explicitly tear down — or does the uninstall fully unwind the subscription? (c) are any callbacks passed to bounded-scope APIs (e.g. `onerror=` on a single-call API) confused with persistent subscriptions, or vice versa?

**C7. Background threads / async tasks**
- Enumerate every long-running flow: `threading.Thread`, `threading.Timer`, `concurrent.futures.Executor`, `asyncio.create_task`, `asyncio.ensure_future`, `asyncio.run`, `loop.run_until_complete`, `setInterval`/`setTimeout`, worker threads, `Goroutine` / `go` calls, daemon flags on threads.
- For foreground watch loops (`while True: do_thing(); sleep(...)`) without threads or tasks, treat the loop body as the "background work" and audit shutdown paths the same way.
- For each long-running flow, identify every termination signal (Ctrl-C → `KeyboardInterrupt`, `SIGTERM`, `SIGHUP`, console-close, parent process exit, scheduled-task "Stop the running task", container SIGTERM with grace period) and trace which signals reach a teardown branch and which kill the process before teardown runs.
- Verify in-flight work has a graceful drain or is idempotent on retry; verify shutdown signal propagation through nested tasks (`asyncio.gather` cancellation semantics, `Thread.join` timeouts, task cancellation cooperative-yield points).
- Cross-reference the deployment model: a watch loop that is only invoked via single-shot `--once` arguments by a scheduler is interactive-only in practice, narrowing the C7 hazard surface.
- Shape B proof-of-absence requires ≥3 adversarial probes. Examples: (a) what happens if the `sleep` call is interrupted by SIGTERM on POSIX vs Windows — does the loop body still attempt one more iteration, or does the process die immediately? (b) if the inner work raises an unexpected exception not caught by inner handlers, does the outer loop crash without printing a teardown message and without retrying on the next interval — and is that intended fail-fast behavior or a silent reliability bug? (c) if a tight-loop configuration (e.g. `--interval 0`, `setInterval(fn, 0)`) is supplied, does the loop become a CPU-burn that no shutdown signal can break out of cleanly except SIGKILL?

**C8. OS-level resources (file descriptors, named pipes, mmap, shared memory, persistent OS objects)**
- Enumerate every site that creates a low-level OS resource: `os.open`/`os.close`, `os.pipe`, `mmap.mmap`, `multiprocessing.shared_memory.SharedMemory`, Windows named pipes (`win32pipe`, `pywin32`), `eventfd`, `inotify` watch handles, scheduled tasks (`Register-ScheduledTask`), Windows services (`New-Service`), systemd units, cron entries, registry keys created at runtime, COM objects, GDI handles.
- For raw FDs and mmap regions, verify explicit close / unmap on every exit path; for persistent OS objects (scheduled tasks, services, registry entries), verify the diff provides a symmetric teardown command and that the teardown command fully unwinds every property set at registration time.
- High-level filesystem APIs (`os.walk`, `os.path.getctime`, `os.rmdir`) do not expose user-managed FDs and belong to C1/C3, not C8.
- Re-running the registration step with the same identifier should be idempotent (i.e. fully replace, not leak the prior registration's child objects).
- Shape B proof-of-absence requires ≥3 adversarial probes. Examples: (a) does any high-level enumeration API (`os.walk`, glob, directory iterators) on Windows hold an OS-level directory enumeration handle that persists past the loop's normal exit, requiring an explicit close — and what about early-exit via inner `except ... continue` branches? (b) if an installer is run twice with different parameters, does the second registration fully replace the first, or does it leak the prior registration's child objects (action, trigger, settings)? (c) do any host-resolution or capability-discovery cmdlets (`Get-Command`, `Get-Service`, etc.) hold cached process tokens or handles that need to be released before the script exits?

## Cross-bucket questions to answer at the end

Q1: Is there any resource acquired in one sub-bucket whose release path lives in another (e.g., a subprocess spawned in C2 whose pipes are reaped only when the surrounding `tempfile.TemporaryDirectory` in C3 exits, or a thread in C7 that owns a socket from C4)? Cite both lines.

Q2: What is the worst leak hazard introduced by this artifact — the one most likely to silently produce a runtime resource leak on a long-lived host (operator runs the long-running flow in a terminal for days, daemon under a service manager, container restart loop)? Cite [path:line] for the acquisition site and the missing release path.

Q3: Where would an exception thrown from inside a `try` block (any `try: ... except: ...` or `try: ... finally: ...` in scope) cause a resource to leak past its intended owner? Name the line(s) most fragile, including catch-all `except OSError: pass` / `except: ...` blocks that may swallow leak signals.

## Output

Lead with a preamble: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket C1–C8, produce Shape A (a finding tied to specific [path:line] evidence) or Shape B (proof-of-absence) with at least 3 adversarial probes specific to that sub-bucket. After the per-sub-bucket walk, answer Q1–Q3 from the cross-bucket section.

Report every leak you reach, including uncertain ones and P2 ones, as Shape A findings under the relevant sub-bucket, and give each finding a confidence level (high, medium, or low) beside its severity so a later pass can rank and filter them.

Open Questions section: list any ambiguities — e.g. behavior depending on platform, runtime version, or deployment configuration that the inlined source material does not pin down. Each open question must name the sub-bucket it belongs to and the [path:line] context that triggered it.

Read-only. No edits, no commits.
