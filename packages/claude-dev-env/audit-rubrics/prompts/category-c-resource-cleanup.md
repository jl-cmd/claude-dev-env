Audit [REPO/ARTIFACT] [TARGET_ID] for **Category C only** (resource cleanup and lifecycle). Skip A, B, D–N. Sub-bucket forced-exhaustion mode: Category C is decomposed into 8 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

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
- Shape B proof-of-absence requires ≥3 adversarial probes specific to this sub-bucket. Examples: (a) does any code path open a file via stdlib (`open`, `io.open`, `os.fdopen`, `pathlib.Path.open`, language-equivalent)? (b) do any error/exception callbacks (e.g. an `onerror=` handler) ever receive an object carrying an open FD that the callback must close? (c) do any helper APIs that look like single-call helpers actually return a handle the caller is expected to close?

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
- Local-only invocations of cmdlets, CLIs, or RPC endpoints should be distinguished from genuine network calls.
- Shape B proof-of-absence requires ≥3 adversarial probes. Examples: (a) does any imported stdlib or third-party module implicitly open a network socket on import, on first use, or at module construction time? (b) do any local cmdlet / CLI invocations actually reach a remote service (e.g. cloud-provider auth lookup, package-registry resolution, AppX execution-alias) under common configurations? (c) do any name-resolution or service-discovery calls (DNS, mDNS, AppX alias, `Get-Command`) hit network paths under common Windows / macOS / Linux configurations?

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

P1 adversarial quota: run an explicit second pass with the prompt "assume your first pass missed at least 3 P1 leaks across these 8 sub-buckets — find them." Surface any P1 leaks discovered in this pass as Shape A findings appended to the relevant sub-bucket(s).

Open Questions section: list any ambiguities — e.g. behavior depending on platform, runtime version, or deployment configuration that the inlined source material does not pin down. Each open question must name the sub-bucket it belongs to and the [path:line] context that triggered it.

Read-only. No edits, no commits.

---

# Worked example: jl-cmd/claude-code-config PR #394

Audit jl-cmd/claude-code-config PR #394 for **Category C only** (resource cleanup and lifecycle). Skip A, B, D–N. Sub-bucket forced-exhaustion mode: Category C is decomposed into 8 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

PR: feat(scripts): add sweep-empty-dirs utility and scheduled-task installer
Head SHA: 62c9c169ee7a44824e5da25c4cf8b74fdca08a53
ID prefix: `find`.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**C1. File handles / file objects**
- Production code (`sweep_empty_dirs.py`) contains zero `open()` calls and zero `os.fdopen` calls — all I/O is `print(...)` to stdout/stderr (lines 20, 44, 82, 89-92, 98) which Python manages globally, plus `os.walk`, `os.path.getctime`, and `os.rmdir` which do not return file objects to user code.
- Config (`sweep_config.py`) is import-only — no I/O whatsoever.
- Test file uses `Path(nonempty_dir, "keepme.txt").write_text("hello")` at `test_sweep_empty_dirs.py:84` — `pathlib.Path.write_text` opens, writes, and closes the file in a single call internally; no leaked handle for the test caller to mishandle.
- The PowerShell launcher does no `[IO.File]::Open*` calls; only `Test-Path`, `Get-Command`, scheduled-task cmdlets, and `Write-Host`.
- Shape B proof-of-absence requires ≥3 adversarial probes: (a) does any code path open a file via stdlib (`open`, `io.open`, `os.fdopen`, `pathlib.Path.open`)? (b) does the `_log_walk_error` callback (line 19-20) ever receive an `OSError` with an open `.fd` attribute it must close? (c) does `tempfile.TemporaryDirectory` internally return any user-facing file descriptors (vs. just a path string)?

