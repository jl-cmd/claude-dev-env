Audit [REPO/ARTIFACT] [TARGET_ID] for **Category F only** (silent failures). Skip A–E, G–N. Sub-bucket forced-exhaustion mode: Category F is decomposed into 8 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA]
- Title / short description: [TITLE]
- Revision identifier (commit SHA, doc version, transcript date, etc.): [REVISION_ID]
- Scope note (what is in vs out of scope): [SCOPE_NOTE]

ID prefix: `find`.

## Source material

Inline the artifact under audit here, broken into named sections. A "section" is the natural chunk you'd quote and reference back to when reporting a finding — pick the chunk size that lets a finding cite `[section name]:[line/paragraph N]` unambiguously. See the chunking guide at `../source-material-section-types.md` for the lookup table (code PR → one file per section; long module → one function per section; design doc → one heading per section; etc.) and the rule of thumb for monolithic artifacts ("impose your own breaks at logical hinge points and label them: `### lines 1–40 (parameter parsing)`").

Use one `###` header per section so each chunk is independently citable:

```
### [section identifier — e.g. relative file path, function name, heading title, clause number]
[content of that section, in a fenced block when it is code/config]
```

Repeat for every section in scope.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**F1. Catch-all except clauses**
- Locate every bare `except:`, `except Exception:`, `except BaseException:` (and language-equivalents: PowerShell `try { } catch { }` with no type filter, JS `catch (e) {}`, Go `_ = err`, Rust `let _ = result`).
- For each, classify the body: `pass` / `continue` / log-only / re-raise. Only re-raise (or a documented benign-case-with-trace) is compliant.
- For the swallowing variants, enumerate which exception subclasses the protected call actually raises and identify which are real failures vs benign known cases (e.g., for `os.rmdir`: `FileNotFoundError`, `PermissionError`, `NotADirectoryError`, `OSError(ENOTEMPTY)`, `OSError(EBUSY)` — only `ENOTEMPTY` is benign).
- Check for asymmetry: do two error handlers in the same module disagree on whether to log? A handler that logs to stderr next to one that silently swallows is a Category F smell even when each is locally defensible.
- Check for double-swallow: does an outer callback (e.g. `os.walk(..., onerror=...)`) already report errors that an inner `except` then swallows again?

