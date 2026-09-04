# Static execution graph for hook audits

## Usage

The command prints one deterministic report to standard output. It does not create a cache, update a catalog, import a hook, or invoke a hook command.

Repository-only audit:

```powershell
python packages/claude-dev-env/scripts/audit_hooks.py
```

Repository plus the current Claude, Codex, and Git installation:

```powershell
python packages/claude-dev-env/scripts/audit_hooks.py --installed --format json
```

Continuous integration checks the canonical inventory and lifecycle catalog with the same command:

```powershell
python packages/claude-dev-env/scripts/audit_hooks.py --format text
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

Python callers get the same immutable report:

```python
from pathlib import Path

from hook_audit import AuditRequest, InstalledMode, audit_hooks

report = audit_hooks(
    AuditRequest(
        repository_root=Path.cwd(),
        installed=InstalledMode.AUTO,
    )
)

for finding in report.findings:
    print(finding.code, finding.message)
```

Exit code `0` means the audit found no error. Exit code `1` means the report contains an audit finding. Exit code `2` means the caller supplied an invalid option or repository root. Missing optional installed files become findings, so one bad input does not hide results from the other inputs.

The JSON shape keeps direct configuration and effective hook execution separate:

```json
{
  "schema_version": 1,
  "direct_registrations": [],
  "effective_hooks": [],
  "findings": [],
  "lifecycle": [],
  "summary": {
    "direct_count": 0,
    "effective_count": 0,
    "finding_count": 0
  }
}
```

Every path in the report uses a portable form such as `<REPO>/...`, `<HOME>/...`, or `script:blocking/code_rules_enforcer.py`. The report never contains a raw command or an absolute personal path.

## Problem

The package has 32 direct commands in `hooks/hooks.json`, but five of those commands are dispatchers. Their ordered rosters add 43 effective hook executions. Claude installs rewritten copies in `~/.claude/settings.json`. Codex keeps a focused projection in `~/.codex/hooks.json`. Git selects native shims through scoped `core.hooksPath` values. A flat JSON scan misses the dispatcher children and cannot distinguish a second snapshot from a second execution. Importing constants would also run module initialization, which is too close to executing the code under audit.

The tool needs one honest model of execution. It keeps the direct registration, expands routers into leaf hooks, and compares each runtime snapshot with its expected projection. A duplicate counts only where trigger domains overlap. Every leaf needs a lifecycle decision.

## Shape

### Core types

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Mapping, NewType, Protocol, Sequence

PortablePath = NewType("PortablePath", str)
TargetId = NewType("TargetId", str)
CommandFingerprint = NewType("CommandFingerprint", str)


class InstalledMode(StrEnum):
    NONE = "none"
    AUTO = "auto"


class RuntimeScope(StrEnum):
    CANONICAL = "canonical"
    CLAUDE = "claude"
    CODEX = "codex"
    GIT = "git"


class RegistrationRole(StrEnum):
    HOOK = "hook"
    DISPATCHER = "dispatcher"
    SHIM = "shim"


class LifecycleClass(StrEnum):
    DELETE = "delete"
    MOVE_TO_LINTER = "move_to_linter"
    MOVE_TO_CI = "move_to_ci"
    KEEP_NONBLOCKING_AUTOMATION = "keep_nonblocking_automation"
    KEEP_BOUNDARY_CHECK = "keep_boundary_check"


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class AnyMatcher:
    pass


@dataclass(frozen=True)
class FiniteMatcher:
    names: tuple[str, ...]


@dataclass(frozen=True)
class PatternMatcher:
    expression: str


MatcherDomain = AnyMatcher | FiniteMatcher | PatternMatcher


@dataclass(frozen=True)
class Trigger:
    event: str
    matcher: MatcherDomain


@dataclass(frozen=True)
class RouteStep:
    role: RegistrationRole
    target: TargetId
    ordinal: int


@dataclass(frozen=True)
class RegistrationPosition:
    group: int
    hook: int


@dataclass(frozen=True)
class DirectRegistration:
    scope: RuntimeScope
    trigger: Trigger
    target: TargetId
    role: RegistrationRole
    timeout_seconds: int | None
    command_fingerprint: CommandFingerprint
    source: PortablePath
    position: RegistrationPosition


@dataclass(frozen=True)
class EffectiveHook:
    scope: RuntimeScope
    trigger: Trigger
    target: TargetId
    argument_fingerprint: CommandFingerprint
    timeout_seconds: int | None
    route: tuple[RouteStep, ...]


@dataclass(frozen=True)
class LifecycleEntry:
    target: TargetId
    lifecycle: LifecycleClass
    reason: str
    replacement: str | None


@dataclass(frozen=True)
class Finding:
    severity: Severity
    code: str
    message: str
    scope: RuntimeScope
    target: TargetId | None


@dataclass(frozen=True)
class HookSnapshot:
    scope: RuntimeScope
    direct_registrations: tuple[DirectRegistration, ...]
    effective_hooks: tuple[EffectiveHook, ...]


@dataclass(frozen=True)
class AuditRequest:
    repository_root: Path
    installed: InstalledMode = InstalledMode.NONE
    home_directory: Path | None = None
    git_work_tree: Path | None = None


@dataclass(frozen=True)
class AuditReport:
    schema_version: int
    direct_registrations: tuple[DirectRegistration, ...]
    effective_hooks: tuple[EffectiveHook, ...]
    lifecycle_entries: tuple[LifecycleEntry, ...]
    findings: tuple[Finding, ...]

    def to_json(self) -> str:
        raise NotImplementedError

    def to_text(self) -> str:
        raise NotImplementedError
```

