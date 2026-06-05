Audit [REPO/ARTIFACT] [TARGET_ID] for **Category D only** (variable scoping, ordering, and unbound references). Skip A–C, E–N. Sub-bucket forced-exhaustion mode: Category D is decomposed into 8 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA]
- Repo / artifact: [REPO_OR_ARTIFACT]
- Target ID: [TARGET_ID] (e.g., PR number, commit SHA, file path, document name)
- Head SHA / revision: [HEAD_SHA_OR_REVISION]
- Title / summary: [TITLE]
- Files / sections in scope: [LIST_OF_PATHS_OR_SECTIONS]

ID prefix: `find`.

Line-number convention: every `:N` reference points to the file-relative line number of the file inlined in `## Source material` further down. A line citation is verifiable iff the cited number is present in the corresponding file fence below.

## Source material

Inline the artifact under audit using one `###` header per section. Pick the chunk size per the [chunking guide](../source-material-section-types.md): one file per section for code PRs, one function/class per section for long single-module audits, one named heading per section for design docs, etc. Keep section anchors stable and copy-pasteable so findings can cite `<section>:<line>` unambiguously.

```
## Source material ([N] sections, all lines in scope)

### [section-1-anchor]
```[language]
[content]
```

### [section-2-anchor]
```[language]
[content]
```
```

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**D1. Variable referenced before assignment on a branch**
- Identify every name that is assigned on only some branches of an `if`/`elif`/`else`, `try`/`except`/`else`/`finally`, or `match` block, then read after the block. Cite each binding site and each read site by `<section>:<line>`.
- For each `try:` block whose `except` arm uses `continue` / `return` / `raise` / `sys.exit` to short-circuit, prove the read site is unreachable on the failure path. Replace `continue` mentally with `pass` and check whether the next read becomes unbound — that is the adversarial probe.
- Walk every loop, comprehension, and generator and confirm names that are only bound conditionally inside the loop body are not read after the loop terminates with zero iterations (e.g., `for x in xs: ...` followed by `return x` when `xs` may be empty).
- Confirm parameters and locals introduced at the top of a function are bound on every code path that reaches their first read (early-return guards, exception handlers, parser-driven `SystemExit`).

**D2. Loop closure capture (by-ref vs by-value)**
- Walk every `for` / `while` loop body and list any `lambda`, nested `def`, list/dict/set/generator comprehension that defers evaluation, `functools.partial`, `asyncio.create_task`, `threading.Thread`, `multiprocessing` worker, or `concurrent.futures.submit` that closes over the loop variable.
- For language-specific late-binding hazards (Python `lambda` capturing by reference, JavaScript `var` in a `for` loop, PowerShell `ForEach-Object { ... }` script blocks vs `foreach` statement), state which language semantics apply and probe whether the captured name is consumed in the same iteration or stored for later.
- Confirm callbacks registered with event loops, signal handlers, or scheduler hooks do not retain stale references to per-iteration state.

**D3. Name shadowing of outer-scope symbols**
- Enumerate every parameter and local name introduced in each function, then check it against (a) language builtins, (b) module-level imports, (c) class-level attributes still in use within the function. Cite each candidate by `<section>:<line>`.
- For names that are intentionally similar to imported modules (e.g., a parameter named `path` in a file that also imports `pathlib.Path`), confirm the function body resolves the imported symbol correctly at every call site.
- Probe loop / comprehension variables that share a name with an outer-scope symbol the surrounding function still relies on after the loop.
- For shell / scripting languages with implicit pipeline variables (PowerShell `$_`, Bash `$_`, `$@`), verify locally introduced names do not collide with those automatic variables.

**D4. Conditional definition leaving a symbol undefined**
- Find every `try: import X / except ImportError:` block, `if sys.platform == "..."` guard, version-conditional fallback, or feature-flag gate that binds a symbol on only some configurations. For each, cite the binding line and every read site that may execute when the guard is false.
- For installer / orchestration scripts that define variables only on one parameter-set branch (e.g., PowerShell `param(...)` sets, argparse subcommands), confirm every read site is reachable only from a branch where the variable was bound. Trace from each early `return` / `exit` upward.
- Confirm there are no platform-conditional `def` statements that leave a function name unbound on the non-matching platform.