**C2. Subprocess / child processes**
- Production code spawns no child processes; only the test helper does.
- `test_sweep_empty_dirs.py:24-32` invokes `subprocess.run(["powershell", "-Command", ...], check=True, capture_output=True)` — the synchronous form. `subprocess.run` blocks until the child exits and reaps the process automatically; no `Popen.wait`/`Popen.communicate` pairing is required.
- `capture_output=True` (line 31) is shorthand for `stdout=PIPE, stderr=PIPE`. Pipes opened by `subprocess.run` are drained and closed by the function before it returns. No FD leak.
- `check=True` (line 30) raises `CalledProcessError` on non-zero exit — that exception path also fully cleans up the child before bubbling out (the cleanup happens inside `subprocess.run` regardless of how it returns).
- No `start_new_session`, no `preexec_fn`, no signal-handler installation that would need teardown. The PowerShell child inherits the parent stdin/stdout but those are stdlib-managed.
- Shape B proof-of-absence requires ≥3 adversarial probes: (a) is there any `Popen` (vs `run`) anywhere in the diff? (b) does the test ever rely on the child's stderr being readable AFTER `subprocess.run` returns (which would require keeping the pipe open)? (c) if the PowerShell child hangs (e.g., a `Read-Host` injected via the f-string at line 28), is there a `timeout=` on `subprocess.run` so the parent test does not block forever — and if not, is that a leak hazard for the test runner's process table on CI?

**C3. Temporary files and directories**
- Every test uses `with tempfile.TemporaryDirectory() as tmp:` — the context manager guarantees `cleanup()` runs on the way out, including on exception.
- Five test functions, five `with` blocks: `test_sweep_empty_dirs.py:36`, `:47`, `:57`, `:75`, `:81`. All correctly entered as context managers.
- No `tempfile.NamedTemporaryFile` (which has the platform-specific `delete=` gotcha on Windows) anywhere in the diff.
- No manual `tempfile.mkdtemp()` (which would not auto-clean) anywhere in the diff.
- The `_set_creation_time_windows` helper (line 20) sets a backdated CreationTimeUtc on the tmp directory itself in `test_empty_root_does_not_crash` (line 76) — backdating does not interfere with `TemporaryDirectory.cleanup()` because cleanup uses path-based recursive deletion, not age-based.
- Shape B proof-of-absence requires ≥3 adversarial probes: (a) does any test exit the `with` block via `return`/`raise` after `os.mkdir` succeeds but before the assertion runs, leaving the inner mkdir-created entry to be reclaimed by `TemporaryDirectory.cleanup()` (which it handles fine via recursive rmtree)? (b) on Windows, if the production `sweep()` (line 23) holds an open handle to a directory it just walked, would `TemporaryDirectory.__exit__` fail with `WinError 32` — and is there any scenario in the five tests where `sweep` could leave such a handle? (c) if `_set_creation_time_windows` raises `CalledProcessError` (subprocess returns non-zero), does the surrounding `with tempfile.TemporaryDirectory()` still clean up? (yes — the context manager catches no exception, but its `__exit__` always runs.)

**C4. Network connections**
- No `requests`, `httpx`, `urllib`, `socket`, `http.client`, no DB driver imports anywhere in the diff. Production code's only external interactions are the local filesystem (`os.walk`, `os.rmdir`, `os.path.getctime`) and timing (`time.time`, `time.sleep`).
- The PowerShell launcher invokes only local cmdlets (`Get-ScheduledTask`, `Register-ScheduledTask`, `Get-Command`, etc.) — no `Invoke-RestMethod`, no `Invoke-WebRequest`.
- Shape B proof-of-absence requires ≥3 adversarial probes: (a) does any imported stdlib module (`argparse`, `os`, `sys`, `time`, `datetime`, `subprocess`, `tempfile`, `pathlib`) implicitly open a network socket on import or first use? (b) does scheduling a Windows task via `Register-ScheduledTask` (line 89) reach out to a remote scheduler service or stay purely local to the host's `taskschd.msc`? (c) does `Get-Command py` / `Get-Command python` (lines 79-80) trigger any network resolution (e.g., AppX execution-alias lookup that hits Microsoft Store)?