`TargetId` is the identity used by duplicate checks, drift checks, and lifecycle lookup. Known package copies collapse to the same value. For example, the source path, Claude-installed path, and Codex-installed path for the code rules hook all become `script:blocking/code_rules_enforcer.py`. An inline `python -c` registration becomes the imported package script when static Python parsing proves the import. Unknown external commands become `opaque:<sha256>` after path redaction. The report includes the digest, not the command.

`HookSnapshot` prevents false duplicates across expected source and installed observations. Duplicate analysis runs inside one runtime scope. Drift analysis compares a runtime scope with its matching expected projection.

`RouteStep` preserves direct and expanded coverage without calling the dispatcher a lifecycle hook. A direct leaf has one route step. A dispatcher child has a dispatcher step followed by a hook step. A native Git hook has a shim step followed by its Python module step. Lifecycle coverage applies to the final `EffectiveHook.target` only.

### Public and internal signatures

```python
def audit_hooks(request: AuditRequest) -> AuditReport:
    raise NotImplementedError


def main(argv: Sequence[str] | None = None) -> int:
    raise NotImplementedError


@dataclass(frozen=True)
class KnownRoots:
    repository: Path
    package_hooks: Path
    home: Path | None
    claude_hooks: Path | None
    codex_hooks: Path | None


class ReadOnlyFiles(Protocol):
    def read_bytes(self, path: Path) -> bytes:
        raise NotImplementedError

    def list_names(self, path: Path) -> tuple[str, ...]:
        raise NotImplementedError


class GitConfigProbe(Protocol):
    def all_hook_paths(self, work_tree: Path) -> tuple[tuple[str, str, str], ...]:
        raise NotImplementedError

    def effective_hook_path(self, work_tree: Path) -> Path | None:
        raise NotImplementedError


def normalize_path(raw_path: Path, roots: KnownRoots) -> PortablePath:
    raise NotImplementedError


def identify_command_target(
    command: str,
    roots: KnownRoots,
    files: ReadOnlyFiles,
) -> tuple[TargetId, CommandFingerprint, CommandFingerprint]:
    raise NotImplementedError


def read_hook_json_snapshot(
    scope: RuntimeScope,
    config_path: Path,
    roots: KnownRoots,
    files: ReadOnlyFiles,
) -> HookSnapshot:
    raise NotImplementedError


@dataclass(frozen=True)
class DispatcherSpec:
    dispatcher_target: TargetId
    constants_relative_path: str
    roster_symbol: str
    entry_shape: str


DISPATCHERS: tuple[DispatcherSpec, ...]


def expand_dispatchers(
    snapshot: HookSnapshot,
    hooks_root: Path,
    specs: tuple[DispatcherSpec, ...],
    files: ReadOnlyFiles,
) -> HookSnapshot:
    raise NotImplementedError


def read_codex_projection(
    repository_root: Path,
    canonical: HookSnapshot,
    files: ReadOnlyFiles,
) -> HookSnapshot:
    raise NotImplementedError


def read_git_projection(
    repository_root: Path,
    files: ReadOnlyFiles,
) -> HookSnapshot:
    raise NotImplementedError


def read_active_git_snapshot(
    work_tree: Path,
    roots: KnownRoots,
    files: ReadOnlyFiles,
    git_config: GitConfigProbe,
) -> HookSnapshot:
    raise NotImplementedError


def read_lifecycle_catalog(
    catalog_path: Path,
    files: ReadOnlyFiles,
) -> Mapping[TargetId, LifecycleEntry]:
    raise NotImplementedError


def find_duplicates(snapshot: HookSnapshot) -> tuple[Finding, ...]:
    raise NotImplementedError


def find_drift(
    expected: HookSnapshot,
    observed: HookSnapshot,
) -> tuple[Finding, ...]:
    raise NotImplementedError


def verify_lifecycle_coverage(
    all_effective_hooks: tuple[EffectiveHook, ...],
    lifecycle_by_target: Mapping[TargetId, LifecycleEntry],
) -> tuple[Finding, ...]:
    raise NotImplementedError
```