**D5. Mutable default arguments**
- Walk every `def` (and language-equivalent: JavaScript default parameters with object/array literals, Ruby keyword defaults, etc.) and confirm no parameter has a mutable literal as its default — `[]`, `{}`, `set()`, `OrderedDict()`, `dict()` with no args, custom dataclass instances.
- For each `def` with a default argument, state whether the default is immutable (numeric, string, `None`, `tuple()`, `frozenset()`) or potentially mutable. Cite each by `<section>:<line>`.
- Probe-of-absence: state the count "0 across all [N] sections" and list every `def` walked.

**D6. Module-level circular imports / load order**
- For each module imported by the artifact under audit, confirm the import graph has no cycle that could leave a symbol partially bound. Cite every `from X import Y` line.
- Check for runtime `sys.path` mutations or `importlib` calls that occur after a top-level `from ... import`. Confirm the sequence cannot leave a name unbound (the `from` either succeeds and binds the name or raises and aborts module load).
- Identify any import-time side effects (top-level function calls, decorator-driven registration, `__init_subclass__` hooks) that depend on partial-module state.

**D7. Async/sync ordering of side effects**
- Scan the entire artifact for `async def`, `await`, `asyncio.gather` / `asyncio.create_task` / `asyncio.run`, JavaScript `async` / `await` / `Promise.all`, or any other deferred-execution primitive. If any are present, walk the ordering of side effects.
- For each `await` site, identify whether a side effect that should have happened *before* the suspension point is actually flushed before yielding control. Probe what an interleaved coroutine could observe.
- For purely synchronous artifacts, cite proof-of-absence with explicit keyword counts ("0 occurrences of `async`, `await`, `asyncio` across all [N] sections").

**D8. Class-attribute vs instance-attribute confusion**
- For every `class` definition, list each attribute introduced in the class body (class attribute) versus inside `__init__` / `__post_init__` / a factory classmethod (instance attribute). Cite each by `<section>:<line>`.
- For each method, walk every `cls.x` and `self.x` access and confirm the access kind matches the attribute's binding site. Probe whether mutation of a class-level mutable (e.g., `cls.cache = {}` shared across instances) is intended or accidental.
- For artifacts with no `class` definitions, cite proof-of-absence by scanning every section for the `class ` keyword and stating the count.

## Cross-bucket questions to answer at the end

Q1: Is there any sub-bucket overlap — i.e., a single line that triggers more than one of D1–D8 simultaneously (e.g., a name that is both shadowed AND only conditionally bound)? Cite every overlapping site by `<section>:<line>` for each bucket it implicates.

Q2: What is the worst unbound-reference hazard a future refactor could introduce by editing the highest-risk loop or branch in the artifact? Name the specific line and the minimal one-token change (e.g., replacing `continue` with `pass`, moving a check above its `try:`, extracting a nested helper) that would convert a currently-clean call into an unbound-name error.

Q3: Among all variables read in the artifact's main entry point or top-level function, which one's binding context is most fragile to the addition of a new flag, parameter, or conditional branch — i.e., which one would silently become read-before-assigned if a maintainer wrapped its assignment in a new `if`? Name the line and the hypothetical branch.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket D1–D8, produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1–Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P1 scoping bugs across these 8 sub-buckets — find them." Open Questions section for ambiguities. Severity quota for the adversarial-pass minimum: P1. Read-only. No edits, no commits.

---

# Worked example: jl-cmd/claude-code-config PR #394

Audit jl-cmd/claude-code-config PR #394 for **Category D only** (variable scoping, ordering, and unbound references). Skip A–C, E–N. Sub-bucket forced-exhaustion mode: Category D is decomposed into 8 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

PR: feat(scripts): add sweep-empty-dirs utility and scheduled-task installer
Head SHA: 62c9c169ee7a44824e5da25c4cf8b74fdca08a53
ID prefix: `find`.

