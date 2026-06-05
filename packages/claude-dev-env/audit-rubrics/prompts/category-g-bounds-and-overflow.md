Audit [REPO/ARTIFACT] [TARGET_ID] for **Category G only** (off-by-one, bounds, integer overflow). Skip A–F, H–N. Sub-bucket forced-exhaustion mode: Category G is decomposed into 8 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA]
- Repository / artifact: [REPO_OR_ARTIFACT]
- Target ID (PR / commit / tag / file set): [TARGET_ID]
- Head SHA / revision: [HEAD_SHA]
- Title or summary: [TITLE]
- Languages / runtimes in scope: [LANGS]

ID prefix: `find`.

## Source material

Inline the artifact under this section (full diff for a PR, full file bodies for a file-set audit, or a representative slice for an oversized artifact). For chunking strategy, file inclusion order, and "all lines in scope" framing, follow the companion chunking guide referenced by the rubric (`../source-material-section-types.md`). When a single artifact exceeds the prompt budget, split into ordered chunks and re-run this prompt per chunk; each chunk must independently satisfy the per-sub-bucket Shape A / Shape B requirement against the lines it contains.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**G1. Loop bounds**
Scope: every `range(...)`, `while i < n`, `for i in range(len(x)+1)`, manual index counters, generator-driven loops, recursion depth bounds, and any inclusive-vs-exclusive iteration boundary in the artifact.
Required output: at least one Shape A finding citing the off-by-one site, OR exactly one Shape B proof-of-absence with ≥3 adversarial probes (e.g., (a) is there an implicit upper bound an iterator could miss — symlink loops, infinite generators, deep recursion? (b) does an empty-collection edge case skip the loop body cleanly? (c) does a manual counter that runs alongside the iterator drift by one when the underlying collection mutates mid-loop?).

**G2. Slice / substring indices**
Scope: every `s[i:j]`, `arr[-n:]`, `split(...)[i]`, character-level indexing, regex match groups treated as substrings, and any computed slice endpoint that could equal `len(x) + 1` or a negative index that clamps unexpectedly.
Required output: Shape A citing the bad slice, OR Shape B with ≥3 adversarial probes (e.g., (a) does any consumer downstream apply a length-dependent truncation? (b) does a path-splitting helper underflow when its input is exactly the root? (c) can a regex group index be `0` for a non-matching capture and still be sliced into?).

**G3. Array / list indexing with computed offsets**
Scope: every `arr[i + offset]`, `dict[computed_key]` where the key is numeric, off-the-end probes (`arr[len(arr)]`), iterator advancement that returns a sentinel the next call dereferences, and PowerShell `$collection[$index]` with computed `$index`.
Required output: Shape A citing the index site, OR Shape B with ≥3 adversarial probes (e.g., (a) can a lookup return `$null` / `None` that the next access dereferences? (b) does an argv-style list ever get indexed past its known length? (c) does a `foreach` element receive a `$null` member from an empty collection?).

**G4. Integer arithmetic overflow** ⭐ canonical surface
Scope: 32-bit vs 64-bit assumptions; PowerShell `[int]` overflow at 2^31; `time.time() * 1000` precision loss; multiplication that crosses platform `int` ceilings; counters seeded from user input; ticks / nanoseconds / milliseconds conversions; cross-language defaults that share a magnitude but not a source of truth.
Required output: Shape A citing the overflow site or the duplicated-default drift hazard, OR Shape B with ≥3 adversarial probes (e.g., (a) what happens at `2^31 - 1` and `2^31` for each `[int]`-typed parameter? (b) is `0` accepted as a degenerate value that produces a busy loop or a zero-interval scheduler entry? (c) are equivalent constants declared in two languages without a shared source of truth — and does drift on one side go undetected?).

**G5. Floating-point comparison**
Scope: every `==` / `!=` / `>=` / `<=` between floats; iterative accumulators where epsilon noise compounds; `0.1 + 0.2 != 0.3` patterns; mixed int-float comparison; filesystem-resolution rounding (FAT32 = 2s, NTFS = 100ns, ext4 = ns) interacting with sub-second thresholds.
Required output: Shape A citing the float-equality or epsilon-free comparison, OR Shape B with ≥3 adversarial probes (e.g., (a) is the comparison `==` vs `>=` / `<=` — and does the boundary semantics matter? (b) does sub-second filesystem-resolution rounding on one platform produce stale-equality results that another platform avoids? (c) is the float subtraction monotonic under wall-clock adjustment, or could it produce a negative result that flips the comparison direction?).

