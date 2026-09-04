# Candidate Luna: execution-graph hook audit

## Usage

The command reads configuration, source rosters, and native Git metadata. It never invokes a hook. It prints one deterministic JSON report to stdout.

```text
python -m scripts.hook_audit \
  --package-root packages/claude-dev-env \
  --classifications packages/claude-dev-env/hooks/hook-lifecycle.json \
  --claude-json "$HOME/.claude/settings.json" \
  --codex-json "$HOME/.codex/hooks.json" \
  --git-root .
```

The source-only CI call omits the three optional installed inputs:

```text
python -m scripts.hook_audit --package-root packages/claude-dev-env --format json
```

A test or another Python tool calls `audit` once.

```python
from pathlib import Path

from scripts.hook_audit import AuditOptions, audit

report = audit(
    AuditOptions(
        package_root=Path("packages/claude-dev-env"),
        classification_file=Path("packages/claude-dev-env/hooks/hook-lifecycle.json"),
        claude_json=None,
        codex_json=None,
        git_root=None,
    )
)
assert report.schema_version == 1
```

The local comparison call supplies fixture paths instead of personal defaults:

```python
report = audit(
    AuditOptions(
        package_root=fixture_package,
        classification_file=fixture_classifications,
        claude_json=fixture_claude_settings,
        codex_json=fixture_codex_hooks,
        git_root=fixture_repository,
    )
)
```

## Problem

`hooks/hooks.json` records direct commands, but five dispatchers hide their leaf hooks in Python roster constants. The current source has 32 direct commands. The installed Claude and Codex files contain different merged and older shapes, including standalone commands that also occur inside dispatcher rosters. The installer rewrites plugin-root paths and native Git uses the effective `core.hooksPath`. A text search cannot tell whether two commands run the same leaf hook, whether an installed roster drifted from source, or whether a hook has an explicit lifecycle decision. The audit needs one graph that records direct declarations and expanded executions. Personal paths stay out of the output.

## Shape

The tool is a graph builder. It first creates `Registration` nodes for package, installed Claude, installed Codex, and optional native Git sources. It then resolves each command into a `HookTarget` and adds `EffectiveExecution` nodes. A dispatcher registration adds one classified runner node plus one leaf execution for every roster entry. Direct commands add one leaf execution. The graph retains `route`, so a duplicate can say that a standalone command and a dispatcher child reach the same target.

The five dispatcher specifications are fixed metadata in the audit module. They identify the Python file, its event, the constants file, and the roster symbol.

| Dispatcher | Event | Roster source | Symbol |
| --- | --- | --- | --- |
| `blocking/pre_tool_use_dispatcher.py` | `PreToolUse` | `hooks_constants/pre_tool_use_dispatcher_constants.py` | `ALL_HOSTED_HOOK_ENTRIES` |
| `blocking/bash_pre_tool_use_dispatcher.py` | `PreToolUse` | `hooks_constants/bash_pre_tool_use_dispatcher_constants.py` | `ALL_BASH_HOSTED_HOOK_ENTRIES` |
| `blocking/bash_post_call_dispatcher.py` | `PostToolUse` | `hooks_constants/bash_post_call_dispatcher_constants.py` | `ALL_BASH_POST_TOOL_USE_HOSTED_HOOK_ENTRIES` |
| `validation/post_tool_use_dispatcher.py` | `PostToolUse` | `hooks_constants/post_tool_use_dispatcher_constants.py` | `ALL_POST_HOSTED_HOOK_ENTRIES` |
| `blocking/stop_dispatcher.py` | `Stop` | `hooks_constants/stop_dispatcher_constants.py` | `ALL_STOP_HOSTED_HOOK_PATHS` |

The roster reader parses those constants files with `ast.parse`. It evaluates only string literals, tuple and set literals, known names, set union, and the three known entry constructors. It never imports a dispatcher, imports a hook, calls `runpy`, or evaluates arbitrary Python. Unsupported roster syntax produces a diagnostic and no guessed children. For a dispatcher registration, the child coverage is the intersection of the parent matcher and the roster entry's applicable tool set. This preserves `apply_patch` narrowing and installed matcher drift.