Line-number convention: every `:N` reference below points to the file-relative line number of the file inlined in `## Diff (4 new files, all lines in scope)` further down. The four files in scope are `packages/claude-dev-env/scripts/sweep_empty_dirs.py`, `packages/claude-dev-env/scripts/config/sweep_config.py`, `packages/claude-dev-env/scripts/tests/test_sweep_empty_dirs.py`, and `packages/claude-dev-env/scripts/Install-SweepEmptyDirs.ps1`. A line citation in this prompt is verifiable iff the cited number is present in the corresponding file fence below.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**D1. Variable referenced before assignment on a branch** ⭐ canonical D case for this PR
- The block at `sweep_empty_dirs.py:26-36` assigns `created` only inside `try:` (line 27, `created = os.path.getctime(each_directory_path)`) and uses it at `sweep_empty_dirs.py:30` (`if now - created >= min_age_seconds:`). The `except OSError:` arm at lines 28-29 calls `continue`, which skips the rest of the loop body. Verify the control-flow claim explicitly: when `os.path.getctime` raises, does control re-enter line 30 with `created` unbound, or does `continue` short-circuit to the next `os.walk` iteration?
- The `except OSError: continue` arm on line 28-29 is the only path on which `created` could be unbound at line 30. If the loop body were ever reordered so the `if` ran before the `except` handler, or if `continue` were replaced with `pass` (or `return None`, or a `log()` call with no jump), line 30 would read an unbound name. Note this in the proof and cite the two lines (28, 30) that make `continue` load-bearing.
- Inside the inner `try:` at `sweep_empty_dirs.py:31-36`, no name introduced on line 32-34 (`os.rmdir(...)`, the literal `f"deleted: ..."` string, `removed.append(...)`) is read after the `except OSError: pass` arm, so the inner block has no D1 hazard. State this explicitly.
- Verify `now` (`sweep_empty_dirs.py:20`), `removed` (`sweep_empty_dirs.py:21`), and the loop variable `each_directory_path` (`sweep_empty_dirs.py:23`) are each bound before every site that reads them. `removed` is read at line 38 (`return removed`) — confirm the loop never raises out without binding `removed` (it is bound before the loop on line 21, so this is safe).
- In `main()` (`sweep_empty_dirs.py:53-71`), the variable `arguments` (line 55) is read on lines 57, 58, 61, 62, 65, 68 — confirm `parse_args()` either returns or raises (`SystemExit`); it cannot leave `arguments` unbound at any read site. State this explicitly.

**D2. Loop closure capture (by-ref vs by-value)**
- The only loop in production code is `sweep_empty_dirs.py:23-36` (`for each_directory_path, _, _ in os.walk(...)`). Walk every line inside that loop body and confirm: no `lambda` keyword, no nested `def`, no `asyncio.create_task` / `threading.Thread` / `multiprocessing` / `concurrent.futures.submit`, no list/dict/set comprehension that defers evaluation, no `functools.partial` capturing `each_directory_path`. The body only calls module-level functions (`os.path.getctime`, `os.rmdir`, `print`, `removed.append`) directly, so `each_directory_path` is consumed in the same iteration it is bound.
- The PowerShell `foreach` loops at `Install-SweepEmptyDirs.ps1:30-32` and `Install-SweepEmptyDirs.ps1:34-36` iterate over `$task.Actions` and `$task.Triggers` and only call `Write-Host` with the current iteration's variable inside `$(...)` subexpressions. PowerShell `foreach` binds the iterator variable by value to the local scope on each iteration, and there are no script blocks (`{ ... }` passed to `ForEach-Object` or stored as `[scriptblock]`) that would defer evaluation. Confirm by walking lines 30, 31, 32, 34, 35, 36.
- The `while True:` loop at `sweep_empty_dirs.py:67-69` has no nested closures or deferred callbacks; it only calls `sweep(...)` and `time.sleep(...)` synchronously. The `try:`/`except KeyboardInterrupt:` (lines 66-71) wraps the whole loop, so no callback is registered with the event loop or signal handler.

