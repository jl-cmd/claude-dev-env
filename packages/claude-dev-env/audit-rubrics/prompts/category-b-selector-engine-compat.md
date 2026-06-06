Audit [REPO/ARTIFACT] [TARGET_ID] for **Category B only** (selector / query / engine compatibility). Skip A, C–P. Sub-bucket forced-exhaustion mode: Category B is decomposed into 7 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA: repo, ref/SHA, PR or commit range, file count, language matrix, declared engine/runtime/browser/DB targets — fill before running.]
ID prefix: `find`.

## Source material ([N] files/sections, all lines in scope)

[INLINE THE FULL ARTIFACT HERE — see ../source-material-section-types.md for chunking guidance.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**B1. CSS / DOM selector vs target browser engine**
- Every CSS selector in the diff — verify pseudo-class support (`:has()`, `:is()`, `:where()`, `:focus-visible`, `:focus-within`) against every browser engine in the declared support matrix; flag any selector that requires an engine version newer than the declared minimum.
- Every attribute selector, `::part()`, `::slotted()`, and shadow-DOM piercing pattern — verify the target engine actually exposes the matching DOM (e.g. shadow boundaries, scoped styles).
- Every selector fed to `document.querySelector` / `querySelectorAll` / jQuery `$()` / Selenium `By.css_selector` / Playwright `page.locator` — verify the **runtime** selector engine matches the **target browser** engine; a Node-side jsdom selector parse can succeed where the real browser fails (or vice versa).
- Every CSS feature query (`@supports`), media query level, and container query — verify availability across the declared engine matrix and that fallback paths exist for engines that do not parse the syntax.
- Every test-runner DOM assertion (snapshot, `outerHTML`/`innerHTML` equality, computed-style read) — verify the runner uses the same engine as the production target, or document the divergence.
- Cross-engine quirks: WebKit-only `-webkit-` prefixes, Gecko-only `-moz-`, IE/Edge legacy filters; flag any production reliance on a single-engine prefix without a standard fallback.

**B2. SQL syntax vs database version**
- Every SQL string literal, ORM-generated query, and migration — verify CTE (`WITH … AS`) support against the declared minimum DB version (MySQL ≥ 8.0, MariaDB ≥ 10.2, SQLite ≥ 3.8.3, etc.).
- Every window function (`OVER`, `PARTITION BY`, `ROWS BETWEEN`), `LATERAL` join, `FILTER` clause, and `MERGE`/`UPSERT` syntax — verify the target dialect and version supports it.
- Every JSON operator (`->`, `->>`, `@>`, `?`, `jsonb_path_query`, `JSON_VALUE`, `JSON_EXTRACT`) — verify dialect-specific syntax matches the declared engine.
- Every full-text search clause (`MATCH … AGAINST`, `to_tsvector`, `CONTAINS`, `FREETEXT`) and every spatial / geometry function — verify engine and version availability.
- Every dialect-specific function (`GROUP_CONCAT` vs `STRING_AGG` vs `LISTAGG`, `IFNULL` vs `NVL` vs `COALESCE`, `LIMIT n` vs `TOP n` vs `FETCH FIRST n ROWS`).
- Every migration's reversibility and online-DDL safety on the target version (ALGORITHM/LOCK hints, transactional DDL availability).

**B3. Regex syntax vs engine flavor**
- Every regex in the diff — verify lookbehind support (POSIX ERE has none; Python `re` requires fixed-width lookbehind; Python `regex`, PCRE, Perl, .NET, JS V8 ≥ 2018 allow variable-width).
- Every named group — verify `(?P<name>…)` (Python) vs `(?<name>…)` (PCRE/JS/.NET) vs `(?'name'…)` (.NET only) matches the engine in use.
- Every backreference, recursion (`(?R)`, `(?0)`), conditional (`(?(1)yes|no)`), atomic group (`(?>…)`), possessive quantifier (`*+`, `++`) — verify engine support.
- Every Unicode character class (`\p{L}`, `\p{Script=Greek}`) and Unicode flag (`u`, `re.UNICODE`) — verify the engine has Unicode tables compiled in and the flag is honored.
- Every regex passed across boundaries (Python → JS via JSON, server → client) — verify the consumer engine accepts the same flavor; flag any flavor-translation gap.
- Every f-string- or template-built regex — verify interpolated values are escaped (`re.escape`, `RegExp.escape` proposal, manual literal-quote helpers) so user-supplied input cannot inject metacharacters.

**B4. Shell / CLI / cmdlet syntax vs runtime version**
- Every PowerShell cmdlet — verify availability across the declared edition matrix (Windows PowerShell 5.1 ↔ PowerShell 7+ ↔ PowerShell on Linux/macOS) and version-specific parameter sets.
- Every shebang (`#!/usr/bin/env pwsh`, `#!/bin/bash`, `#!/usr/bin/env python3`) vs the actual interpreter resolved at runtime — flag mismatches between declared and invoked interpreter (e.g. shebang says `pwsh` but Python `subprocess.run(["powershell", …])` resolves to PS 5.1 on Windows).
- Every parameter set in a `param(...)` block — verify `[CmdletBinding(DefaultParameterSetName=…)]` is set when ambiguity is possible; missing default = `Parameter set cannot be resolved` at runtime.
- Every cmdlet flag combination — verify both flags belong to the same parameter set per Microsoft docs (e.g. `-RepetitionInterval` is an `-Once` parameter, NOT `-Daily`).
- Every bash-ism — `[[ ... ]]` (bash 3+ only, not POSIX `sh`), arrays, process substitution `<(…)`, `${var,,}` lower-case expansion (bash 4+), associative arrays — verify against the declared minimum shell.
- Every CLI flag deprecation across versions (`gh` flag changes, `git` porcelain v2, `docker` deprecated commands) — verify the declared minimum tool version still accepts the syntax in use.
- Every `Get-Command`, `command -v`, `which` lookup — verify error-handling parity (`-ErrorAction SilentlyContinue` on the failing path, `|| true`, `2>/dev/null`) so a missing dependency degrades gracefully across versions.

**B5. JSON path / XPath / structural query vs library**
- Every JSONPath expression — verify the target library's flavor (`jq` vs Python `jsonpath-ng` vs `jsonpath-rw` vs JS `jsonpath-plus` vs Goessner reference). Filter syntax (`[?(@.foo)]`), recursive descent (`..`), and slicing differ.
- Every XPath expression — verify XPath 1.0 vs 2.0 vs 3.0 functions (`matches()`, `tokenize()`, `string-join()` are 2.0+); flag any 2.0+ function fed to a 1.0-only engine like `lxml.etree`'s default.
- Every JSON Pointer (`/foo/bar/0`), JSON Patch op, and JMESPath query — verify library version and edge cases (escaped `~` and `/`).
- Every YAML/TOML structural query (`yq`, `tomlq`) — verify version flavor (`yq` v3 Python ↔ v4 Go are incompatible).
- Every cross-library round-trip: `jq` filter handed to a Python jsonpath consumer, or XPath compiled in lxml then serialized for libxslt — verify each consumer accepts the source flavor.

**B6. Search query DSL vs engine**
- Every Lucene/Elasticsearch query string — verify field syntax (`field:value`), required/excluded operators (`+`, `-`), fuzzy (`term~2`), proximity (`"a b"~5`), and wildcard rules (`*`, `?`) match the engine version's parser.
- Every Elasticsearch query DSL object (`match`, `bool`, `should`, `must`, `filter`, `term`, `terms`) — verify removed/renamed clauses across major versions (e.g. `query_string` defaults, `term` vs `match` for `text` fields, mapping-type removal in ES 7+).
- Every Zoekt / Sourcegraph / OpenSearch / Solr query — verify dialect-specific operators and that the deployment has the relevant features enabled (e.g. ES `query_string` may be disabled for security).
- Every escaping rule for special characters in the DSL (`+ - && || ! ( ) { } [ ] ^ " ~ * ? : \ /`) — verify the producer escapes them before handing to the engine; flag any user-supplied input concatenated raw.
- Every analyzer assumption (whitespace, standard, keyword, ngram) — verify the index mapping matches what the query string assumes.

**B7. ORM vs raw SQL semantic differences**
- Every ORM filter expression — verify SQLAlchemy `.filter()` (Core/ORM expression) vs `.filter_by()` (kwargs only, equality only) usage; flag any `.filter_by()` passed boolean operators it does not support.
- Every Django Q expression, F expression, `Subquery`, `OuterRef`, `Exists` — verify the ORM version supports the construct (e.g. `FilteredRelation` is Django 2.0+, `Window` is 2.0+).
- Every lazy vs eager loading decision (`select_related`, `prefetch_related`, SQLAlchemy `joinedload`/`selectinload`/`subqueryload`) — verify N+1 risk and that the chosen strategy matches the dialect's join semantics.
- Every transaction context manager (`with session.begin():`, `@transaction.atomic`, `db.session.commit()`) — verify isolation level, autocommit behavior, and savepoint support match the declared DB version.
- Every raw SQL escape hatch (`session.execute(text(...))`, `cursor.execute()`, `RawSQL`) — verify it bypasses the ORM's dialect-rewriting and ensure the literal SQL still satisfies B2 (engine version) constraints.
- Every model field type (`JSONField`, `ArrayField`, `HStoreField`) — verify the backing DB version supports the underlying column type and operators.

## Cross-bucket questions to answer at the end

Q1: Are there any compatibility constraints that span two sub-buckets that single-bucket analysis would miss? (E.g. a query string that crosses B3 regex flavor + B6 search DSL escaping; a script that crosses B4 cmdlet syntax + B3 format-string interpolation; an ORM expression that crosses B7 lazy-load semantics + B2 dialect SQL.)

Q2: What's the worst engine-incompatibility hazard introduced by this artifact? Cite file:line. Rank by (a) likelihood the deployment hits the incompatible engine, (b) severity when it does, (c) detectability before production.

Q3: Where would a future engine/library upgrade most likely break a selector, query, cmdlet, or interpolated pattern in this artifact? Name the most fragile lines and the upgrade path that would break them (browser version bump, DB major upgrade, PowerShell edition change, ORM major version, search-engine major version).

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket B1–B7, produce Shape A (≥1 finding) or Shape B (proof-of-absence with ≥3 distinct adversarial probes). Cross-bucket Q1–Q3 answers after the per-sub-bucket walk. Adversarial second pass (P1 quota): "assume your first pass missed at least 3 P1 incompatibility bugs across these 7 sub-buckets — find them." Open Questions section for ambiguities, undeclared engine targets, or cases where the declared support matrix is incomplete. Read-only. No edits, no commits.

---

# Worked example: jl-cmd/claude-code-config PR #394

Audit jl-cmd/claude-code-config PR #394 for **Category B only** (selector / query / engine compatibility). Skip A, C–N. Sub-bucket forced-exhaustion mode: Category B is decomposed into 7 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

PR: feat(scripts): add sweep-empty-dirs utility and scheduled-task installer
Head SHA: 62c9c169ee7a44824e5da25c4cf8b74fdca08a53
ID prefix: `find`.

````
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
````

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**B1. CSS / DOM selector vs target browser engine**
- The four PR #394 files contain no HTML, no CSS, no JavaScript, no DOM-rendering or shadow-DOM code, no browser-test runner.
- Shape B proof-of-absence expected. Adversarial probes must each verify a distinct DOM/CSS dimension:
  - Probe B1.a: confirm zero CSS selectors anywhere in the four files — no `:has()`, `:is()`, `:where()`, no attribute selectors, no `::part()`, no `::slotted()`. Walk every string literal in `sweep_empty_dirs.py`, `sweep_config.py`, `test_sweep_empty_dirs.py`, `Install-SweepEmptyDirs.ps1`.
  - Probe B1.b: confirm zero references to `document.querySelector` / jQuery `$()` / `getElementById` / shadow-root `attachShadow` / Selenium `By.css_selector` / Playwright `page.locator`. The Python test harness uses `subprocess.run`, not a browser driver.
  - Probe B1.c: confirm zero rendered-output assertions — no HTML snapshot fixtures, no `outerHTML`/`innerHTML` comparisons, no DOM-tree equality checks. The test file at `tests/test_sweep_empty_dirs.py` lines 35-76 only asserts on filesystem state (`os.path.isdir`, list membership of `removed`).

**B2. SQL syntax vs database version**
- The four PR #394 files contain no database access, no ORM, no migrations, no SQL string literals.
- Shape B proof-of-absence expected. Adversarial probes must each verify a distinct DB dimension:
  - Probe B2.a: confirm `sweep_empty_dirs.py` imports only `argparse`, `os`, `sys`, `time` plus two names from `config.sweep_config` (lines 4-10). No `sqlite3`, no `psycopg2`, no SQLAlchemy, no Django ORM.
  - Probe B2.b: confirm zero SQL keyword tokens (`SELECT`, `INSERT`, `UPDATE`, `DELETE`, `WITH`, `JOIN`, `MERGE`, `WINDOW`) appear in any string literal across all four files. No CTEs, no window functions, no JSON operators (`->`, `->>`, `@>`).
  - Probe B2.c: confirm no migration directory or schema file is added by the PR — the four added files are `sweep_empty_dirs.py`, `config/sweep_config.py`, `tests/test_sweep_empty_dirs.py`, `Install-SweepEmptyDirs.ps1`. None is a `*.sql`, `migrations/*.py`, `alembic/`, or `prisma/schema.prisma`.

**B3. Regex syntax / format-string flavor vs engine — Python f-string → PowerShell**
- The test helper `_set_creation_time_windows` at `tests/test_sweep_empty_dirs.py` lines 20-27 (def at line 20, body lines 21-27) builds a PowerShell command via Python f-string interpolation. The critical line is `tests/test_sweep_empty_dirs.py:25` — `f"(Get-Item '{path}').CreationTimeUtc = [DateTime]'{date_str}'"` — and the surrounding `subprocess.run(["powershell", "-Command", ...], check=True, capture_output=True)` call at lines 23-27. The interpolated `path` and `date_str` values pass through Python f-string substitution → argv list → Windows `CreateProcess` argv → `powershell.exe` `-Command` parser → PowerShell single-quoted string-literal parser → `[DateTime]` cast.
- Adversarial probe B3.a (single-quote injection): PowerShell single-quoted string literals (`'…'`) do not honor backslash escapes, but `''` is the embedded-single-quote escape. If `path` contains `'` (e.g. `won't`), the `f"...'{path}'..."` substitution at `tests/test_sweep_empty_dirs.py:25` produces a PowerShell command with an unbalanced quote — `(Get-Item 'won't').CreationTimeUtc = ...` — which terminates the literal early and leaves `t')` as a parse error. The Python helper does not call any escape function. Verify whether this breaks `test_deletes_empty_dir_older_than_threshold` (line 30) when run from a tmp path containing an apostrophe (Windows usernames with apostrophes, e.g. `O'Brien`, are legal).
- Adversarial probe B3.b (`$(...)` subexpression hazard): PowerShell single-quoted strings DO NOT expand `$(...)`, `$variable`, or backtick escapes — they are inert. But the OUTER PowerShell `-Command` payload is a double-quoted-equivalent context where the entire Python f-string sits as a single argv entry. Verify that the `[DateTime]` literal subsequently invoked at `tests/test_sweep_empty_dirs.py:25` does not allow an embedded `$(...)` to escape — i.e. confirm that even if `date_str` were attacker-influenced, the `[DateTime]'…'` cast parses within single quotes only and never re-evaluates the contents through PowerShell's expression engine.
- Adversarial probe B3.c (backtick escape): backticks (`` ` ``) are PowerShell's escape character inside double-quoted strings but inert inside single-quoted strings. The f-string at `tests/test_sweep_empty_dirs.py:25` wraps `{path}` in single quotes, so backticks in `path` should pass through literally — verify against PowerShell 5.1 and PowerShell 7+, both invoked via `["powershell", ...]` (which on Windows resolves to PS 5.1 by default — see B4).
- Adversarial probe B3.d (`[DateTime]` parse format): `dt.strftime("%Y-%m-%d %H:%M:%S")` at `tests/test_sweep_empty_dirs.py:22` produces e.g. `2026-05-08 14:23:45`. PowerShell's `[DateTime]'<string>'` cast parses via `DateTime.Parse`, which is **culture-sensitive** by default. On a Windows machine where `Get-Culture` is e.g. `de-DE` (`yyyy-MM-dd` is unambiguous, but the time separator `:` vs. month-day reordering matters for some locales), `DateTime.Parse` may misinterpret the string or throw `FormatException`. The Python helper does not pin a culture (no `[CultureInfo]::InvariantCulture` use). Verify whether the same parse succeeds on PS 5.1 and PS 7+ across at least `en-US`, `de-DE`, `ja-JP`.

**B4. Shell / CLI / cmdlet syntax vs runtime version — ScheduledTasks module + powershell.exe vs pwsh**
- `Install-SweepEmptyDirs.ps1` declares the interpreter via shebang `#!/usr/bin/env pwsh` at line 1 (PowerShell 7+), but invokes the `ScheduledTasks` module: `Get-ScheduledTask` at `Install-SweepEmptyDirs.ps1:22`, `Unregister-ScheduledTask` at line 41, `New-ScheduledTaskAction` at line 70, `New-ScheduledTaskTrigger` at line 71, `New-ScheduledTaskSettingsSet` at line 72, `Register-ScheduledTask` at line 74. The `ScheduledTasks` module is a Windows-native CDXML module (introduced in Windows 8 / Server 2012, PS 3.0); on PS 7+ it is reachable on Windows via the WindowsPowerShell Compatibility shim auto-load, but absent entirely on Linux/macOS PS 7+.
- Probe B4.a (shebang vs platform): `#!/usr/bin/env pwsh` at `Install-SweepEmptyDirs.ps1:1` says "run me on PowerShell 7+", but the cmdlets at lines 22, 41, 70-74 only resolve on Windows. Verify whether the script declares a `#Requires -RunAsAdministrator` / `#Requires -Version` / `#Requires -PSEdition Desktop` / OS guard. It does not. Cross-check Microsoft docs: https://learn.microsoft.com/powershell/scripting/lang-spec/chapter-13#1310-the-requires-statement.
- Probe B4.b (`-Daily` parameter set + `-RepetitionInterval`): `New-ScheduledTaskTrigger -Daily -At "00:00" -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)` at `Install-SweepEmptyDirs.ps1:71`. Per https://learn.microsoft.com/powershell/module/scheduledtasks/new-scheduledtasktrigger, `-RepetitionInterval` belongs to the `-Once` parameter set, NOT the `-Daily` parameter set. Confirm whether the cmdlet errors with `Parameter set cannot be resolved using the specified named parameters` on both PS 5.1 (ScheduledTasks v1.0.0.0 shipped with Windows 8.1 / Server 2012 R2) and PS 7+ (same module via Windows Compatibility).
- Probe B4.c (`New-ScheduledTaskSettingsSet` switches): `-AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable` at `Install-SweepEmptyDirs.ps1:72`. Verify all three switches exist in the ScheduledTasks v1.0.0.0 module baseline (Windows 8.1 / Server 2012 R2). Microsoft docs: https://learn.microsoft.com/powershell/module/scheduledtasks/new-scheduledtasksettingsset.
- Probe B4.d (`powershell` vs `pwsh` argv resolution): the Python test helper at `tests/test_sweep_empty_dirs.py:24` hardcodes `["powershell", "-Command", …]`. On Windows, `powershell` resolves to **Windows PowerShell 5.1** (`%WinDir%\System32\WindowsPowerShell\v1.0\powershell.exe`), NOT to PowerShell 7+ (`pwsh.exe`). The shebang on the installer says PS 7+, but the test helper runs PS 5.1. Two different runtimes for one PR. Verify the `[DateTime]'<string>'` cast (B3.d) and `Get-Item` semantics behave identically across both. Cross-check https://learn.microsoft.com/powershell/scripting/install/migrating-from-windows-powershell-51-to-powershell-7.
- Probe B4.e (parameter-set ambiguity with no default): the `param(...)` block at `Install-SweepEmptyDirs.ps1:2-17` declares three parameter sets (`install`, `remove`, `status`) but the script lacks `[CmdletBinding(DefaultParameterSetName=…)]`. With no default set, a no-argument invocation triggers `Parameter set cannot be resolved` on PS 5.1 and PS 7+. The exit code and error stream shape differ subtly across the two versions — verify whether the user's downstream automation can disambiguate.
- Probe B4.f (`Get-Command` -ErrorAction asymmetry): `$_py = Get-Command py -ErrorAction SilentlyContinue` at `Install-SweepEmptyDirs.ps1:64` swallows the not-found error, but `(Get-Command python).Source` at line 65 has no `-ErrorAction SilentlyContinue`. If `python` is not on PATH, the line throws a terminating error before the `if (-not $PythonPath)` check at line 66 can fire. Verify the version-specific shape of the resulting error stream — PS 5.1 emits a `CommandNotFoundException`, PS 7+ emits the same with a slightly different formatted prefix; downstream automation that grep-matches the error text breaks across versions.

**B5. JSON path / XPath / structural query vs library**
- The four PR #394 files contain no JSON path, no XPath, no JsonPointer, no structural query expressions.
- Shape B proof-of-absence expected. Adversarial probes must each verify a distinct structural-query dimension:
  - Probe B5.a: confirm no `jq` invocations anywhere — neither `subprocess.run(["jq", ...])` in Python nor `jq` cmdlets nor inline `--jq` flags in PowerShell. The Python `subprocess.run` at `tests/test_sweep_empty_dirs.py:23-27` invokes `powershell`, not `jq`.
  - Probe B5.b: confirm no `import jsonpath_ng`, `import lxml`, `import xml.etree`, no `from xml import dom`, no `xpath.compile(...)` calls. `sweep_empty_dirs.py` imports only `argparse`, `os`, `sys`, `time` (lines 4-7) plus the config module.
  - Probe B5.c: confirm no JSON-pointer (`/foo/bar`) string literals, no JsonPath-style `$.foo[?(@.bar)]` patterns, no XPath `/html/body//div[@class='x']` patterns in any string in the four files. Walk every f-string and string literal.

**B6. Search query DSL vs engine**
- The four PR #394 files contain no search-engine queries, no Lucene/Elasticsearch/Zoekt/OpenSearch DSL.
- Shape B proof-of-absence expected. Adversarial probes must each verify a distinct search-DSL dimension:
  - Probe B6.a: confirm no HTTP calls to `/_search`, `/_msearch`, `/_count`, `/_analyze` endpoints — `sweep_empty_dirs.py` does not import `requests`, `urllib`, `httpx`, `aiohttp`. Pure stdlib + local config.
  - Probe B6.b: confirm no Lucene-syntax fragments — no `field:value`, no `+required -excluded`, no fuzzy `term~2`, no proximity `"a b"~5`. The only colon-bearing literals in the diff are PowerShell hash separators (`$($action.Execute) $($action.Arguments)` at `Install-SweepEmptyDirs.ps1:31`) and the time literal `"00:00"` at line 71 — neither is a search-DSL fragment.
  - Probe B6.c: confirm no `match`/`bool`/`should`/`must`/`filter` clause objects appearing as Python dict literals or JSON. No Elasticsearch DSL anywhere.

**B7. ORM vs raw SQL semantic differences**
- The four PR #394 files contain no ORM usage, no raw SQL, no transaction context, no DB session.
- Shape B proof-of-absence expected. Adversarial probes must each verify a distinct ORM dimension:
  - Probe B7.a: confirm no SQLAlchemy / Django ORM / Peewee / Tortoise / Pony imports anywhere — `sweep_empty_dirs.py` lines 4-10 are limited to stdlib `argparse, os, sys, time` plus the local `config.sweep_config` module.
  - Probe B7.b: confirm no `.filter()`, `.filter_by()`, `Q()`, `F()`, `Subquery(...)`, `select()`, `insert()` ORM-style calls in any file. The closest expression-tree call is `os.walk(root, onerror=_log_walk_error, topdown=False)` at `sweep_empty_dirs.py:23-25` — that is a stdlib filesystem walk, not an ORM query.
  - Probe B7.c: confirm no transaction context manager (`with session.begin():`, `@transaction.atomic`, `db.session.commit()`) and no lazy-vs-eager-load distinction anywhere. The only context managers in the diff are `tempfile.TemporaryDirectory()` calls in test bodies at `tests/test_sweep_empty_dirs.py:31, 41, 50, 63, 69`.

## Cross-bucket questions to answer at the end

Q1: Are there any compatibility constraints that span two sub-buckets that single-bucket analysis would miss? Specifically, does the f-string-built PowerShell command at `tests/test_sweep_empty_dirs.py:25` cross B3 (Python f-string interpolation safety + PowerShell `[DateTime]` parse-format flavor) and B4 (PS 5.1 vs PS 7+ runtime, hard-coded `powershell` argv at line 24) such that the same line is exposed to both axes? Does the trigger-cmdlet call at `Install-SweepEmptyDirs.ps1:71` cross B4 (parameter-set validity for `-Daily` + `-RepetitionInterval`) and an A-category contract (already audited separately) such that a Category B finding would silently subsume a Category A one?

Q2: What's the worst engine-incompatibility hazard introduced by this PR? Cite file:line. Candidates: (a) the `-Daily -RepetitionInterval` parameter-set mismatch at `Install-SweepEmptyDirs.ps1:71` per Microsoft docs; (b) the `[DateTime]'<string>'` culture-sensitive parse at `tests/test_sweep_empty_dirs.py:25`; (c) the `powershell` vs `pwsh` runtime split between `tests/test_sweep_empty_dirs.py:24` and `Install-SweepEmptyDirs.ps1:1`; (d) the bare `(Get-Command python).Source` at `Install-SweepEmptyDirs.ps1:65` lacking `-ErrorAction SilentlyContinue`.

Q3: Where would a future engine/library upgrade most likely break a cmdlet, command line, or interpolated pattern in this diff? Name the line(s) most fragile. Candidates to evaluate: (a) the `ScheduledTasks` module being relocated or deprecated in a future Windows / PS 7+ release (lines 22, 41, 70-74 of `Install-SweepEmptyDirs.ps1`); (b) the f-string + `[DateTime]'…'` cast at `tests/test_sweep_empty_dirs.py:25` if a future PS release tightens culture parsing; (c) the hard-coded `["powershell", ...]` argv at `tests/test_sweep_empty_dirs.py:24` if Windows 12 ships `pwsh` as the default and removes Windows PowerShell 5.1.

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket B1–B7, produce Shape A or Shape B (with ≥3 probes). Cross-bucket Q1–Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 P1 incompatibility bugs across these 7 sub-buckets — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.
