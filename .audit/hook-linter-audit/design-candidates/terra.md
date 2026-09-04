# Terra candidate: compile one hook snapshot

## Problem

The package manifest hides real executions behind five dispatchers. Installed Claude and Codex files can add, copy, or change those registrations. Git can add another boundary through `core.hooksPath`. The audit needs one complete, reviewable picture without importing a hook module, running a command string, or printing a local path or command payload.

## Usage (caller's view)

Run the package-only audit first. It inventories every direct manifest command and expands the five declared dispatcher rosters.

```powershell
python packages/claude-dev-env/scripts/audit_hooks.py --format json
```

Add the active files when the operator wants to compare installed configuration. The tool labels paths as `$CLAUDE_HOME`, `$CODEX_HOME`, `$GIT_HOOKS`, or `$REPO` in its output.

```powershell
python packages/claude-dev-env/scripts/audit_hooks.py `
  --claude-hook-json "$env:USERPROFILE/.claude/settings.json" `
  --codex-hook-json "$env:USERPROFILE/.codex/hooks.json" `
  --git-repository . `
  --format json `
  --output .audit/hook-linter-audit/inventory.json `
  --strict
```

Library callers get one snapshot and inspect its findings. They do not load sources, expand rosters, compare files, or apply lifecycle rules themselves.

```python
request = AuditRequest.for_package(PACKAGE_ROOT)
report = audit(request)
assert report.status is AuditStatus.CLEAN
```

The CI job calls the same interface with the checked-in lifecycle catalog. A missing classification, unexpanded dispatcher, malformed source, definite duplicate, or drift finding makes `--strict` return a nonzero status.

```python
report = audit(AuditRequest.for_package(PACKAGE_ROOT, strict=True))
raise_for_failures(report)
```

## Shape

`audit()` is a snapshot compiler. It reads configuration and roster declarations as data, turns them into logical executions, then applies the catalog and comparison rules in memory. It writes nothing unless the caller supplies `--output`. It runs `git config --show-origin --get-all core.hooksPath` through an argument list when `--git-repository` is present. That command reads Git configuration and does not invoke a Git hook. No hook command, Python hook module, shell string, or discovered shim runs.

```
package manifest ─┐
Claude JSON     ─┼─> configured registrations ─> expanded executions ─> checks ─> report
Codex JSON      ─┤                                  │                    │
Git hooks path  ─┘                                  └─> lifecycle catalog ┘
                         static Python roster AST ──────^
```

The package manifest remains the expected Claude registration. It is an expectation source, not an active runtime plane, so it never creates a false duplicate with installed Claude configuration. Every optional Claude file shares the `claude` runtime plane. Every optional Codex file shares the `codex` plane. Git receives its own plane. Duplicate checks run inside one plane. Drift checks compare matching managed identities across the package and installed sources.

### Dispatcher coverage

`DispatcherRegistry` is a fixed table with one entry for each current dispatcher command. It points at the declaration that already owns the roster. `StaticRosterReader` parses a restricted Python AST and resolves only literal strings, tuples, frozensets, union expressions, and local `from ... import ...` aliases. It does not import the constants module. A new manifest command ending in `dispatcher.py` without a registry entry is an `unexpanded_dispatcher` error.

| Manifest command tail | Roster declaration | Child selector |
| --- | --- | --- |
| `blocking/pre_tool_use_dispatcher.py` | `hooks_constants/pre_tool_use_dispatcher_constants.py:ALL_HOSTED_HOOK_ENTRIES` | `applicable_tool_names` intersected with the manifest matcher |
| `blocking/bash_pre_tool_use_dispatcher.py` | `hooks_constants/bash_pre_tool_use_dispatcher_constants.py:ALL_BASH_HOSTED_HOOK_ENTRIES` | `applicable_tool_names` intersected with the manifest matcher |
| `blocking/bash_post_call_dispatcher.py` | `hooks_constants/bash_post_call_dispatcher_constants.py:ALL_BASH_POST_TOOL_USE_HOSTED_HOOK_ENTRIES` | `applicable_tool_names` intersected with the manifest matcher |
| `validation/post_tool_use_dispatcher.py` | `hooks_constants/post_tool_use_dispatcher_constants.py:ALL_POST_HOSTED_HOOK_ENTRIES` | inherited manifest matcher |
| `blocking/stop_dispatcher.py` | `hooks_constants/stop_dispatcher_constants.py:ALL_STOP_HOSTED_HOOK_PATHS` | inherited manifest matcher |