**D3. Name shadowing of outer-scope symbols**
- Walk every parameter and local name introduced in `sweep_empty_dirs.py` and check against Python builtins and module-level imports (`argparse`, `os`, `sys`, `time`, `DEFAULT_AGE_SECONDS`, `DEFAULT_POLL_INTERVAL`):
  - `os_error: OSError` (`sweep_empty_dirs.py:13`) — does NOT shadow the imported `os` module (the suffix `_error` disambiguates). Confirm by checking that `os.path.getctime` (line 27), `os.walk` (line 23), `os.rmdir` (line 32), `os.path.isdir` (line 57) all still resolve to the module.
  - `root: str` (`sweep_empty_dirs.py:17`, also used as `arguments.root` on lines 57, 58, 62, 65, 68) — not a builtin; not an imported symbol. Safe.
  - `min_age_seconds: int` (`sweep_empty_dirs.py:17`) — not a builtin; not an imported symbol. Safe.
  - `now` (`sweep_empty_dirs.py:20`) — not a builtin (`time.time` is the source; `now` is a local name). Safe.
  - `removed: list[str]` (`sweep_empty_dirs.py:21`) — not a builtin; safe.
  - `each_directory_path` (`sweep_empty_dirs.py:23`) — loop variable; not a builtin; safe.
  - `created` (`sweep_empty_dirs.py:27`) — not a builtin; safe.
  - `parser` (`sweep_empty_dirs.py:42`, `sweep_empty_dirs.py:54`) — not a builtin; the local in `main()` shadows nothing (`_build_parser` returns a fresh object). Safe.
  - `arguments` (`sweep_empty_dirs.py:55`) — not a builtin; not an imported symbol. Safe.