**G6. Date / time arithmetic** ⭐ canonical surface
Scope: timezone math; DST transitions; leap seconds; `now - then >= threshold` precision; `time.time()` (wall-clock) vs `time.monotonic()` / `time.perf_counter()` selection; Unix epoch vs Windows FILETIME (100ns ticks since 1601); `[DateTime]` cast on strings without timezone suffix; cross-language datetime contracts.
Required output: Shape A citing the timezone-naive arithmetic or the wall-clock-vs-monotonic mismatch, OR Shape B with ≥3 adversarial probes (e.g., (a) is the threshold wide enough to absorb worst-case NTP slew (≤128ms typical) without flipping the comparison? (b) does a cross-language string-based datetime contract silently discard timezone information? (c) does the platform-dependent meaning of "ctime" (creation time on Windows, inode-change time on POSIX) match the test's assumption?).

**G7. Unicode codepoint vs byte length**
Scope: `len()` semantics (Python = codepoints, Go = bytes, JS = UTF-16 code units); UTF-8 encoded byte-length truncation that splits mid-codepoint; surrogate pairs; BMP vs non-BMP characters; argv encoding across `subprocess.run` / `CreateProcessW` / `execve`.
Required output: Shape A citing the codepoint/byte mismatch, OR Shape B with ≥3 adversarial probes (e.g., (a) does any consumer apply a byte-length cap that could split a UTF-8 codepoint? (b) does a directory walker decode names as raw bytes (POSIX `surrogateescape`) vs UTF-16 (Windows) in a way that affects which entries are seen? (c) do non-BMP characters round-trip correctly through subprocess argv encoding?).

**G8. Threshold and age comparisons** ⭐ canonical surface
Scope: every `>=` vs `>` boundary on age / size / count thresholds; inclusive-vs-exclusive semantics; docstring/help-text/code disagreement on boundary direction; tests that exercise comfortably-above and comfortably-below cases but skip the exact-boundary case; user-facing copy that uses one symbol while the code uses another.
Required output: Shape A citing the boundary-semantics conflict (code site + docstring/help-text/UI site), OR Shape B with ≥3 adversarial probes (e.g., (a) is the inclusive-vs-exclusive choice safe under sub-second filesystem-resolution rounding that could land a "fresh" value at exactly the boundary? (b) does any test seed a value at exactly the threshold to exercise the boundary? (c) do user-facing strings use `≥` / `>` symbols faithful to the code, and does the docstring agree?).

## Cross-bucket questions to answer at the end

Q1: Are there boundary hazards that span two sub-buckets — e.g., a G6 timestamp imprecision that combines with a G8 inclusive comparison to flip a borderline case, or a G4 overflow that interacts with a G1 loop bound to produce an infinite iteration? Cite the line pair.
Q2: What's the worst boundary hazard introduced by this artifact? Cite `[file]:[line]` (and any companion file:line if the hazard is multi-site).
Q3: Which threshold or constant is most fragile to a future change in input scale (e.g., shifting from minute-scale ages to second-scale, or from 2-minute defaults to 2-millisecond defaults)? Identify the line(s) where the unit assumption is hardcoded.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket G1-G8, produce Shape A or Shape B (with ≥3 probes). Each Shape A finding must cite the file:line where the boundary or numeric type fails. Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P1 boundary or overflow bugs across these 8 sub-buckets — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

---

# Worked example: jl-cmd/claude-code-config PR #394

Audit jl-cmd/claude-code-config PR #394 for **Category G only** (off-by-one, bounds, integer overflow). Skip A–F, H–N. Sub-bucket forced-exhaustion mode: Category G is decomposed into 8 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

PR: feat(scripts): add sweep-empty-dirs utility and scheduled-task installer
Head SHA: 62c9c169ee7a44824e5da25c4cf8b74fdca08a53
ID prefix: `find`.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**G1. Loop bounds**
- The only iteration in `sweep_empty_dirs.py` is `for each_directory_path, _, _ in os.walk(root, onerror=_log_walk_error, topdown=False):` at lines 23-25 — `os.walk` is iterator-driven with no explicit numeric range, no `range()`, no `while i < n` counter.
- The only `while` is `while True:` at line 67 inside `main()`'s loop branch, terminated by `KeyboardInterrupt` — no numeric bound to be off-by-one against.
- Shape B probes: (a) is there an implicit upper bound that `os.walk` could miss (symlink loops creating infinite descent, very deep trees hitting `MAXPATHLEN`)? (b) does `topdown=False` interact with the iteration count when the root contains 0 entries — does the loop body even execute, or is the post-condition `removed = []` returned cleanly? (c) the test at line 62-65 (`test_empty_root_does_not_crash`) iterates a root that itself was aged to `time.time() - 300` — does `os.walk` yield the root itself, and if so does `os.rmdir` attempt to delete `tempfile.TemporaryDirectory`'s own directory while the context manager still holds it?

**G2. Slice / substring indices**
- No string or list slicing in any of the four files. No `s[i:j]`, no `arr[-n:]`, no `split(...)[i]` indexing, no `[0]`/`[1]`/`[-1]` element access.
- `os.path.join(tmp, "parent", "child", "leaf")` at test line 51 builds a path; no slice operations on the result.
- Shape B probes: (a) does the f-string `f"warning: cannot scan {os_error.filename} — {os_error.strerror}"` at line 14 of `sweep_empty_dirs.py` perform any implicit truncation that depends on filename length? (b) does `os.path.join` ever produce a string the consumer slices downstream? (c) the PowerShell `Split-Path -Parent $PSCommandPath` at line 46 of `Install-SweepEmptyDirs.ps1` — does it index a substring that could underflow when `$PSCommandPath` is exactly the drive root?

**G3. Array / list indexing with computed offsets**
- `removed: list[str] = []` at line 21 is only ever appended to (line 34) and returned (line 38) — no index access into `removed`.
- Test asserts use membership (`assert empty_dir in removed`, lines 36, 45, 57, 58, 59, 74) — no positional indexing.
- The PowerShell `foreach ($action in $task.Actions)` and `foreach ($trigger in $task.Triggers)` at lines 30, 34 of `Install-SweepEmptyDirs.ps1` iterate by element, not by index.
- Shape B probes: (a) does `Get-ScheduledTask` ever return `$null` in a way that makes `$task.Actions` an indexer-into-null? (b) does `_set_creation_time_windows` ever receive a path that exceeds `MAX_PATH` (260 chars on Windows pre–long-path) such that `subprocess.run`'s argv list overflows? (c) does the `["powershell", "-Command", ...]` argv list at lines 24-26 of the test file ever produce a fourth element that an `argv[i]` consumer would expect at index 2?

**G4. Integer arithmetic overflow** ⭐ canonical surface
- Python side: `DEFAULT_AGE_SECONDS: int = 120` and `DEFAULT_POLL_INTERVAL: int = 30` at lines 3-4 of `sweep_config.py`. Python `int` is arbitrary precision — no 32-bit ceiling. `argparse` `type=int` (lines 44, 48 of `sweep_empty_dirs.py`) likewise produces a Python int. `time.sleep(arguments.interval)` at line 69 accepts any non-negative number; no overflow risk on the value itself.
- PowerShell side: `[int]$IntervalMinutes = 5` (line 7) and `[int]$AgeSeconds = 120` (line 10) of `Install-SweepEmptyDirs.ps1`. `[int]` in PowerShell is `System.Int32` — range `-2147483648` to `2147483647`. Both defaults are 4-5 orders of magnitude below the ceiling. The user-overridable values would have to exceed 2^31-1 (≈ 68 years in seconds, ≈ 4084 years in minutes) to overflow.
- `New-TimeSpan -Minutes $IntervalMinutes` at line 71 of `Install-SweepEmptyDirs.ps1`: `TimeSpan` is internally `Int64` ticks (100ns each). 5 minutes × 60 × 10⁷ = 3×10⁹ ticks — well within `Int64` range. Even 4084-year overflow on `[int]$IntervalMinutes` would be caught at the `[int]` cast, not at the `TimeSpan` construction.
- Cross-language defaults: PowerShell `[int]$AgeSeconds = 120` (line 10) is passed through argv as the bare token `120` to Python's `argparse type=int`. Python parses it back to an arbitrary-precision int. No precision drift at this magnitude. **But:** the two defaults (PS line 10 and Python sweep_config.py line 3) are independently hardcoded with no shared source of truth — drift in a future edit is the real G4 hazard, not arithmetic overflow today.
- Shape A candidate (P2): `[int]$AgeSeconds = 120` and `DEFAULT_AGE_SECONDS: int = 120` are duplicated literals across two files with no validation that they match. A future edit to one without the other produces a silent default drift. Cite `Install-SweepEmptyDirs.ps1:10` and `sweep_config.py:3`.
- Adversarial probes: (a) what happens if the user invokes `Install-SweepEmptyDirs.ps1 -AgeSeconds 2147483648`? PowerShell's `[int]` cast would throw at parameter binding — verify whether the script handles this or crashes uninformatively. (b) `New-TimeSpan -Minutes` accepts `[int32]` per Microsoft docs — is `$IntervalMinutes = 0` accepted, and does `-RepetitionInterval (TimeSpan.Zero)` register a degenerate task? (c) `time.sleep(arguments.interval)` at line 69 with `arguments.interval = 0` — does the busy loop spin without yielding to the OS?

**G5. Floating-point comparison**
- `now = time.time()` at line 20 of `sweep_empty_dirs.py` returns `float` (seconds since epoch, sub-second precision).
- `created = os.path.getctime(each_directory_path)` at line 27 returns `float`.
- `if now - created >= min_age_seconds:` at line 30 — float minus float compared against `int` (`min_age_seconds: int`). Python promotes the int to float for comparison. The comparison is `>=`, not `==`, so IEEE-754 epsilon noise does not produce stale-result equality bugs of the `0.1 + 0.2 != 0.3` kind.
- The float subtraction `now - created` carries ~15-16 significant decimal digits. For Unix timestamps in 2026 (~1.78×10⁹), epsilon-magnitude noise is on the order of 10⁻⁷ seconds — irrelevant against a 120-second threshold.
- Shape B probes: (a) for very small `min_age_seconds` (e.g., `min_age_seconds=0` as in `test_skips_nonempty_dir` at line 73), the comparison `now - created >= 0` is dominated by `getctime` filesystem-resolution rounding (FAT32 = 2-second granularity, NTFS = 100ns) — does this matter for the test's intent? (b) does `time.time()` ever return a value equal to `os.path.getctime` for a directory just created, producing `0.0 >= 0` = True and immediate deletion? (c) is the float subtraction monotonic under wall-clock adjustment (NTP slew, manual clock change) — could `now < created` produce a negative result that compares False against a positive `min_age_seconds`?

**G6. Date / time arithmetic** ⭐ canonical surface
- `time.time()` at line 20 of `sweep_empty_dirs.py` returns a UTC-anchored Unix timestamp (seconds since 1970-01-01T00:00:00Z) per Python docs. There is no DST math, no timezone arithmetic, no leap-second handling in the file.
- `os.path.getctime` at line 27 also returns a UTC-anchored Unix timestamp (the platform-dependent "ctime" — on Windows this is creation time, on POSIX it is inode-change time). The two values are in the same units and the same epoch, so the subtraction at line 30 (`now - created`) is dimensionally consistent.
- Wall-clock vs monotonic: `time.time()` is wall-clock and subject to NTP adjustment, manual clock changes, and (theoretically) leap-second smearing. For age comparisons against a 2-minute default this is robust; for sub-second thresholds it would not be. The rubric calls out `time.time()` precision vs `time.monotonic()` / `time.perf_counter()` — verify whether the 2-minute default is wide enough to absorb a worst-case 1-second NTP slew.
- The test file at lines 21-22 builds a UTC `datetime` and formats it as `"%Y-%m-%d %H:%M:%S"` (no timezone suffix in the format string) and passes it to PowerShell `[DateTime]'{date_str}'`. PowerShell's `[DateTime]` cast on a string with no timezone parses as `Kind=Unspecified`, then assignment to `.CreationTimeUtc` reinterprets it as UTC. **This is a fragile contract:** if the format string ever included `%z`, PowerShell's `[DateTime]` cast would still discard the offset.
- Adversarial probes: (a) is the 120-second default wide enough that NTP slew (typically ≤128ms per `ntpd`) cannot push `now - created` below the threshold for a directory that should be deleted? (b) does `os.path.getctime` on Windows return file creation time or inode-change time — and does this match the test's assumption when `_set_creation_time_windows` mutates `CreationTimeUtc`? (c) the test at lines 34, 53, 54, 55, 64 passes `time.time() - 300` to `_set_creation_time_windows` — by the time PowerShell runs and writes `CreationTimeUtc`, additional wall-clock seconds have elapsed; does the 300-second offset have enough margin against a slow CI runner?
- Shape A candidate (P1, intended-behavior question): `if now - created >= min_age_seconds` at line 30 includes the boundary. Combined with the docstring at line 2 saying "older than 2 minutes," the boundary semantics may not match the docstring (see G8).

**G7. Unicode codepoint vs byte length**
- Python `len(...)` is never called on any string in `sweep_empty_dirs.py` or `sweep_config.py`. No length-based decisions.
- The test file's `subprocess.run(["powershell", "-Command", f"(Get-Item '{path}').CreationTimeUtc = ..."])` at lines 23-26 embeds `path` directly into a PowerShell command string. If `path` contains a single quote, the embedded single quote terminates the literal early — but this is a quoting/injection concern (Category C), not a codepoint vs byte length concern. There is no `len(path)` check upstream.
- The PowerShell `Write-Host` lines (e.g., line 75 of `Install-SweepEmptyDirs.ps1`) use string interpolation but no character/byte counting.
- Shape B probes: (a) does any consumer of `_log_walk_error`'s output (line 14) — for example, log forwarding or stderr capture — apply a byte-length truncation that mid-codepoint splits a UTF-8-encoded `os_error.filename`? (b) does `os.walk` decode directory names from raw bytes (POSIX) vs UTF-16 (Windows) in a way that affects which entries are seen — the `surrogateescape` boundary on Linux? (c) PowerShell's `Get-Item '{path}'` at test line 25 — does `'{path}'` containing non-BMP characters (codepoints above U+FFFF) get correctly round-tripped through `subprocess.run`'s argv encoding (Windows uses UTF-16 internally, but `subprocess.run` on Python 3.6+ uses CreateProcessW so this is normally fine)?

**G8. Threshold and age comparisons** ⭐ canonical surface
- `if now - created >= min_age_seconds:` at line 30 of `sweep_empty_dirs.py` uses `>=`, which means a directory whose age is **exactly** `min_age_seconds` IS deleted (the boundary fires).
- The docstring at line 2 reads: `"""Delete empty directories older than 2 minutes under a given root."""` — strict reading of "older than" suggests `>` (exclusive boundary).
- The argparse help text at line 45 reads: `f"Minimum age in seconds (default: {DEFAULT_AGE_SECONDS} = 2 minutes)"` — "minimum age" wording is ambiguous: a "minimum of 2 minutes" can be interpreted as "≥ 2 minutes" (matches the code) OR as "must exceed the 2-minute floor" (matches the docstring).
- The test at lines 30-37 (`test_deletes_empty_dir_older_than_threshold`) seeds `time.time() - 300` (300s old) against `min_age_seconds=120` — comfortably above the boundary, does not exercise the exact-boundary case.
- The test at lines 40-46 (`test_skips_empty_dir_newer_than_threshold`) seeds a fresh directory (age ≈ 0s) against `min_age_seconds=120` — comfortably below the boundary, does not exercise the exact-boundary case.
- The test at lines 68-75 (`test_skips_nonempty_dir`) passes `min_age_seconds=0` against a fresh directory. With `>=`, `now - created >= 0` is True (the age is at-or-past the zero boundary), so the only thing keeping the directory alive is `os.rmdir` raising `OSError` because the directory is non-empty (line 35 `except OSError: pass`). This is a load-bearing test that verifies non-emptiness rather than age — but it relies on `>=` semantics; with `>` (strict), the directory would also be skipped because `0 > 0` is False.
- Shape A candidate (P1): Boundary semantics conflict between code (line 30: `>=`, inclusive) and docstring (line 2: "older than", suggests exclusive `>`). Cite the conflict pair.
- Shape A candidate (P2 alternative): The age threshold inclusivity is not exercised by any test. Cite line 30 (the `>=` site) and the absence of an exact-120s test in `test_sweep_empty_dirs.py`.
- Adversarial probes for the `>=` boundary: (a) does a directory created at exactly `now - 120.0` seconds match the spirit of "older than 2 minutes" (no, by strict reading) or the letter of the code (yes)? (b) is the inclusive-boundary semantics safe under sub-second filesystem-resolution rounding (FAT32's 2-second granularity could land a "fresh" directory at exactly the boundary)? (c) does the PowerShell installer's `Write-Host` at line 75 (`age ≥ ${AgeSeconds}s`) document the inclusive boundary correctly — the `≥` symbol in the user-facing message is faithful to the code at sweep_empty_dirs.py:30, but the Python docstring at sweep_empty_dirs.py:2 says "older than" — three sites, two interpretations.

## Cross-bucket questions to answer at the end

Q1: Are there boundary hazards that span two sub-buckets — e.g., a G6 timestamp imprecision that combines with a G8 inclusive comparison to flip a borderline case? Cite the line pair.
Q2: What's the worst boundary hazard introduced by this PR? Cite `packages/claude-dev-env/scripts/sweep_empty_dirs.py:<line>` (and any companion file:line if the hazard is multi-site).
Q3: Which threshold or constant is most fragile to a future change in input scale (e.g., shifting from minute-scale ages to second-scale, or from 2-minute defaults to 2-millisecond defaults)? Identify the line(s) where the unit assumption is hardcoded.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket G1-G8, produce Shape A or Shape B (with ≥3 probes). Each Shape A finding must cite the file:line where the boundary or numeric type fails. Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P1 boundary or overflow bugs across these 8 sub-buckets — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

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