### Static readers

The dispatcher registry has exactly five entries:

1. `blocking/pre_tool_use_dispatcher.py` reads `ALL_HOSTED_HOOK_ENTRIES`.
2. `blocking/bash_pre_tool_use_dispatcher.py` reads `ALL_BASH_HOSTED_HOOK_ENTRIES`.
3. `blocking/stop_dispatcher.py` reads `ALL_STOP_HOSTED_HOOK_PATHS`.
4. `validation/post_tool_use_dispatcher.py` reads `ALL_POST_HOSTED_HOOK_ENTRIES`.
5. `blocking/bash_post_call_dispatcher.py` reads `ALL_BASH_POST_TOOL_USE_HOSTED_HOOK_ENTRIES`.

`expand_dispatchers` parses each constants file with `ast.parse`. Its evaluator accepts string literals, tuple and set literals, `frozenset` calls, named literal aliases, and the three known dataclass constructor shapes. Every other node produces `UNSUPPORTED_ROSTER_SYNTAX`. The reader never imports a constants module. It confirms that every roster target stays under the selected hooks root before reading it.

The command reader uses lexical tokenization only. It recognizes a direct Python script, the package root placeholders, and inline Python imports through `ast.parse` of the `-c` payload. It never passes command text to a shell. An unknown command remains visible as an opaque fingerprint and receives `OPAQUE_COMMAND`.

The Codex expected projection comes from static reads of `codex_compat_materializer.py`. The reader extracts the literal event, matcher, target, and timeout constants. This keeps the materializer as the source of truth. Unsupported computed values produce a finding instead of a guessed projection.

The Git expected projection reads the literal `KNOWN_GIT_HOOK_NAMES` array from `git_hooks_installer.mjs` and maps each name to the source module with hyphens replaced by underscores. The active probe runs only these argument-list commands with `shell=False`:

```text
git config --show-origin --show-scope --get-all core.hooksPath
git config --path --get core.hooksPath
```

The probe lists only known Git hook names in the effective directory. It parses a generated Python shim with `ast.parse`. An unrelated native hook becomes `git-opaque:<hook-name>:<sha256>`. The tool hashes its bytes and does not print the bytes.

### Duplicate and drift rules

The analyzer expands a matcher such as `Write|Edit|MultiEdit|apply_patch` into a sorted finite set. Empty matchers become `AnyMatcher`. Other matcher strings remain patterns.

Two leaves are duplicate effective executions when all of these facts match inside one runtime scope:

- event
- target
- argument fingerprint
- one finite trigger name, or the same pattern text

A finite name can also prove overlap with a regex by `fullmatch`. Two different free-form patterns do not prove intersection. The analyzer emits `MATCHER_OVERLAP_UNKNOWN` when the same target and event use such patterns. It does not label an undecidable pair as a duplicate.

Drift uses two indexes. A direct-registration index catches router, timeout, matcher, and command-shape changes. An effective-execution index catches missing, extra, or changed leaf behavior after dispatcher expansion. Claude compares against the complete canonical managed projection. Codex compares against the focused projection extracted from the materializer. Git compares against the installer projection. Unmanaged installed hooks remain in the inventory and lifecycle check, but they do not count as package drift.

The indexes are local immutable maps built once per analysis:

```python
@dataclass(frozen=True)
class ExecutionKey:
    scope: RuntimeScope
    event: str
    trigger_name: str
    target: TargetId
    argument_fingerprint: CommandFingerprint


@dataclass(frozen=True)
class DriftKey:
    event: str
    matcher_key: str
    target: TargetId
    argument_fingerprint: CommandFingerprint


def index_effective_hooks(
    snapshot: HookSnapshot,
) -> Mapping[ExecutionKey, tuple[EffectiveHook, ...]]:
    raise NotImplementedError
```