The compiler emits a launcher execution and one child execution per roster member. That reflects what runs: the dispatcher itself starts, then each selected child starts in its process. Direct commands such as the inline `validators.run_all_validators` runner stay direct entries. They receive a logical module target when the restricted inline-Python parser recognizes the import. Everything else remains an opaque command that the audit tracks by registration location without emitting its text.

### Data types

```python
class LifecycleDisposition(StrEnum):
    DELETE = "delete"
    MOVE_TO_LINTER = "move_to_linter"
    MOVE_TO_CI = "move_to_ci"
    KEEP_AUTOMATION = "keep_nonblocking_automation"
    KEEP_BOUNDARY_CHECK = "keep_boundary_check"


class RuntimePlane(StrEnum):
    PACKAGE = "package"
    CLAUDE = "claude"
    CODEX = "codex"
    GIT = "git"


class ExpansionKind(StrEnum):
    DIRECT = "direct"
    DISPATCHER = "dispatcher"
    DISPATCHED_CHILD = "dispatched_child"
    NATIVE_GIT = "native_git"


class SelectorConfidence(StrEnum):
    EXACT = "exact"
    POSSIBLE = "possible"


@dataclass(frozen=True)
class AuditRequest:
    package_root: Path
    lifecycle_catalog_path: Path
    claude_hook_jsons: tuple[Path, ...] = ()
    codex_hook_jsons: tuple[Path, ...] = ()
    git_repository: Path | None = None
    strict: bool = False

    @classmethod
    def for_package(
        cls,
        package_root: Path,
        strict: bool = False,
    ) -> "AuditRequest":
        raise NotImplementedError


@dataclass(frozen=True)
class SourceRef:
    plane: RuntimePlane
    ordinal: int
    display_name: str


@dataclass(frozen=True)
class RegistrationRef:
    source: SourceRef
    event: str
    group_index: int
    hook_index: int
    matcher: str | None


@dataclass(frozen=True)
class ToolSelector:
    exact_tool_names: frozenset[str] | None
    raw_matcher: str | None


@dataclass(frozen=True)
class ManagedTarget:
    logical_name: str
    relative_path: PurePosixPath | None


@dataclass(frozen=True)
class OpaqueTarget:
    registration: RegistrationRef


HookTarget = ManagedTarget | OpaqueTarget


@dataclass(frozen=True)
class ConfiguredRegistration:
    ref: RegistrationRef
    selector: ToolSelector
    target: HookTarget
    invocation_text: str


@dataclass(frozen=True)
class EffectiveExecution:
    ref: RegistrationRef
    target: HookTarget
    selector: ToolSelector
    kind: ExpansionKind
    ancestry: tuple[PurePosixPath, ...]
    extra_arguments: tuple[PurePosixPath, ...]


@dataclass(frozen=True)
class LifecycleEntry:
    disposition: LifecycleDisposition
    reason: str
    owner: str
    evidence: str


@dataclass(frozen=True)
class LifecycleCatalog:
    entries: Mapping[str, LifecycleEntry]


@dataclass(frozen=True)
class DuplicateFinding:
    left: EffectiveExecution
    right: EffectiveExecution
    confidence: SelectorConfidence


@dataclass(frozen=True)
class DriftFinding:
    kind: Literal["registration", "content"]
    target: ManagedTarget
    sources: tuple[SourceRef, ...]


@dataclass(frozen=True)
class AuditReport:
    configured: tuple[ConfiguredRegistration, ...]
    effective: tuple[EffectiveExecution, ...]
    classifications: Mapping[EffectiveExecution, LifecycleEntry | None]
    duplicates: tuple[DuplicateFinding, ...]
    drift: tuple[DriftFinding, ...]
    errors: tuple[str, ...]
    status: "AuditStatus"
```

`ManagedTarget.logical_name` has stable, reviewable names such as `hook:blocking/pii_prevention_blocker.py`, `module:validators.run_all_validators`, and `native-git:pre-commit`. It never holds an absolute path. The catalog uses these names as keys. The normalizer keeps an internal resolved path only long enough to read an allowed managed script and compare its bytes. It reports `external registration <source/event/group/hook>` for opaque or unrecognized installed commands. It keeps their raw string in the parser process only; JSON and text output omit it.

The catalog is one checked-in file, `packages/claude-dev-env/hooks/hook_lifecycle.json`. It holds every decision and its reason. Code holds no fallback disposition. An observed execution without a catalog entry is a failure. A catalog entry with no source-manifest execution is stale and fails the package-only audit. That catches a deleted or renamed hook before the catalog becomes fiction.

```json
{
  "schema_version": 1,
  "entries": {
    "hook:blocking/pre_tool_use_dispatcher.py": {
      "disposition": "keep_boundary_check",
      "reason": "Hosts write-boundary policy checks.",
      "owner": "hooks",
      "evidence": "hooks.json PreToolUse"
    }
  }
}
```