Every target receives a stable `hook_id`. A source or managed installed path becomes `hook:<relative-path>` after root recognition. An unrecognized path becomes `external:<sha256-of-normalized-path>`. Inline commands and non-command hook bodies use a digest of a redacted normalized form. The report never stores the original command or absolute path.

Path normalization applies before identity comparison. It converts separators, folds Windows case, expands only known path tokens such as `${CLAUDE_PLUGIN_ROOT}`, `$HOME`, `${HOME}`, `%USERPROFILE%`, and `~`, and maps recognized roots to `<package>`, `<repo>`, `<claude-home>`, `<codex-home>`, `<agents-home>`, and `<git-hooks>`. A path outside a recognized root becomes a short SHA-256 label. Command parsing handles quoted Windows and POSIX tokens plus the installer's literal base64 path expression. It decodes base64 data only as data. It does not execute the expression.

The lifecycle registry is the only source of classification. `hooks/hook-lifecycle.json` contains one exact entry per stable `hook_id` and one value from this enum. It covers dispatcher runners, leaf hooks, direct commands, non-command hooks, and native Git entrypoints.

```python
class LifecycleClass(StrEnum):
    DELETE = "delete"
    LINTER = "linter"
    CONTINUOUS_INTEGRATION = "continuous-integration"
    NONBLOCKING_AUTOMATION = "nonblocking-automation"
    BOUNDARY = "boundary"
```

The audit does not infer a class from `blocking/`, `validation/`, or any other directory. Duplicate registry keys, unknown classes, a missing entry, and an entry for an unknown target are findings. Strict mode returns a nonzero status for any of them. A registry can classify a user hook by the emitted external digest without exposing its path.

The public interface is three functions. `audit` builds the graph and findings. `render_json` emits sorted keys and stable arrays. `main` parses command-line options and returns a status. Callers pass typed records, not raw JSON dictionaries.

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence


@dataclass(frozen=True)
class AuditOptions:
    package_root: Path
    classification_file: Path
    claude_json: Path | None
    codex_json: Path | None
    git_root: Path | None
    strict: bool = True
    output_format: Literal["json"] = "json"


def audit(options: AuditOptions) -> AuditReport:
    """Build the read-only execution graph and its findings."""
    raise NotImplementedError("design only")