`ExecutionKey` supports duplicate lookup inside a scope. `DriftKey` omits scope so an expected projection can align with its installed copy. Drift compares timeouts, route targets, and relative managed order after alignment. It ignores absolute group positions because an installer can preserve a user hook before the managed groups. This structure keeps lookup linear in the inventory size. No later cache or secondary database is needed.

### Lifecycle catalog

`packages/claude-dev-env/scripts/hook_audit/lifecycle.json` is the only classification source. Directory names, blocking flags, and command output do not infer lifecycle. The catalog uses portable target IDs:

```json
{
  "schema_version": 1,
  "hooks": {
    "script:blocking/code_rules_enforcer.py": {
      "lifecycle": "move_to_linter",
      "reason": "The check reads proposed source content and belongs in the shared code check.",
      "replacement": "code_rules_gate"
    }
  }
}
```

The parser rejects duplicate JSON keys, unknown enum values, empty reasons, and a missing replacement for `move_to_linter` or `move_to_ci`. It reports a missing catalog row for every effective target. It also reports a stale catalog row that matches no canonical or installed hook. Repeated executions of one target share one lifecycle row. If one script needs two classifications, the audit reports `MIXED_TARGET_SEMANTICS`; the script needs separate entry points.

### Deterministic and private output

The report sorts direct registrations, effective hooks, lifecycle rows, and findings by typed keys before rendering. JSON uses fixed indentation, sorted object keys, UTF-8, and one trailing newline. It contains no timestamp.

Raw paths remain inside readers. Domain records accept only `PortablePath` and `TargetId`. The boundary catches file and JSON errors, normalizes their messages, and drops the original exception text when it can contain a path. Commands are fingerprints only. Known roots collapse before hashing, so the same managed hook has the same identity on Windows and Linux.

## File map

```text
packages/claude-dev-env/scripts/audit_hooks.py
    Thin argument parser, renderer selection, and exit-code policy.

packages/claude-dev-env/scripts/hook_audit/__init__.py
    Exports AuditRequest, AuditReport, InstalledMode, and audit_hooks.

packages/claude-dev-env/scripts/hook_audit/model.py
    Immutable domain types, portable serialization, and sort keys.

packages/claude-dev-env/scripts/hook_audit/readers.py
    JSON reader, command target parser, five static roster adapters,
    Codex projection reader, Git projection reader, and path normalization.

packages/claude-dev-env/scripts/hook_audit/audit.py
    Snapshot assembly, indexes, duplicate checks, drift checks, and lifecycle coverage.

packages/claude-dev-env/scripts/hook_audit/lifecycle.json
    The single lifecycle classification catalog.

packages/claude-dev-env/scripts/tests/test_hook_audit_source.py
    Direct and expanded canonical inventory tests.

packages/claude-dev-env/scripts/tests/test_hook_audit_installed.py
    Claude, Codex, Git, drift, and privacy fixture tests.

packages/claude-dev-env/scripts/tests/test_hook_audit_policy.py
    Duplicate, matcher, catalog, rendering, and no-execution tests.
```

The public interface has one operation. `readers.py` hides five source formats and three installation projections. `audit.py` owns comparison policy. Callers call `audit_hooks`. They do not load, expand, compare, classify, and render as separate stages.

## Test plan

All tests use temporary fixture roots or the checked-in canonical source. They never point at the developer's real home directory.

1. Parse the current canonical `hooks.json` and assert 32 direct commands, exactly five dispatcher registrations, and all event, matcher, timeout, and ordinal values.
2. Expand the five current rosters and assert the ordered child counts `20`, `17`, `2`, `2`, and `2`. Assert 43 expanded leaves and verify representative per-tool narrowing for `apply_patch`, `PowerShell`, `Stop`, and `PostToolUse`.
3. Put a sentinel write in a fixture hook body. Audit it and assert the sentinel file does not exist. Patch `runpy.run_path`, `importlib.import_module`, `exec`, and `eval` to fail if called by a reader.
4. Feed each accepted roster AST shape to the restricted evaluator. Feed an attribute call, comprehension, function call, and computed path and assert `UNSUPPORTED_ROSTER_SYNTAX`.
5. Build a Claude fixture with an old standalone hook beside its dispatcher child. Assert one proven duplicate. Put the same records in canonical and Codex scopes and assert no cross-snapshot duplicate.
6. Cover finite matcher intersection, finite-to-regex proof, equal patterns, and two undecidable patterns.
7. Rewrite only root paths and interpreter names in installed fixtures and assert no drift. Prepend an unmanaged group and assert no order drift. Change a timeout, matcher, managed child order, and child target and assert distinct direct and effective drift findings.
8. Add an unmanaged installed hook. Assert it appears in inventory and needs a lifecycle row, but does not count as package drift.
9. Parse Codex projection literals and the three Git hook names from the checked-in sources. Mock both allowed `git config` calls and reject every other subprocess argument list.
10. Cover global and local `core.hooksPath` evidence, effective local precedence, a generated shim, an opaque native hook, a missing directory, and a path that escapes through a symlink.
11. Cover one lifecycle row per enum value, duplicate keys, unknown values, missing replacements, missing coverage, stale rows, and mixed target semantics.
12. Render the same shuffled records twice and assert byte-identical JSON. Scan output for the fixture username, drive root, home path, raw command, and secret fixture token.
13. Run the focused suite with `python -m pytest packages/claude-dev-env/scripts/tests/test_hook_audit_source.py packages/claude-dev-env/scripts/tests/test_hook_audit_installed.py packages/claude-dev-env/scripts/tests/test_hook_audit_policy.py`.

