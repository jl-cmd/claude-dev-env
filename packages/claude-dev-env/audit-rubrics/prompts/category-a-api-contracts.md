Audit [REPO/ARTIFACT] [TARGET_ID] for **Category A only** (API contract verification). Skip B–P. Sub-bucket forced-exhaustion mode: Category A is decomposed into 9 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA: title / change description / head SHA or revision identifier / scope summary]
ID prefix: `find`.

## Source material ([N] files/sections, all lines in scope)

[INLINE THE FULL ARTIFACT HERE — see ../source-material-section-types.md for chunking guidance.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**A1. Function/method signatures vs internal call sites**
- Enumerate every defined function or method's parameter list: count, names, defaults, kw-only barriers (Python `*`), positional-only barriers (`/`), variadic markers (`*args`, `**kwargs`).
- For every internal call within the artifact, verify the binding matches the callee's signature: positional count, keyword names, required-vs-optional, default fall-through.
- Flag positional arguments passed to keyword-only parameters and vice versa.
- Flag calls that omit a required parameter relying on a default that does not exist on the current branch.
- Verify decorators (`@staticmethod`, `@classmethod`, `@property`) do not silently shift the parameter binding (e.g., `self` / `cls` insertion).
- Confirm sync-vs-async (is the symbol `async def`?), the exact access path a caller uses (free function vs instance method via an object attribute vs import path), and that a keyword-only parameter with no default is required — omitting it raises `TypeError`.

**A2. Return-type annotation vs every code path**
- For each annotated function, walk every code path: explicit `return X`, fall-through to implicit `None`, exception-handler exit, generator `yield` paths, async coroutine return value.
- Verify each path's actual return value is assignable to the declared annotation; flag `-> bool` functions that can return `None`, `-> list[T]` functions that can return `None` on an early exit, etc.
- For functions that raise instead of returning on some path, confirm the annotation does not promise a value the caller will dereference.
- Inspect `try/except/finally` chains for paths that return from `finally` and override `try`/`except` returns.
- For async functions, confirm the annotation refers to the awaited type, not the coroutine wrapper.
- The full failure contract is the return value AND every exception raised — list each `raise` in the body and the docstring `Raises:`; a `-> bool` that can also raise is not fully described as "returns bool".

**A3. CLI/argument-parser declaration → downstream Namespace contract**
- For every `add_argument(...)` (or equivalent CLI declaration), verify the auto-derived or explicit `dest=` matches the attribute name accessed downstream on the parsed namespace.
- Verify `type=` (or schema coercion) matches every downstream consumer's expectation — e.g., a value handed to a function requiring `int` is declared `type=int`, not the default `str`.
- Switch flags (`action="store_true"` / `store_false`) produce booleans; non-switch arguments produce typed values; flag the mismatch where a switch is treated as a value or vice versa.
- Default values resolve correctly when the flag is omitted; flag any code path that assumes the user supplied the argument.
- Required-vs-optional declaration matches the downstream code's null-handling.

**A4. Stdlib/library callback contracts**
- Identify every callback handed to a library function (e.g., `os.walk(onerror=...)`, sort `key=`, `filter`, `map`, `re.sub(repl=callable)`, signal handlers, threading callbacks). Verify each callback's signature matches what the library calls it with — arity, positional-vs-keyword, return type the library consumes.
- For every stdlib function the artifact calls, verify argument types and exception contracts: which exceptions can each call raise, and is each caller prepared (or deliberately not prepared) for them.
- Verify kwargs to stdlib functions are spelled correctly for the targeted runtime version (deprecated/renamed kwargs, version-introduced kwargs).
- Catch-site precision — for any "catches X" claim confirm the exact catch site and scope (an `except` around only a rollback inside `finally` does not catch the same error from the `with` body).
- Flag callbacks whose return value the library consumes but the implementation returns `None` (or vice versa).
- Confirm callback exception behavior: which exceptions in the callback bubble out, which are swallowed by the library, which terminate iteration.

**A5. Subprocess / external-process invocation contract**
- For every `subprocess.run` / `subprocess.Popen` / equivalent call, verify the `args` shape: list-of-strings vs single string vs `shell=True` semantics.
- Verify kwargs are valid for the targeted runtime version (`capture_output`, `text`, `encoding`, `check`, `timeout`); flag combinations that conflict (`stdout=PIPE` + `capture_output=True`).
- Exception contract under `check=True` (raises `CalledProcessError` on non-zero exit) — verify callers either propagate or handle, with no silent swallow that masks failure.
- Verify quoting/escaping of arguments crossing the subprocess boundary, especially when interpolating untrusted strings.
- Verify the resolved executable path is real on the target platform, not assumed (`which` / `Get-Command` failure paths).

**A6. Shell/host-language cmdlet or function parameter sets and binding**
- For every shell or host-language function/cmdlet declaration with parameter sets (PowerShell `param(...)` with `ParameterSetName=`, Bash `getopts`, etc.), verify the declaration matches every invocation pattern. Confirm a default parameter set is declared if no-arg invocation is reachable.
- For every cmdlet/builtin invocation, verify the parameter combination is valid per the cmdlet's documented parameter sets — flag combinations that mix flags from disjoint parameter sets.
- Flag missing `-ErrorAction` (or equivalent) declarations on calls whose null-checks downstream assume swallowed errors.
- Verify each cmdlet/builtin argument's type coercion at the boundary matches what the cmdlet expects.
- Confirm pipeline-bound parameters (`ValueFromPipeline`, `ValueFromPipelineByPropertyName`) match what upstream emits.

**A7. Cross-language / cross-process argv and serialization boundary**
- Trace every value crossing a language or process boundary (shell argv → Python `sys.argv`, environment variables, JSON/IPC payloads, file-format round-trips). Verify the producer's serialization matches the consumer's parser.
- Flag trailing-backslash, embedded-space, embedded-quote, and Unicode hazards on Windows argv composition (Microsoft C-runtime argv parser rules) and POSIX shell word-splitting.
- Verify argument-order conventions match across the boundary — e.g., flag order, positional placement, separator handling (`--`).
- Cross-language default-value drift: a default declared on one side that differs from the default on the other side; verify either both are sourced from a single config or both are intentionally mirrored.
- Cross-language type drift: integer width, signed/unsigned, floating-point precision, string encoding (UTF-8 vs UTF-16), null/empty-string semantics.

**A8. Documented API/tool calls vs official API documentation**
- For every API call, MCP tool invocation, CLI command, or SDK method call documented in the source material, identify the provider.
- Look up the official documentation for that API (Context7 MCP for libraries/SDKs, API reference docs for REST endpoints, tool definitions in session for MCP calls, `--help` for CLI tools).
- Verify the documented parameter names, types, and required-ness match the official API signature.
- For read-only API calls, execute one safe invocation to confirm the documented shape succeeds in practice.
- For write calls, verify the signature against the provider's own published API contract — their REST reference docs, OpenAPI spec, SDK source code, or `--help` output. When a read endpoint exposes the same state, call it to confirm the write contract.
- Flag every call where documented parameters, types, or behavior diverge from the official API contract.

**A9. Intra-module sibling-helper API parity**
- Did the diff add a new check / validator / parser / handler alongside existing sibling helpers in the same module? Verify the new one matches the sibling cohort's signature — every parameter the peer checks accept (e.g., `all_changed_lines` for diff-line filtering).
- Verify the new helper's scoping semantics match the cohort: whole-file vs fragment content surface, diff-line filtering, and `defer_scope_to_caller` handling.
- Verify the new helper's result-shape contract matches: where the result cap is applied (pre-scope vs post-scope), whether `defer_scope_to_caller=True` is honored, and the return type.
- When the new helper omits a sibling-accepted parameter, runs on a different content surface than its siblings, or applies the result cap at a different point in the pipeline, name it as an A9 finding. Cite the new helper and the sibling it diverges from as the pair.
- For a pure-code artifact with no new sibling helper, A9 is one line of proof-of-absence (the diff adds no helper alongside an existing cohort).

### Documentation as contract (when the artifact asserts facts about the code)

When the artifact is documentation that asserts facts about the codebase (symbol names, signatures, return types, exceptions, file paths), run all seven documentation-as-contract checks below; each yields a confirmation or a finding. For a pure-code artifact, this section is one line of proof-of-absence (the artifact asserts no code facts).

- Full failure contract — the failure signals of a function are its return value AND every exception it raises; trace the body and the docstring `Raises:` for every `raise`. _Example:_ a docs PR says a UI helper "returns `bool`", but it also raises a custom not-found error, so "returns bool" understates the contract.
- Call shape — required versus optional parameters (a keyword-only parameter with NO default is required; omitting it raises `TypeError`), sync versus async, and the exact access path (free function versus instance method reached through an object attribute versus import path). _Example:_ a doc presents a helper as a free function, but it is an `async` instance method reached through an object attribute, so the doc's call example would raise `TypeError`.
- Reuse-first — before a doc endorses a hand-written snippet, search for a dedicated helper that already does it. _Example:_ a doc endorses hand-composing `normalize(name).lower()` inline while a dedicated `normalize_for_matching()` helper already does exactly that.
- Path resolution — every file or directory path a doc cites resolves from the repository root. _Example:_ a doc cites a bare `snapshots/` directory as if it sat at the repo root, but the tree lives under `subsystem/snapshots/`.
- Cross-entry consistency — scan parallel rows, sections, and table entries for claims that contradict each other. _Example:_ two adjacent table rows map the same subsystem to two different exception base classes.
- Catch-site precision — when a doc claims code "catches X", confirm the exact site and scope of the catch. _Example:_ a doc says a context manager catches a driver error, but the `except` wraps only the rollback inside `finally`, so an error raised in the `with` body propagates uncaught.
- Citation freshness — re-derive every `file:line` claim against the current code; never trust a prior "verified" assertion or wording borrowed from a comment. _Example:_ an attribute name carried over from a review comment names a member the class does not define; the current code exposes it under a different name.

## Cross-bucket questions to answer at the end

Q1: Are there any contracts that span two sub-buckets that single-bucket analysis would miss?
Q2: What is the worst contract-drift hazard introduced by this artifact? Cite file:line.
Q3: Where would a future refactor most likely break a cross-bucket or cross-language contract? Name the line(s) most fragile.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket A1–A9, produce Shape A or Shape B (with ≥3 adversarial probes). Documentation-as-contract: when the artifact asserts code facts, walk all seven checks and report each as a finding or a confirmation; for a pure-code artifact, one line of proof-of-absence. Cross-bucket Q1–Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P1 bugs across these 9 sub-buckets — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

---

# Worked example: jl-cmd/claude-code-config PR #394 (May 2026 audit experiment)

Audit jl-cmd/claude-code-config PR #394 for **Category A only** (API contract verification). Skip B–N. Sub-bucket forced-exhaustion mode: Category A is decomposed into 8 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

PR: feat(scripts): add sweep-empty-dirs utility and scheduled-task installer
Head SHA: 62c9c169ee7a44824e5da25c4cf8b74fdca08a53
ID prefix: `find`.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**A1. Python function signatures vs internal call sites**
- Every defined function's parameter list (count, names, defaults, kw-only).
- Every internal call within `sweep_empty_dirs.py` matches its target's signature.

**A2. Python return-type annotation vs every code path**
- Each function's return annotation is satisfied by every path: explicit `return X`, fall-through, exception-handler exit.
- Pay specific attention to `main() -> None` (with the `KeyboardInterrupt` path) and `sweep(...) -> list[str]` (single return path).

**A3. argparse parser → Namespace contract**
- Every `add_argument(...)` declared in `_build_parser()` produces the exact dest name accessed in `main()`.
- `type=` matches downstream usage (e.g., `time.sleep` accepts the type).
- Switch flag (`--once`) produces a bool; non-switches produce typed values.
- Default values resolve correctly when the flag is omitted.

**A4. stdlib callback contracts (os.walk onerror, getctime, rmdir)**
- `os.walk(root, onerror=_log_walk_error, topdown=False)` — `_log_walk_error` matches the exact signature stdlib calls (positional `OSError`).
- `os.path.getctime`, `os.rmdir` argument and exception contracts.
- `time.sleep` argument contract.
- `os.walk`'s own kwargs (`onerror`, `topdown`) are spelled correctly for the Python version targeted.

**A5. subprocess invocation contract (test file)**
- `subprocess.run([list], check=True, capture_output=True)` — kwargs valid for the targeted Python.
- The list shape — `["powershell", "-Command", string]` — matches `subprocess.run`'s expected `args` parameter.
- Exception contract: `check=True` raises CalledProcessError on non-zero exit; tests do not catch it.

**A6. PowerShell cmdlet parameter sets and binding**
- `param(...)` declarations with `ParameterSetName=` — does the script declare `[CmdletBinding(DefaultParameterSetName=...)]`? If not, what happens with no-arg invocation?
- `New-ScheduledTaskTrigger -Daily -At ... -RepetitionInterval ...` — is `-RepetitionInterval` valid for the `-Daily` parameter set per Microsoft's docs? Verify against https://learn.microsoft.com/powershell/module/scheduledtasks/new-scheduledtasktrigger.
- `Get-Command python` (line 80) — missing `-ErrorAction SilentlyContinue` in the fallback breaks the subsequent null-check contract.
- `Register-ScheduledTask`, `New-ScheduledTaskAction`, `New-ScheduledTaskSettingsSet`, `Get-ScheduledTask`, `Unregister-ScheduledTask` — verify each call's parameter shape against its cmdlet signature.

**A7. Cross-language argv boundary (PowerShell argv construction → Python sys.argv → argparse)**
- The `New-ScheduledTaskAction -Argument` string `"$ScriptPath --once --age $AgeSeconds ""$Target"""` — when expanded and passed to Windows process creation, does the resulting argv match what argparse expects?
- Trailing-backslash hazard: if `$Target` ends with `\`, what does the Microsoft C-runtime argv parser produce?
- The Python `argparse` flag order — does the launcher's argv arrangement (`<flags> <positional>`) match what argparse accepts?
- Cross-language default-value drift: PowerShell `[int]$AgeSeconds = 120` vs Python `DEFAULT_AGE_SECONDS: int = 120` — both hardcoded, no shared source of truth.
- Cross-language type drift: PowerShell `[int]` vs Python `type=int` — both convert to integer, but PowerShell's `[int]` is 32-bit signed; argparse's `int(...)` is Python int (arbitrary precision). Match for normal values.

## Cross-bucket questions to answer at the end

Q1: Are there any contracts that span two sub-buckets that single-bucket analysis would miss?
Q2: What's the worst contract-drift hazard introduced by this PR? Cite file:line.
Q3: Where would a future refactor most likely break a cross-language contract? Name the line(s) most fragile.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket A1-A7, produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P1 bugs across these 8 sub-buckets — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

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