def render_json(report: AuditReport) -> str:
    """Serialize a report without raw commands, personal paths, or timestamps."""
    raise NotImplementedError("design only")


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the audit CLI and print one machine-readable report."""
    raise NotImplementedError("design only")
```

```python
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class SourceKind(StrEnum):
    PACKAGE = "package"
    CLAUDE = "claude"
    CODEX = "codex"
    GIT = "git"


class HookKind(StrEnum):
    COMMAND = "command"
    DISPATCHER = "dispatcher"
    PROMPT = "prompt"
    GIT_ENTRYPOINT = "git-entrypoint"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PathRoots:
    package_root: Path
    repository_root: Path | None
    home: Path
    claude_home: Path
    codex_home: Path
    agents_home: Path
    git_hooks: Path | None


@dataclass(frozen=True)
class DispatcherSpec:
    target_relative_path: str
    event: str
    roster_relative_path: str
    roster_symbol: str


@dataclass(frozen=True)
class RosterEntry:
    target_relative_path: str
    applicable_tools: frozenset[str]


GitConfigGetter = Callable[[Path], str | None]


@dataclass(frozen=True)
class Coverage:
    matcher_key: str
    known_tools: frozenset[str]
    has_unknown_pattern: bool


@dataclass(frozen=True)
class HookTarget:
    hook_id: str
    display_path: str
    kind: HookKind
    content_digest: str | None
    command_key: str


class ExecutionRole(StrEnum):
    RUNNER = "runner"
    LEAF = "leaf"


@dataclass(frozen=True)
class Registration:
    source: SourceKind
    ordinal: int
    event: str
    matcher: Coverage
    target: HookTarget
    timeout_seconds: int | None
    route: tuple[str, ...]


@dataclass(frozen=True)
class EffectiveExecution:
    execution_id: str
    source: SourceKind
    event: str
    coverage: Coverage
    target: HookTarget
    timeout_seconds: int | None
    route: tuple[str, ...]
    ordinal: int
    role: ExecutionRole


class FindingKind(StrEnum):
    DUPLICATE_EXECUTION = "duplicate-effective-execution"
    DRIFT = "drift"
    MISSING_CLASSIFICATION = "missing-classification"
    INVALID_CLASSIFICATION = "invalid-classification"
    ROSTER_READ_FAILURE = "roster-read-failure"
    CONFIG_READ_FAILURE = "config-read-failure"
    OVERLAP_UNPROVEN = "overlap-unproven"


@dataclass(frozen=True)
class Finding:
    kind: FindingKind
    code: str
    severity: Literal["error", "warning"]
    hook_ids: tuple[str, ...]
    execution_ids: tuple[str, ...]
    sources: tuple[SourceKind, ...]


@dataclass(frozen=True)
class AuditReport:
    schema_version: int
    source_fingerprints: tuple[tuple[str, str], ...]
    executions: tuple[EffectiveExecution, ...]
    classifications: tuple[tuple[str, LifecycleClass], ...]
    findings: tuple[Finding, ...]

    @property
    def is_clean(self) -> bool:
        """Return true when the graph has no error finding."""
        raise NotImplementedError("design only")
```

The internal signatures keep each boundary testable.

```python
def read_config_registrations(
    path: Path,
    source: SourceKind,
    roots: PathRoots,
) -> tuple[Registration, ...]:
    """Read hook groups without running command entries."""
    raise NotImplementedError("design only")


def read_dispatcher_roster(
    package_root: Path,
    dispatcher_target: HookTarget,
    spec: DispatcherSpec,
) -> tuple[RosterEntry, ...]:
    """Parse one known roster with a restricted Python AST reader."""
    raise NotImplementedError("design only")


def expand_dispatcher_registrations(
    registrations: tuple[Registration, ...],
    package_root: Path,
    roots: PathRoots,
) -> tuple[EffectiveExecution, ...]:
    """Add dispatcher children with inherited event and intersected coverage."""
    raise NotImplementedError("design only")


def read_native_git_registrations(
    repository_root: Path,
    git_config_getter: GitConfigGetter,
    roots: PathRoots,
) -> tuple[Registration, ...]:
    """Read core.hooksPath and direct Git hook entrypoints without invoking them."""
    raise NotImplementedError("design only")


def normalize_target(
    command_or_path: str,
    roots: PathRoots,
    kind: HookKind,
) -> HookTarget:
    """Return a stable identity and redacted display form."""
    raise NotImplementedError("design only")


def compare_effective_executions(
    source_executions: tuple[EffectiveExecution, ...],
    active_executions: tuple[EffectiveExecution, ...],
) -> tuple[Finding, ...]:
    """Find duplicate targets and source-to-installed command or roster drift."""
    raise NotImplementedError("design only")


def apply_classifications(
    executions: tuple[EffectiveExecution, ...],
    registry_path: Path,
) -> tuple[tuple[str, LifecycleClass], tuple[Finding, ...]]:
    """Require one exact registry class for every effective target."""
    raise NotImplementedError("design only")
```

The analysis order is fixed and idempotent.

```text
read package hooks.json
read optional Claude and Codex JSON files
read optional effective core.hooksPath and Git entrypoint names
normalize every target and matcher
expand every recognized dispatcher from its AST roster
mark source executions as desired and installed or Git executions as active
find duplicate active executions with overlapping known coverage
compare desired and active signatures for drift
apply the one lifecycle registry to every effective target
sort the graph and findings by source, event, target, route, and ordinal
render JSON with no wall clock, environment value, or raw path
```

Duplicate detection uses the same `hook_id`, event, and overlapping coverage for leaf executions. It also reports repeated runner registrations. Different argument keys or timeout values add a drift finding but do not hide the duplicate. Unknown regex overlap is reported as `overlap-unproven`; the tool never claims that two patterns are disjoint from a weak parser. Source-only duplicate findings and active duplicate findings carry different source fields, so the package declaration is not mistaken for a running process.

Drift comparison pairs source and installed executions by `hook_id`, event, and route role. It reports missing managed executions, unexpected installed executions, matcher coverage changes, timeout changes, command argument changes, content digest changes, and roster child changes. An absent optional installed input means "not inspected", not "clean" and not "drifted".

## Synthesis decision

This candidate recommends the graph-first shape as the base. The graph keeps the dispatcher route beside the leaf target, so a duplicate finding can name both paths. The static AST roster reader keeps the five Python rosters as the source of truth. The exact lifecycle registry keeps policy out of directory names. A missing classification is a hard, testable failure.

## Tradeoffs accepted

- We accept a small restricted AST evaluator in exchange for never importing or running hook code.
- We accept hashed labels for unrecognized paths in exchange for cross-file identity without personal data.
- We accept an `overlap-unproven` finding for unsupported matcher expressions in exchange for avoiding false claims about duplicate coverage.
- We accept one registry entry per target in exchange for an explicit lifecycle decision and no directory-based default.
- We accept a JSON-only CLI in exchange for stable machine consumption and a small public interface.

## Alternatives considered

The flat command walker reads every `command` field and compares normalized strings. It is short, but it hides dispatcher children and cannot explain a standalone child versus a dispatcher duplicate.

Importing dispatcher constants and calling their Python objects gives exact rosters with little parser code. It also imports the dispatcher dependency graph, can trigger import-time behavior, and makes the read-only guarantee depend on every hook author.

A parser per source writes separate package, Claude, Codex, and Git reports and merges them later. Each parser would repeat target normalization and matcher rules. The caller would learn several report shapes, and path drift would hide behind a late merge.

## Open questions and risks

- Should an unclassified user-owned hook make the default CLI exit nonzero, or should only `--strict` make it an error?
- Should the report treat simultaneous Claude and Codex coverage as an active duplicate, or label it as a possible duplicate when both config files are supplied?
- Should native Git entrypoints remain leaf executions, or should a later version add a second restricted static reader for their subprocess targets?
- Which unsupported matcher forms need exact finite-tool expansion before the first implementation? The initial version should report them instead of guessing.

## Next implementation step

Add `hook_audit.py` with `AuditOptions`, `HookTarget`, `Coverage`, and a fixture-backed JSON reader that normalizes paths without opening or executing any hook.

## File map

- `packages/claude-dev-env/scripts/hook_audit.py` owns the public API, restricted AST roster reader, normalized execution graph, comparison rules, renderer, and CLI.
- `packages/claude-dev-env/hooks/hook-lifecycle.json` is the reviewed, exact-key classification registry and the only lifecycle policy source.
- `packages/claude-dev-env/scripts/test_hook_audit.py` holds focused fixture tests for each reader and pure comparison function.
- `.audit/hook-linter-audit/inventory.json` is not written by the tool. A caller can redirect the deterministic stdout report when a durable artifact is needed.

## Test plan

- Parse package, Claude, and Codex fixture JSON with every event shape, empty matcher, multiple matcher groups, non-command entry, malformed group, and missing file.
- Assert the five dispatcher specifications expand the expected leaf paths and intersect parent matcher coverage correctly, including the narrower `apply_patch` roster.
- Feed dispatcher source fixtures containing an unsupported AST expression and assert a roster-read finding without any import or execution.
- Normalize equivalent Windows, POSIX, home-token, plugin-root, and installer base64 command forms to the same `hook_id`; assert that output contains only placeholders or hashes.
- Create a fixture with a standalone child plus a dispatcher child and assert one duplicate finding. Use non-overlapping matchers and assert no duplicate finding.
- Change an installed timeout, interpreter argument, matcher, roster child, and script digest one at a time and assert the matching drift code.
- Test missing, duplicate, unknown, and complete registry entries. Assert that directory names never supply a default class.
- Inject a fake Git config getter and assert that `core.hooksPath` and direct Git entrypoints are read while `subprocess.run`, `runpy.run_path`, and hook `main` functions are never called.
- Render the same fixture twice and assert byte-identical JSON, sorted findings, no timestamps, no raw command strings, no absolute user paths, and stable SHA-256 fingerprints.
- Run the focused test file with `python -m pytest packages/claude-dev-env/scripts/test_hook_audit.py`.