The source count tests are deliberate tripwires. A hook registration or roster change updates the source, lifecycle row, and expected count in one review.

## Rationale

The execution graph is the core model. A flat inventory cannot tell whether a dispatcher is a hook, whether an installed file is another execution or another snapshot, or whether a native Git shim owns policy. Routes preserve that distinction. The leaf target gives duplicates, drift, and lifecycle coverage one stable join key.

Static, syntax-limited adapters are safer than imports. They return an unsupported-syntax finding when a roster stops being declarative. Five explicit adapters look less clever than a general Python evaluator, and that is a virtue here. The audit stays understandable and never runs the code it judges.

Portable identities solve two problems together. They make source-to-install comparisons meaningful, and they stop reports from leaking usernames or machine paths. Fingerprints keep opaque hooks visible without printing command text.

The catalog records decisions, not discovery. Discovery comes from live configuration and roster sources on every run. A hand-maintained inventory would become a second registration list. The catalog stays the one source of truth for the five lifecycle outcomes.

## Synthesis decision

This candidate recommends the static execution graph as the base. Its defining choices are restricted AST readers, snapshot-scoped duplicate analysis, projection-specific drift, and target-keyed lifecycle policy. Synthesis still selects or grafts this candidate.

## Tradeoffs accepted

- We accept five small roster adapters in exchange for a hard no-import boundary.
- We accept an explicit unsupported-syntax finding in exchange for refusing to guess at computed Python or JavaScript configuration.
- We accept incomplete proof for arbitrary regex-to-regex overlap in exchange for never reporting a duplicate that the matcher model cannot prove.
- We accept content-based opaque identities in exchange for keeping external commands and paths out of reports.
- We accept checked-in count tripwires in exchange for catching a newly added dispatcher or roster child during the same change.

## Alternatives considered

### Import the five constants modules

This shape has less parser code, but imports execute module top-level code and extend the trusted boundary to every future import. The caller still needs separate command, projection, privacy, and classification logic. The interface looks small while hiding an unsafe dependency.

### Keep one hand-written inventory file

A single ledger could list registrations, dispatcher children, Git hooks, and lifecycle decisions. It would be easy to render and hard to trust. Every hook change would require synchronized edits to runtime configuration and the ledger. The chosen design derives inventory and keeps only human lifecycle decisions in the catalog.

### Scan Python and JSON with regular expressions

Regex scanners are short until quoting, inline Python, constructor defaults, aliases, and Windows paths arrive. Their uncertainty leaks into every detector. Restricted syntax adapters put uncertainty at the read boundary and return typed records to the rest of the tool.

## Open questions and risks

- Should `MATCHER_OVERLAP_UNKNOWN` fail continuous integration, or remain a warning until matcher syntax becomes finite?
- Does Codex intend to keep one focused managed hook? If its projection grows, the static reader needs a supported literal collection instead of one target constant.
- Should an active external `core.hooksPath` count as Git drift when it intentionally belongs to Husky or Lefthook? The inventory can classify it without claiming package drift unless the user marks the path package-managed.
- Can a hook target legitimately need two lifecycle outcomes? The design treats that as a split-entry-point signal. A real counterexample would require a policy key wider than `TargetId`.
- Reparse points can escape a declared root. The reader should report the escape and hash only the link metadata unless the user explicitly adds the resolved root.

## Next implementation step

Add the core types and five restricted roster adapters with one failing source-only test that expects 32 direct registrations, five dispatchers, and 43 expanded leaves.