- Verify that the test file's local names (`tmp`, `empty_dir`, `fresh_dir`, `leaf`, `nonempty_dir`, `removed`, `path`, `timestamp`, `dt`, `date_str`) at `test_sweep_empty_dirs.py:31-76` do not shadow any of the imports `datetime`, `os`, `subprocess`, `sys`, `tempfile`, `time`, `Path`. In particular, `path: str` (line 21) is a parameter name and is shadowed-by-design — confirm the function body (lines 22-28) never references the imported `Path` (it doesn't; it uses `subprocess.run` only).
- Verify the `date_str` (`test_sweep_empty_dirs.py:23`) and `dt` (line 22) names are short and do NOT collide with stdlib types (`datetime.datetime` is referenced via the imported `datetime` module on line 22, not via a local `datetime` rebind). State whether `datetime` is rebound anywhere in the file (it is not).
- The PowerShell variable `$_py` (`Install-SweepEmptyDirs.ps1:64`) does NOT shadow the automatic variable `$_` (PowerShell's pipeline current-object variable). PowerShell distinguishes `$_` from `$_py` — confirm by reading lines 64-65 and noting that no pipeline expression on those lines relies on `$_`.

**D4. Conditional definition leaving a symbol undefined**
- `sweep_empty_dirs.py` has zero `try: import X / except ImportError:` blocks; every import (lines 4-7, 9-10) is unconditional and at module top.
- `sweep_empty_dirs.py` has zero `if sys.platform == "..."` guards. The script's Windows-only behavior (Windows-style creation timestamps, scheduled-task helper) is implicit, not gated. State explicitly that no symbol is platform-conditionally bound.
- The `_set_creation_time_windows` helper (`test_sweep_empty_dirs.py:21-28`) is unconditionally defined and unconditionally called from every test function (`test_sweep_empty_dirs.py:35, 54, 55, 56, 65`). It is NOT wrapped in `if sys.platform == "win32":` — but the audit treats that as a cross-cutting concern (test will fail on non-Windows due to `subprocess.run(["powershell", ...])`), not as a D4 *unbound-name* hazard.
- `Install-SweepEmptyDirs.ps1` defines `$ScriptDir`, `$ScriptPath`, `$_py`, `$PythonPath`, `$Action`, `$Trigger`, `$Settings` (lines 46-72) only on the install path (when `$Status` and `$Remove` are both falsy — both early-return on lines 25, 37, 43). The `Register-ScheduledTask` line at `Install-SweepEmptyDirs.ps1:74` reads `$Action`, `$Trigger`, `$Settings` — confirm these reach line 74 only when the `$Status` and `$Remove` early returns at lines 25, 37, 43 did not fire.

**D5. Mutable default arguments**
- `sweep_empty_dirs.py` has zero functions with mutable defaults. Walk each `def`:
  - `_log_walk_error(os_error: OSError)` (`sweep_empty_dirs.py:13`) — no defaults.
  - `sweep(root: str, min_age_seconds: int)` (`sweep_empty_dirs.py:17`) — no defaults.
  - `_build_parser()` (`sweep_empty_dirs.py:41`) — no defaults.
  - `main()` (`sweep_empty_dirs.py:53`) — no defaults.
- `test_sweep_empty_dirs.py` has zero functions with mutable defaults. Walk each `def`:
  - `_set_creation_time_windows(path: str, timestamp: float)` (`test_sweep_empty_dirs.py:21`) — both defaults absent.
  - The five `test_*` functions (lines 31, 41, 50, 63, 69) — all parameterless.
- Confirm there are zero `def f(... = [])`, `def f(... = {})`, `def f(... = set())`, `def f(... = OrderedDict())` constructs in the entire diff. State the proof-of-absence with the count "0 across all four files".

**D6. Module-level circular imports / load order**
- `sweep_empty_dirs.py` imports from `config.sweep_config` (lines 9-10). `config/sweep_config.py` defines two module-level constants (`DEFAULT_AGE_SECONDS`, `DEFAULT_POLL_INTERVAL`) and imports nothing. Confirm there is no `from sweep_empty_dirs import X` anywhere in `config/sweep_config.py` — i.e., no cycle.
- `test_sweep_empty_dirs.py` does a runtime `sys.path` mutation (`test_sweep_empty_dirs.py:14-16`) and then imports `from sweep_empty_dirs import sweep` at line 18. Confirm this sequence cannot leave `sweep` unbound: the `sys.path.insert` at line 16 is inside an `if` (line 15) but the `from ... import` at line 18 is unconditional, so the import either succeeds (binds `sweep`) or raises (test collection fails loudly). No partial-binding hazard.
- `sweep_empty_dirs.py` has zero import-time side effects (no top-level function calls beyond `def`/`from`/`import`). The entry point at `sweep_empty_dirs.py:74-75` is the standard `if __name__ == "__main__": main()` guard, which is not a load-order hazard.

**D7. Async/sync ordering of side effects**
- This PR contains zero `async def` definitions, zero `await` expressions, zero `asyncio.gather` / `asyncio.create_task` / `asyncio.run` calls. Confirm by scanning all four files for the keywords `async`, `await`, `asyncio`. Cite proof-of-absence.
- The synchronous loop at `sweep_empty_dirs.py:67-69` performs side effects (filesystem deletions inside `sweep`, then `time.sleep`) in straight-line order. There is no event-loop interleaving and no concurrent task that could observe an intermediate state.
- The PowerShell installer is also entirely synchronous; `New-ScheduledTaskAction`, `New-ScheduledTaskTrigger`, `New-ScheduledTaskSettingsSet`, `Register-ScheduledTask` (lines 70-74) execute in declared order. No `Start-Job`, no `Start-ThreadJob`, no `-AsJob` flag.

**D8. Class-attribute vs instance-attribute confusion**
- This PR contains zero `class` definitions across all four files. Confirm by scanning each file for the `class ` keyword (Python) and `class { ... }` blocks (PowerShell). Cite proof-of-absence — no `cls.x` / `self.x` / `__init__` / class-body assignments exist, so D8 is structurally inapplicable to this artifact.

## Cross-bucket questions to answer at the end

Q1: Does the `try: created = os.path.getctime(...) / except OSError: continue` block at `sweep_empty_dirs.py:26-30` carry any sub-bucket overlap (e.g., is `created` *also* shadowing a wider-scope name that would be read on the `continue` path)? Cite both the D1 site and the D3 site if so.
Q2: What's the worst unbound-reference hazard a future refactor could introduce by editing the loop body at `sweep_empty_dirs.py:23-38`? Name the line that, if changed (e.g., replacing `continue` with `pass`, or moving the `if now - created` check above the `try:`, or extracting a nested helper), would convert a currently-clean call into an `UnboundLocalError`.
Q3: Among the variables read in `main()` (`sweep_empty_dirs.py:53-71`), which one's binding context is most fragile to the addition of a new `argparse` flag or a new conditional branch — i.e., which one would silently become read-before-assigned if a maintainer wrapped its assignment in a new `if`? Name the line and the hypothetical branch.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket D1–D8, produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1–Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P1 scoping bugs across these 8 sub-buckets — find them." Open Questions section for ambiguities. Severity quota for the adversarial-pass minimum: P1. Read-only. No edits, no commits.

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