**C5. Locks, semaphores, mutexes**
- No `threading.Lock`, `threading.RLock`, `threading.Semaphore`, `multiprocessing.Lock`, `asyncio.Lock`, no `fcntl` or `msvcrt` advisory file locks anywhere in the diff.
- The watch loop in `main()` (lines 93-98) is single-threaded; no shared-state coordination is needed.
- The PowerShell installer is single-threaded; no `Mutex` / `Semaphore` cmdlets used.
- Shape B proof-of-absence requires ≥3 adversarial probes: (a) does `os.rmdir` (line 43) take a Windows-internal directory lock that could deadlock with a concurrent enumerator on the same root? (b) does `Register-ScheduledTask -Force` (line 89) take an exclusive lock on the Task Scheduler database that a concurrent installer invocation would block on — and is there a stale-lock scenario? (c) does `tempfile.TemporaryDirectory.cleanup()` use any internal lock that would persist past test teardown?

**C6. Subscriptions / event listeners / signal handlers**
- No `signal.signal(...)` registration anywhere in the diff. The watch loop relies on Python's default SIGINT → `KeyboardInterrupt` translation, which the interpreter manages globally — there is no user-installed handler to restore on shutdown.
- No `atexit.register` anywhere in the diff.
- No `weakref.finalize`, no observer-pattern registration, no asyncio event-loop callbacks (the diff is synchronous throughout).
- The PowerShell launcher does no `Register-ObjectEvent`, `Register-EngineEvent`, or WMI subscription.
- Shape B proof-of-absence requires ≥3 adversarial probes: (a) does the `KeyboardInterrupt` handler at lines 97-98 leave any signal handler in a non-default state for the next process invoked by the same shell? (b) when `Register-ScheduledTask` (line 89) succeeds, does it install any persistent COM event subscription that a future `Unregister-ScheduledTask` (line 55) must explicitly tear down — or does `Unregister-ScheduledTask` fully unwind the subscription? (c) does the `_log_walk_error` callback (line 19) registered as `os.walk(..., onerror=...)` need to be explicitly unregistered after the walk completes — or is the registration scoped to the single `os.walk` call?

**C7. Background threads / async tasks** ⭐ canonical C case for this PR
- `main()` at lines 77-98 is the only long-running flow. The continuous-watch path (lines 93-98) is `try: while True: sweep(...); time.sleep(...) except KeyboardInterrupt: print("\nstopped.")`.
- The only user-visible teardown path is `KeyboardInterrupt` (line 97). On Ctrl-C, Python raises the exception inside `time.sleep` or between iterations, the loop unwinds, and `print("\nstopped.")` runs. There is no other teardown action — no flush of in-flight `removed` lists, no marker file, no exit code distinction between "interrupted" and "completed normally".
- Crucially: there is **no SIGTERM handler**. On Windows, `SIGTERM` from the Task Scheduler's "Stop the running task" action, or from a parent process closing the console, terminates the process without invoking the `except KeyboardInterrupt` block. The "stopped." message will not print on SIGTERM. Cite line 97 (`except KeyboardInterrupt:`) as the only teardown branch and verify whether the surrounding scheduled-task contract (the PR's intent — see `Install-SweepEmptyDirs.ps1:89`'s `Register-ScheduledTask`) ever invokes the watch-loop path or only the `--once` path.
- Cross-reference: `Install-SweepEmptyDirs.ps1:85` builds `-Argument "$ScriptPath --once --age $AgeSeconds ""$Target"""` — every scheduled invocation is `--once`, which takes the line 85-87 branch (`if arguments.once: sweep(...); return`) and bypasses the watch loop entirely. So the watch loop is **interactive-only** in practice. The C7 hazard is therefore confined to operators running `python sweep_empty_dirs.py /target` in a terminal without `--once` and then sending SIGTERM (vs Ctrl-C).
- No `threading.Thread` / `threading.Timer` / `concurrent.futures.Executor` / `asyncio.create_task` / `asyncio.run` anywhere in the diff. The "background" is a foreground `while True: time.sleep` loop, not a thread or task.
- Shape A finding hazard: the watch loop has no graceful drain of the `sweep()` call currently in progress when SIGTERM arrives mid-sweep. `os.rmdir` at line 43 could be interrupted between the `os.path.getctime` check (line 38) and the `os.rmdir` call (line 43), but since each iteration is independent and `removed` is a local list discarded at sweep return (line 49), there is no consistency hazard — only an output-line hazard (the most recent `print(f"deleted: ...")` at line 44 may not flush). Verify whether this is acceptable for a scheduled-task-only use case.
- Shape B proof-of-absence requires ≥3 adversarial probes: (a) what happens if `time.sleep(arguments.interval)` (line 96) is interrupted by SIGTERM on POSIX vs Windows — does the loop body still attempt one more sweep, or does the process die immediately? (b) if `sweep()` (line 95) raises an unexpected `OSError` not caught by its inner handlers (e.g., `OSError: [WinError 1392] The file or directory is corrupted`), does the watch loop crash without printing "stopped." and without re-attempting on the next interval? Verify whether this is intended fail-fast behavior or a silent reliability bug. (c) if the operator launches the watch loop with `--interval 0`, does the loop become a CPU-burn that no shutdown signal can break out of cleanly except SIGKILL? Probe lines 68-73 of the parser definition for default/min validation.