**F2. Errors logged then swallowed**
- Every `logger.error(...)` / `print(..., file=sys.stderr)` / `Write-Warning` / `console.error(...)` followed by `return None` / `return default` / fall-through with no re-raise.
- Verify the caller chain: is the logged error observable to a human? Logs that go to stderr but the caller never inspects exit code or status output are still effectively swallowed at the system boundary.
- Asymmetric narration: is the success path loud (`print("deleted: X")`) and the failure path silent? Either both should narrate or neither should.
- For library callbacks whose return value the stdlib explicitly ignores (e.g. `os.walk`'s `onerror`), trace whether the log-then-return is the only signal upward — if so, downstream status/exit-code reporting must also reflect that errors occurred.

**F3. Default fallback values masking failure**
- `dict.get(key, default)` where the absence of the key is itself a bug.
- `or default` short-circuits hiding `None` returns from fallible calls.
- `getattr(obj, attr, default)` masking `AttributeError` from the wrong object type.
- argparse `default=...` for values that should fail-loud when absent.
- Loop iterators that return empty on permission/IO errors (e.g. `os.walk` on an unreadable root) and let the function return successfully with no work done — verify the watcher does not silently sweep nothing forever.
- Type coercion that accepts nonsensical values: `[int]$X` accepts `0` and negative numbers silently; absence of `[ValidateRange(...)]` / explicit bounds checking is the F3 hazard.
- Re-validation cadence: if a startup guard (`if not os.path.isdir(root): sys.exit(1)`) runs once but the protected resource can disappear mid-run, the guard's success becomes an F3 fallback for every subsequent iteration.

**F4. Async task error swallowing**
- `asyncio.create_task(...)` without exception observation (no `.add_done_callback`, no later `await`).
- `asyncio.gather(..., return_exceptions=True)` where the returned exceptions are not inspected.
- `Thread(target=...)` with no `join()` or no exception forwarding.
- `multiprocessing.Pool.apply_async` without `.get()` or error callback.
- JS `Promise` not awaited and no `.catch(...)`.
- PowerShell `Start-Job`, `Start-ThreadJob`, `Invoke-Command -AsJob` without `Receive-Job -Wait` or job-state inspection.
- External-async equivalents that count as Shape B candidates: scheduled tasks (Windows Task Scheduler, cron) whose `LastTaskResult` / exit code is never read by an operator-facing tool. Probes for that case: does the installer's `-Status` flow surface `LastTaskResult`? Does the success message lie when the underlying registration emitted a non-terminating warning piped to `Out-Null`? Does the long-running loop body handle SIGTERM / scheduler shutdown distinctly from KeyboardInterrupt?

**F5. Status returns identical on success and failure**
- Functions returning `bool` / `int` / `list` / `Optional[T]` where the same value (`True`, `0`, `[]`, `None`) appears on the happy path AND inside a catch-all error branch.
- Distinguish "no work to do" (legitimate empty) from "work attempted but every step silently failed" (F5 hazard) — if the caller cannot tell these apart from the return value, that is a finding.
- Process-level F5: does the program exit 0 after a long run that silently failed every operation? Compare the exit code on Ctrl+C-after-success vs Ctrl+C-after-all-failures.
- Callback-level F5: stdlib callbacks whose return value is contractually ignored (e.g. `os.walk`'s `onerror` returns `None`) are immune to F5 — book that as a clarification, not a finding.

**F6. Ignored return values from fallible calls**
- `subprocess.run(...)` without `check=True` AND no manual `.returncode` inspection.
- `os.write`, `os.read`, `socket.send`, `socket.recv` whose short-write/short-read return values are discarded.
- File-handle methods (`f.write`) whose returned byte count is not checked when partial writes are possible (Windows pipes, network sockets).
- PowerShell pipelines piped to `| Out-Null` that may be hiding a non-terminating warning.
- Functions that return a status object alongside a side effect — verify the side effect's success is the actual contract and the discarded return is informational only.
- Exception-only contracts (e.g. `os.rmdir` returns `None`, raises on failure) belong under F1, not F6 — note the cross-reference rather than double-booking.

**F7. PowerShell error-suppression patterns**
- `-ErrorAction SilentlyContinue` followed by `.Property` / `.Method` access on a possibly-`$null` result. Compliant only when an explicit `if ($result)` guard runs before the property access.
- `-ErrorAction Ignore` (stronger than SilentlyContinue — does not even populate `$Error`).
- `2>$null`, `*>$null`, `$ErrorActionPreference = 'SilentlyContinue'` mutations.
- `$?` not consulted after a native-binary call where exit code matters.
- The opposite hazard: a fallback path that drops `-ErrorAction SilentlyContinue` from a `Get-Command` (or similar) call where the `$null` was the entire contract — produces a terminating error on the path that was supposed to be silent-then-handled-by-the-next-line.
- Semantic-success-but-functional-failure: `Get-Command` finds the Microsoft Store stub `python.exe` whose `.Source` resolves but whose execution opens the Store. The cmdlet did not error, but the resolved interpreter cannot run code. Verify whether scripts validate that resolved paths actually do their job.
- Mismatched user-facing messages: a `-Remove` / `-Uninstall` flow that prints "X removed." regardless of whether anything was actually unregistered.

**F8. Test-level swallowing**
- `try/except` / `try/catch` inside a test body that catches and logs instead of asserting. Tests must fail loudly when their target raises.
- `pytest.warns` used where `pytest.raises` was the actual contract.
- Tests asserting only on the success path with no negative-space coverage of the swallowed-error branch.
- Tests whose name encodes an assertion ("does not crash") but whose body asserts nothing — the test passes incidentally and would also pass if the function silently failed every operation.
- Coverage gaps for known F1 / F2 / F6 swallowing branches: if the audited code has `except OSError: pass`, is there a test that exercises that branch and verifies the post-conditions (e.g. directory still present, no log line emitted)?
- Test fixtures using `subprocess.run(..., check=True)` are compliant — the exception path is the contract.

## Cross-bucket questions to answer at the end

Q1: Are there error paths that span two sub-buckets (e.g., an F1 catch-all whose result feeds into an F5 status-equivalence — same return value regardless of how many silent failures occurred)?
Q2: What's the worst silent-failure hazard introduced by this artifact? Cite `[section]:[line]`. Justify against P0/P1 severity using observable user impact (e.g., a watcher that runs forever and never makes progress because of a permissions issue, with no log line indicating why).
Q3: Where would a future error-handling refactor most likely *introduce* a silent failure? Name the line(s) most fragile — for instance, adding a top-level `try/except` around a long-running loop body to "make it more resilient" can convert the only loud failure (top-level crash) into a silent infinite-loop-of-nothing.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket F1-F8, produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P1 silent failures across these 8 sub-buckets — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

---

# Worked example: jl-cmd/claude-code-config PR #394

Audit jl-cmd/claude-code-config PR #394 for **Category F only** (silent failures). Skip A–E, G–N. Sub-bucket forced-exhaustion mode: Category F is decomposed into 8 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

PR: feat(scripts): add sweep-empty-dirs utility and scheduled-task installer
Head SHA: 62c9c169ee7a44824e5da25c4cf8b74fdca08a53
ID prefix: `find`.

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

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**F1. Catch-all except clauses**
- `sweep_empty_dirs.py` line 28-29: `except OSError: continue` absorbs `os.path.getctime` failures inside the `os.walk` bottom-up loop. Verify this is the documented "file vanished mid-walk" case and not masking a permission denial that leaves stale empty dirs forever.
- `sweep_empty_dirs.py` line 35-36: `except OSError: pass` absorbs `os.rmdir` failures. The intent comment in the rubric says "silently skips non-empty dirs". Enumerate the OSError subclasses `os.rmdir` actually raises: `FileNotFoundError`, `PermissionError`, `NotADirectoryError`, `OSError(ENOTEMPTY)`, `OSError(EBUSY)`. The non-empty case (ENOTEMPTY) is the *only* benign one — every other subclass is a real failure being swallowed without logging.
- Critical asymmetry: `_log_walk_error` (line 14-15) DOES log walk-level errors to stderr, but the inner `except OSError: pass` at line 35-36 logs nothing on the rmdir path. The PR ships two error handlers that disagree on whether errors deserve a stderr trace.
- The walk-level handler `_log_walk_error` is wired through `os.walk(root, onerror=_log_walk_error, topdown=False)` at lines 22-24. Verify whether the `except OSError: continue` at line 28-29 ever fires for an error `os.walk`'s `onerror` already reported, producing a double-swallow with the second handler being silent.
- `main()` at lines 65-83 has no top-level `try/except` around `sweep(...)`, so unhandled errors inside the loop body (other than KeyboardInterrupt at line 81) would crash the watcher. Verify whether any silent-failure within `sweep()` could leave the watcher running but no longer making progress (e.g., sweep returns empty list every cycle because every rmdir fails).

**F2. Errors logged then swallowed**
- `_log_walk_error` (lines 14-15) writes to stderr and returns implicitly — `os.walk` continues. The CALLER (`sweep`) never observes that a walk-level error happened. `removed` is returned to `main()` which only ever does `sweep(arguments.root, arguments.age)` (lines 70 and 76 inside the watch loop) without inspecting the return value. The walk-error trace exists but the failure does not propagate. Audit whether the watcher's exit code or status output should reflect that scan errors occurred.
- `print(f"deleted: {...}")` at line 33 is success-only narration; there is no symmetric `print(f"failed to remove: {...}")` inside the rmdir except handler at line 35-36. The success path is loud; the failure path is silent.
- The installer at line 65-66 prints no diagnostic when `Get-Command py` returns `$null` — the absence is silently absorbed into the if/else expression, then re-checked at line 67 with `if (-not $PythonPath)`. The user sees the "Cannot find Python" message at line 68 but never sees *which* discovery step failed (py vs python) or *why*.

**F3. Default fallback values masking failure**
- `arguments.root`, `arguments.age`, `arguments.interval` come from argparse with `default=DEFAULT_AGE_SECONDS` (line 50) and `default=DEFAULT_POLL_INTERVAL` (line 53). If the imports at lines 9-10 of `sweep_empty_dirs.py` fail (e.g., `config.sweep_config` becomes unavailable due to a sys.path drift), the failure is loud (ImportError at module load). No `dict.get` / `getattr` / `or default` fallback in this file.
- `os.walk(root, onerror=_log_walk_error, topdown=False)` (lines 22-24): if `root` is a path that exists but is not iterable due to permissions, `os.walk` returns an empty iterator and `removed` is `[]` — the function returns successfully with no work done. Verify this is desired: the watcher will silently sweep nothing every cycle. Compare against `main()`'s line 67 guard `if not os.path.isdir(arguments.root): sys.exit(1)` — that guard is checked once at startup but not on every iteration of the watch loop, so a deleted-mid-watch root produces an empty-success silent failure.
- The PowerShell installer's `[int]$AgeSeconds = 120` (line 22) and `[int]$IntervalMinutes = 5` (line 19) silently coerce non-int input — `Install-SweepEmptyDirs.ps1 -AgeSeconds "abc"` raises a parameter-binding exception (loud), but `-AgeSeconds 0` or `-AgeSeconds -1` is accepted silently and produces a watcher that sweeps every directory regardless of age. No validation attribute (`[ValidateRange(1, [int]::MaxValue)]`) is present.

**F4. Async task error swallowing**
- No `asyncio`, no `create_task`, no `gather`, no `Thread`, no `multiprocessing` in any of the four diff files. Verify by scanning:
  - `sweep_empty_dirs.py` — single-threaded `while True: sweep(...); time.sleep(...)` at lines 73-79.
  - `Install-SweepEmptyDirs.ps1` — synchronous cmdlet calls only; no `Start-Job`, `Start-ThreadJob`, `Invoke-Command -AsJob`, or `Register-ObjectEvent`.
  - `test_sweep_empty_dirs.py` — synchronous `subprocess.run(..., check=True)` only; no async test fixtures.
- F4 is therefore Shape B for this PR. Three adversarial probes:
  1. Could the scheduled-task wrapper (which runs `sweep_empty_dirs.py --once` every IntervalMinutes per the trigger at line 73) be considered an "async task" whose errors are swallowed by Task Scheduler? Verify `New-ScheduledTaskSettingsSet` at line 75 does not request error notifications; the task's `LastTaskResult` is observable via `Get-ScheduledTaskInfo` but the installer's `-Status` branch (lines 21-32) only prints `$task.State`, `$action`, and `$trigger` — never `LastTaskResult`. Failed runs are invisible to the operator.
  2. The installer pipes `Register-ScheduledTask -Force | Out-Null` at line 77. `Out-Null` discards the returned task object — if Register-ScheduledTask emits a non-terminating warning (e.g., principal mismatch), it is suppressed.
  3. `time.sleep(arguments.interval)` at line 78 is interruptible only via KeyboardInterrupt (line 81). Any non-keyboard signal (SIGTERM on POSIX, the scheduler-driven shutdown on Windows) terminates the process abruptly with no cleanup hook — verify this is acceptable given the watcher's stateless design.

**F5. Status returns identical on success and failure**
- `sweep(root, min_age_seconds) -> list[str]` (line 17) returns `removed` (line 39). The list is empty in three distinct scenarios: (a) no empty directories existed (legitimate success), (b) `os.walk` raised pre-iteration (caught by `_log_walk_error` callback — execution continues with empty walker), (c) every candidate directory failed `os.rmdir` and the failures were swallowed at line 35-36. The caller cannot distinguish these three outcomes from the return value alone.
- `_log_walk_error(os_error)` returns `None` implicitly (line 14-15). `os.walk` ignores the return value of its `onerror` callback per the stdlib contract — the return-equivalence check is moot for this function.
- `main()` returns `None` (line 64) and never returns a non-zero exit code in the success branches. `sys.exit(1)` fires only when the root is not a directory (line 69). A watcher that ran for an hour and silently failed every rmdir exits with code 0 on Ctrl+C the same as a watcher that successfully cleaned 1000 directories. This is canonical F5: terminal status equivalent for opposite outcomes.

**F6. Ignored return values from fallible calls**
- `os.rmdir(each_directory_path)` at line 31 has no return value (`-> None`). The contract for failure is exception-only; F6 does not apply directly to this call. The exception-swallowing concern is already booked under F1.
- `print(f"deleted: ...")` at line 33 returns `None`; print failures are not checked. Ordinary case, not a hazard here.
- `sweep(...)` at line 70 (the once-mode call) returns `list[str]` and the return value is discarded by `main`. Verify whether discarding the return is acceptable given the function's other side effect (the `print(f"deleted: ...")` log at line 33 already informs the operator). Discarding here is benign because the print is the user-facing channel; the list return is for testing.
- `sweep(...)` at line 76 (inside the watch loop) — same return-discard. Same reasoning applies.
- `subprocess.run` in `test_sweep_empty_dirs.py` at line 24 uses `check=True` and `capture_output=True`. `check=True` converts non-zero exit to `CalledProcessError`; the test does not catch it. Return-value inspection is not required because the exception path is the contract. Compliant.
- `Register-ScheduledTask -Force | Out-Null` at line 77 of installer — `Out-Null` deliberately discards the returned `CimInstance` task object. The cmdlet still raises a terminating error on registration failure (per Microsoft's `Register-ScheduledTask` docs), so the discard is not silent. But the success-path side effect is opaque: a future caller wanting to verify the registered trigger's `Repetition.Interval` cannot, because the object is gone. Verify whether the script's `-Status` flow at lines 21-32 fully covers post-registration verification.
- `Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue` at line 42 of installer — return value discarded, errors suppressed. Booked under F7 below; the F6 concern is whether the absence-of-task case (the user runs `-Remove` when nothing is registered) should be treated as success (current behavior) or as a warning. Current behavior prints `"$TaskName removed."` at line 43 even when nothing was removed.

**F7. PowerShell error-suppression patterns**
- `Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue` at line 22 of installer — null is captured into `$task`, then explicitly checked by `if (-not $task)` at line 23. The null absorption is handled. Compliant.
- `Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue` at line 42 of installer — the `-ErrorAction SilentlyContinue` makes the absence-of-task case non-terminating. Verify intent: should `-Remove` against a never-installed task be a success (current) or a clearly-flagged no-op? The `Write-Host "$TaskName removed."` at line 43 will print regardless, mis-stating the outcome.
- ⚠️ `Get-Command py -ErrorAction SilentlyContinue` at line 65 immediately followed by `.Source` access at line 66: `$_py = Get-Command py -ErrorAction SilentlyContinue` returns `$null` when `py` is absent; the line 66 expression `$_py.Source` would throw on `$null`, BUT the `if ($_py)` guard short-circuits to the `else` branch first. The `py`-side path is safe.
- ⚠️⚠️ The fallback at line 66 is `(Get-Command python).Source` — *missing* `-ErrorAction SilentlyContinue`. When neither `py` nor `python` is on PATH, `Get-Command python` raises a terminating `CommandNotFoundException`, which propagates past the `if (-not $PythonPath)` guard at line 67 entirely. The intended diagnostic message at line 68 (`"Cannot find Python (py or python) on PATH."`) is never reached. This is the OPPOSITE F7 hazard: the script is *loud* on a failure path that was *intended to be silent-then-handled-by-line-67*. The asymmetry between line 65 (suppressed) and line 66's else-branch (not suppressed) is a real bug.
- No `2>$null`, `*>$null`, or `$ErrorActionPreference` mutation in this script. No `$?` consultation either, but each cmdlet either has explicit error handling or uses default error action.
- Adversarial probe — does `Get-Command python` find the Microsoft Store stub on a fresh Windows 11 install? The stub's `.Source` resolves to `%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe`, which when invoked opens the Store rather than running Python. The installer would register a scheduled task whose `-Execute` path opens the Microsoft Store every IntervalMinutes — a silent semantic failure even though `Get-Command` did not error. Verify whether the installer needs to validate that the resolved interpreter actually executes Python.

**F8. Test-level swallowing**
- `test_sweep_empty_dirs.py` has no try/except inside any test body. All tests use direct asserts (lines 38-39, 47-49, 64-67, 76-78). No `pytest.warns`, no `pytest.raises` either — failure paths are not exercised at all.
- `_set_creation_time_windows` at lines 17-25 uses `subprocess.run(..., check=True, capture_output=True)`. `check=True` raises `CalledProcessError` on PowerShell failure; the test does not catch it. The fixture *should* fail loudly if the helper fails — compliant.
- Adversarial probe — `test_empty_root_does_not_crash` at lines 70-72 asserts nothing about the return value of `sweep(tmp, ...)`. The test name encodes the assertion ("does not crash"), but a sweep that crashed via `sys.exit` mid-call would still propagate a `SystemExit` that pytest reports as a failure, so the negative-space coverage works incidentally. However, a sweep that returned an empty list because every rmdir silently failed would also pass this test. The test does not distinguish "no work to do" from "all work silently failed" — it cannot, given the Shape A hazard at line 35-36.
- Adversarial probe — there is NO test that exercises the `except OSError: pass` branch at line 35-36. No fixture creates a non-empty directory whose creation time is older than the threshold and asserts that `sweep` does NOT delete it (line 75-78's `test_skips_nonempty_dir` uses `min_age_seconds=0` and only checks the rmdir-fails-on-non-empty path, but the path that branch takes is `OSError(ENOTEMPTY)` swallowed silently — the test cannot distinguish "rmdir was called and failed silently" from "rmdir was never called" without instrumentation). The silent-failure behavior is untested.
- Adversarial probe — there is NO test that exercises the `except OSError: continue` branch at line 28-29. No fixture removes a directory mid-walk to simulate the race that the handler ostensibly exists for. The handler is dead code from the test suite's perspective.

## Cross-bucket questions to answer at the end

Q1: Are there error paths that span two sub-buckets (e.g., an F1 catch-all at line 35-36 of `sweep_empty_dirs.py` whose result feeds into an F5 status-equivalence at line 39 — same `removed` list returned regardless of how many silent rmdir failures occurred)?
Q2: What's the worst silent-failure hazard introduced by this PR? Cite `packages/claude-dev-env/scripts/sweep_empty_dirs.py:<line>` or `packages/claude-dev-env/scripts/Install-SweepEmptyDirs.ps1:<line>`. Justify against P0/P1 severity using observable user impact (e.g., a watcher that runs forever and never deletes anything because of a permissions issue, with no log line indicating why).
Q3: Where would a future error-handling refactor most likely *introduce* a silent failure? Name the line(s) most fragile — for instance, adding a top-level `try/except OSError` around the `while True:` loop body in `main()` (lines 73-82) to "make the watcher more resilient" would convert the only loud failure (top-level OSError crash) into a silent infinite-loop sweep-of-nothing.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket F1-F8, produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P1 silent failures across these 8 sub-buckets — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.