### Function signatures

The CLI and `audit()` are the public interface. The remaining functions stay package-private.

```python
def main(argv: Sequence[str] | None = None) -> int:
    raise NotImplementedError


def audit(request: AuditRequest) -> AuditReport:
    raise NotImplementedError


def load_configured_registrations(request: AuditRequest) -> tuple[ConfiguredRegistration, ...]:
    raise NotImplementedError


def parse_hook_json(
    source: SourceRef,
    json_path: Path,
    normalizer: "PathNormalizer",
) -> tuple[ConfiguredRegistration, ...]:
    raise NotImplementedError


def read_effective_git_hooks(
    repository: Path,
    normalizer: "PathNormalizer",
) -> tuple[ConfiguredRegistration, ...]:
    raise NotImplementedError


def expand_dispatchers(
    registrations: Sequence[ConfiguredRegistration],
    registry: "DispatcherRegistry",
) -> tuple[EffectiveExecution, ...]:
    raise NotImplementedError


def read_roster(spec: "DispatcherSpec", package_root: Path) -> tuple["RosterMember", ...]:
    raise NotImplementedError


def intersect_selectors(left: ToolSelector, right: ToolSelector) -> ToolSelector | None:
    raise NotImplementedError


def find_duplicate_executions(
    executions: Sequence[EffectiveExecution],
) -> tuple[DuplicateFinding, ...]:
    raise NotImplementedError


def find_drift(
    executions: Sequence[EffectiveExecution],
    normalizer: "PathNormalizer",
) -> tuple[DriftFinding, ...]:
    raise NotImplementedError


def classify(
    executions: Sequence[EffectiveExecution],
    catalog: LifecycleCatalog,
) -> Mapping[EffectiveExecution, LifecycleEntry | None]:
    raise NotImplementedError
```

`parse_hook_json` accepts both the source shape with a top-level `hooks` object and installed files that expose the same object. It validates each event, matcher group, hook record, and command field at the JSON boundary. Invalid structures yield source-labelled diagnostics and leave other readable sources available for the report.

`read_effective_git_hooks` calls `git` through `subprocess.run` with a fixed argument vector, resolves an absolute or repository-relative `core.hooksPath`, and inspects only regular files with Git-recognized native hook names. It parses a managed Python shim with `ast`, maps it to the local script that the shim names, and records an opaque native hook when the shim does not match. It stays inside the configured hooks directory. It does not execute Git's hook runner, a shim, or its referenced module.

`intersect_selectors` represents simple `A|B|C` matchers as exact tool-name sets. It tests a roster's known tool names against an opaque regex with `re.fullmatch`. Two unrelated opaque regexes create a possible overlap finding rather than a false definite duplicate. A failed matcher compile becomes a validation error.

`find_duplicate_executions` groups by runtime plane, event, and target. It compares selectors after expansion, so a direct `Write` registration and the same dispatcher child on `Write` is a definite duplicate. Package expectations, installed Claude configuration, Codex configuration, and Git remain separate planes. This prevents a package definition from looking like an active second hook.

`find_drift` compares only managed targets. It detects distinct normalized registration shapes for the same expected Claude target, plus byte differences between readable copies under known package, Claude, Codex, or Git-hook roots. It reports `content differs` or `registration differs`, never a digest or script body. Opaque external commands receive a classification error instead of content comparison.

## File map

```text
packages/claude-dev-env/
  hooks/
    hook_lifecycle.json
  scripts/
    audit_hooks.py
    hook_audit/
      __init__.py
      model.py
      sources.py
      roster_reader.py
      audit.py
      render.py
      tests/
        test_sources.py
        test_roster_reader.py
        test_audit.py
        test_render.py
        fixtures/
```

`sources.py` owns untrusted text and filesystem boundaries. `roster_reader.py` owns the small static Python language used by existing roster constants. `audit.py` owns the domain decision of what is effective, duplicated, drifting, or unclassified. `render.py` only serializes an already-sanitized report. This keeps source formats out of callers and stops transport records from escaping through the library interface.

Output uses UTF-8, sorted object keys, fixed source order (`package`, `claude`, `codex`, `git`), and registration order within each source. It has no timestamp, hostname, absolute path, command string, environment value, or file content. The same inputs produce byte-identical JSON.

## Test plan