**C8. OS-level resources (file descriptors, named pipes, mmap, shared memory)**
- No `os.open` / `os.close` (low-level FD APIs) anywhere in the diff. All filesystem calls are high-level (`os.walk`, `os.path.getctime`, `os.rmdir`, `os.path.isdir`, `os.path.join`, `os.mkdir`, `os.makedirs`).
- No `mmap`, no `multiprocessing.shared_memory`, no `os.pipe()`, no Windows named-pipe APIs (`win32pipe`, `pywin32`).
- The Windows scheduled task (registered at `Install-SweepEmptyDirs.ps1:89`) is a persistent OS-level resource. The PR provides a teardown path: `Install-SweepEmptyDirs.ps1:54-58` (`if ($Remove) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue }`). Verify the registration/unregistration pair is symmetric — every property set in `Register-ScheduledTask -Action -Trigger -Settings` (line 89) is fully cleaned up by `Unregister-ScheduledTask -TaskName` alone (it cascades and removes the action/trigger/settings rows from the Task Scheduler database).
- Shape B proof-of-absence requires ≥3 adversarial probes: (a) does `os.walk` (line 34) on Windows hold any OS-level directory enumeration handle that persists past the `for` loop's normal exit, requiring an explicit close — and what about early-exit via the inner `except OSError: continue` (line 39)? (b) if the operator runs `Install-SweepEmptyDirs.ps1` without `-Remove` twice with different `-IntervalMinutes` values, does the second `Register-ScheduledTask -Force` (line 89) fully replace the first registration, or does it leak the prior task's COM action object? (c) does `Get-Command py` / `Get-Command python` (lines 79-80) hold any cached process token that needs to be released before the script exits?

## Cross-bucket questions to answer at the end

Q1: Is there any resource acquired in one sub-bucket whose release path lives in another (e.g., a subprocess spawned in C2 whose pipes are reaped only when the surrounding `tempfile.TemporaryDirectory` in C3 exits)? Cite both lines.
Q2: What's the worst leak hazard introduced by this PR — the one most likely to silently produce a runtime resource leak on a long-lived host (operator runs the watch loop in a terminal for days)? Cite `packages/claude-dev-env/scripts/sweep_empty_dirs.py:<line>` for the acquisition site and the missing release path.
Q3: Where would an exception thrown from inside a `try` block (the inner `try: os.rmdir(...) except OSError: pass` at lines 42-47, the outer `try: while True: ... except KeyboardInterrupt: ...` at lines 93-97, or the test helper's `subprocess.run(check=True)` at line 30 inside a `with tempfile.TemporaryDirectory()`) cause a resource to leak? Name the line(s) most fragile.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket C1-C8, produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P1 leaks across these 8 sub-buckets — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

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