- Parse the repository `hooks.json` into every direct registration. Assert event, matcher, and command order without loading a hook module.
- Read each real dispatcher roster and assert the five command tails map to the five declared symbols. A source manifest dispatcher absent from `DispatcherRegistry` fails the test.
- Give `StaticRosterReader` a module whose top-level statement writes a sentinel. Parse its literal roster and assert the sentinel remains absent.
- Expand fixture registrations for each dispatcher. Assert a launcher and each roster child appear with the expected event, ancestry, selector intersection, and extra arguments.
- Cover the inline `run_all_validators` command as a direct module target. Cover an unrecognized command as an opaque target whose output contains no command text.
- Create direct and dispatched copies of one hook on the same `Write` selector and assert a definite duplicate. Use two unrelated opaque regexes and assert a possible result instead of a definite result.
- Use copied managed scripts with different bytes and matching registration shapes. Assert a content-drift finding without a hash or path. Change a normalized command shape and assert registration drift.
- Feed malformed Claude and Codex JSON, malformed matchers, unsupported roster expressions, and an unreadable optional file. Assert stable diagnostics and a complete report for the other sources.
- Use temporary home directories and commands containing a fake token. Assert JSON has no temporary root, username, token, raw command, file body, or content digest. Run the same fixture twice and compare output bytes.
- Stub the fixed `git config` process boundary, create a native `pre-commit` shim and its managed script, and assert native inventory. Assert the stub receives only the config query and no hook executable runs.
- Omit one catalog entry and add one stale entry. Assert both failures. Run the package-only audit against the checked-in catalog and require a clean result before CI accepts catalog edits.

Focused checks stay cheap:

```powershell
python -m pytest packages/claude-dev-env/scripts/hook_audit/tests -q
python packages/claude-dev-env/scripts/audit_hooks.py --format json --strict
```

## Rationale

The audit's hard part is reconstructing logical executions while avoiding the behavior it studies. Static reading gives the dispatcher constants their existing ownership and keeps the audit side-effect free. The single `audit()` call hides configuration shapes, matcher arithmetic, AST details, source-plane comparisons, and privacy handling. Callers see one immutable report. That is a deep interface with a small surface.

`hook_lifecycle.json` is the sole decision record. The audit derives coverage from manifests and rosters, then checks the catalog against that derived set. A new hook therefore fails visibly until someone records a lifecycle decision. The catalog also records why the decision belongs there, which gives the later linter or CI migration a useful trail.

The compiler preserves registration order for evidence and uses normalized identities only for comparison. It separates active runtime planes from expected source so installed copies show drift without looking like duplicate active processes. Per boundary-discipline, JSON, AST, filesystem, and Git output are validated at their edges. The core comparisons use typed records and pure functions.

## Synthesis decision

This is the Terra candidate. Arena should choose it only if the static roster reader and one-snapshot interface beat the other candidates on complete expansion and a smaller caller surface.

## Tradeoffs accepted

- We accept a small restricted AST evaluator in exchange for proving that roster inspection cannot run hook module code.
- We accept a checked-in catalog that needs maintenance in exchange for one visible lifecycle decision for every effective hook.
- We accept possible duplicate findings for opaque-regex intersections in exchange for avoiding false certainty about regex semantics.
- We accept a fixed Git-hook name catalog in exchange for inventorying actual Git entry points instead of every support module in `core.hooksPath`.
- We accept opaque external-hook failures in exchange for keeping personal command text, paths, and potential credentials out of audit output.

## Alternatives considered

- Import dispatcher constants and read their tuples. It loses the strongest safety property because a changed constants module can run arbitrary import-time code. The caller still receives the same report, but the audit boundary becomes unsafe.
- Use a generic sequence of loader, validator, transformer, and reporter plugins. It exposes execution stages and source-format choices to callers, adds pass-through layers, and makes static dispatcher coverage harder to prove.
- Parse `hooks.json` with shell tools and inspect installed files by printing commands. It is quick for one machine but leaks personal paths and command text, handles quoting poorly, and has no stable programmatic report.

## Open questions and risks

- Which Claude and Codex configuration layers merge in the target runtime, and should the CLI accept an explicit runtime-plane label when users supply more than one installed file?
- Does the lifecycle review want the Git shim itself classified, its target Python script classified, or both? The proposed identity follows the target script and retains the native event as execution evidence.
- Which current direct composite runners besides `run_all_validators` deserve safe static expansion in a later change? The first version classifies them as direct targets so it does not mistake an incomplete expansion for coverage.
- How should CI obtain an installed-config fixture without reading a developer's home directory? The package-only audit is the CI gate. Installed scans remain an explicit operator command with synthetic fixtures in tests.

## Next implementation step

Add the immutable records and a package-manifest parser test that returns every configured registration with sanitized source references, without dispatcher expansion or installed configuration reads.
