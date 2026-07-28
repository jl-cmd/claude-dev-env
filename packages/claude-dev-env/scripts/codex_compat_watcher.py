"""Safe, optional link planning and debounced compatibility reconciliation."""

from __future__ import annotations

import filecmp
import os
import shutil
import stat
import threading
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Literal

from codex_compat_materializer import (
    MaterializerConfig,
    MaterializerError,
    build_plan,
    publish_plan,
    validate_target_path,
)

LinkKind = Literal["symlink", "junction", "copy", "materialize"]
LinkClassification = Literal["byte_compatible", "source_only", "unsupported"]


class _WatcherConfiguration:
    materialize_link_kind = "materialize"
    copy_link_kind = "copy"
    symlink_link_kind = "symlink"
    junction_link_kind = "junction"
    all_configured_root_names = ("agents", "commands", "hooks", "rules", "skills")
    all_unsafe_event_kinds = {"overflow", "ambiguous", "inaccessible", "error", "unknown"}
    reparse_point_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


@dataclass(frozen=True)
class LinkSpec:
    source: str
    target: str
    is_byte_compatible: bool = True
    classification: LinkClassification | None = None
    requested_kind: LinkKind = "symlink"
    should_activate_hook: bool = False
    should_activate_script: bool = False


@dataclass(frozen=True)
class LinkDecision:
    source: str
    target: str
    kind: LinkKind
    action: str
    reason: str


@dataclass
class LinkPlan:
    decisions: list[LinkDecision] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    is_dry_run: bool = True


@dataclass
class LinkReport:
    decisions: list[LinkDecision] = field(default_factory=list)
    applied: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    is_reconcile_required: bool = False
    reconcile_reasons: list[str] = field(default_factory=list)
    reconcile_paths: list[str] = field(default_factory=list)

    @property
    def reconcile_required(self) -> bool:
        return self.is_reconcile_required

    @reconcile_required.setter
    def reconcile_required(self, is_required: bool) -> None:
        self.is_reconcile_required = is_required


@dataclass(frozen=True)
class LinkCapabilities:
    symlink: bool
    junction: bool


@dataclass(frozen=True)
class WatchEvent:
    source_root: str
    kind: str = "changed"
    is_self_event: bool = False
    path: str = ""


def probe_link_capabilities(
    symlink_probe: Callable[[], bool] | None = None,
    junction_probe: Callable[[], bool] | None = None,
    should_allow_temporary_probe: bool = False,
) -> LinkCapabilities:
    """Probe link support while preserving a conservative default.

    Args:
        symlink_probe: Optional injected symlink capability probe.
        junction_probe: Optional injected junction capability probe.
        should_allow_temporary_probe: Whether injected probes may be executed.

    Returns:
        The observed capabilities, or unavailable capabilities by default.

    """
    if not should_allow_temporary_probe:
        return LinkCapabilities(False, False)
    if symlink_probe is None or junction_probe is None:
        return LinkCapabilities(False, False)
    return LinkCapabilities(
        symlink_probe(),
        junction_probe(),
    )


def _select_kind(spec: LinkSpec, capabilities: LinkCapabilities) -> tuple[LinkKind, str]:
    classification = spec.classification or ("byte_compatible" if spec.is_byte_compatible else "source_only")
    if classification == "source_only":
        return _WatcherConfiguration.materialize_link_kind, "converted asset requires materializer"
    if classification == "unsupported":
        return _WatcherConfiguration.materialize_link_kind, "unsupported asset cannot be linked"
    if spec.should_activate_hook or spec.should_activate_script:
        return _WatcherConfiguration.copy_link_kind, "activation is prohibited"
    if spec.requested_kind == _WatcherConfiguration.junction_link_kind and capabilities.junction:
        return _WatcherConfiguration.junction_link_kind, "requested capability available"
    if spec.requested_kind in (_WatcherConfiguration.junction_link_kind, _WatcherConfiguration.symlink_link_kind) and capabilities.symlink:
        return _WatcherConfiguration.symlink_link_kind, "requested capability unavailable; symlink available"
    return _WatcherConfiguration.copy_link_kind, "link capability unavailable"


def _validate_source_path(source_root: Path, source_name: str) -> Path:
    normalized_source = source_name.replace("\\", "/")
    if Path(normalized_source).is_absolute():
        raise ValueError("rooted path is not allowed")
    return validate_target_path(source_root, source_name)


def _validate_source_root(source_root: Path) -> Path:
    """Reject link-like roots and return the canonical source root."""
    expanded_root = source_root.expanduser()
    if expanded_root.is_symlink() or (
        expanded_root.exists() and _is_reparse_point(expanded_root)
    ):
        raise ValueError("source_root_path cannot be a symlink or reparse point")
    return expanded_root.resolve()


def _validate_publication_source(source_path: Path) -> None:
    if source_path.is_symlink():
        raise ValueError("publication source cannot be a symlink or reparse point")
    if not source_path.exists():
        raise ValueError("publication source does not exist")
    if _is_reparse_point(source_path):
        raise ValueError("publication source cannot be a symlink or reparse point")
    if not source_path.is_dir():
        return
    for each_path in source_path.rglob("*"):
        if each_path.is_symlink() or _is_reparse_point(each_path):
            raise ValueError("publication source tree contains a symlink or reparse point")


def build_link_plan(
    all_specs: Iterable[LinkSpec],
    source_root: Path,
    target_root: Path,
    capabilities: LinkCapabilities | None = None,
    should_apply: bool = False,
    should_allow_links: bool = False,
    should_allow_activation: bool = False,
    symlink_probe: Callable[[], bool] | None = None,
    junction_probe: Callable[[], bool] | None = None,
    should_allow_temporary_probe: bool = False,
) -> LinkPlan:
    """Build a relative-path-only plan without changing the filesystem.

    Args:
        all_specs: Link specifications to classify.
        source_root: Source assets are read beneath this source_root_path.
        target_root: Root receiving managed targets.
        capabilities: Optional precomputed link capabilities.
        should_apply: Whether eligible decisions may be authorized.
        should_allow_links: Whether link publication is authorized.
        should_allow_activation: Whether hook or script activation is authorized.
        symlink_probe: Optional injected symlink capability probe.
        junction_probe: Optional injected junction capability probe.
        should_allow_temporary_probe: Whether injected probes may be executed.

    Returns:
        A plan containing decisions and validation errors.

    Raises:
        ValueError: If a source path is rooted.
    """
    plan = LinkPlan(is_dry_run=not should_apply)
    try:
        source_base = _validate_source_root(source_root)
    except ValueError as error:
        plan.errors.append(str(error))
        return plan
    target_base = target_root.expanduser().resolve()
    if source_base == target_base or source_base in target_base.parents or target_base in source_base.parents:
        plan.errors.append("source and target roots overlap")
        return plan
    available = capabilities or probe_link_capabilities(
        symlink_probe=symlink_probe,
        junction_probe=junction_probe,
        should_allow_temporary_probe=should_allow_temporary_probe,
    )
    all_seen_targets: set[str] = set()
    for each_spec in all_specs:
        source_name = each_spec.source
        try:
            _validate_source_path(source_base, source_name)
        except ValueError as error:
            if Path(source_name.replace("\\", "/")).is_absolute():
                raise
            plan.errors.append(str(error))
            continue
        try:
            target_name = each_spec.target
            target_path = validate_target_path(target_base, target_name)
            target_key = target_path.as_posix().casefold()
            if target_key in all_seen_targets or target_path.exists() or target_path.is_symlink():
                raise ValueError("unmanaged target collision")
            all_seen_targets.add(target_key)
            selected_kind, reason = _select_kind(each_spec, available)
            is_linkable = (each_spec.classification or ("byte_compatible" if each_spec.is_byte_compatible else "source_only")) == "byte_compatible"
            can_apply = is_linkable and should_apply and should_allow_links and (should_allow_activation or not (each_spec.should_activate_hook or each_spec.should_activate_script))
            plan.decisions.append(LinkDecision(source_name, target_name, selected_kind, "apply" if can_apply else "report", reason))
        except (OSError, ValueError, MaterializerError) as error:
            plan.errors.append(str(error))
    return plan


def _apply_decision(
    decision: LinkDecision,
    source_root: Path,
    target_root: Path,
    copier: Callable[[Path, Path], None],
    symlink_creator: Callable[[Path, Path, bool], None],
    junction_creator: Callable[[Path, Path], None],
) -> None:
    source_path = _validate_source_path(source_root, decision.source)
    target_path = validate_target_path(target_root, decision.target)
    if decision.kind == "symlink":
        symlink_creator(source_path, target_path, source_path.is_dir())
        return
    if decision.kind == "junction":
        junction_creator(source_path, target_path)
        return
    copier(source_path, target_path)


def _report_unsupported_junction(source_path: Path, target_path: Path) -> None:
    raise RuntimeError("Windows junction creation is unsupported without an injected junction creator")


def _is_reparse_point(file_path: Path) -> bool:
    file_stat = file_path.stat(follow_symlinks=False)
    return bool(
        getattr(file_stat, "st_file_attributes", 0)
        & _WatcherConfiguration.reparse_point_attribute
    )


def _validate_copy_source(source_path: Path) -> None:
    if source_path.is_symlink() or _is_reparse_point(source_path):
        raise ValueError("copy source cannot be a symlink or reparse point")
    if source_path.is_file():
        return
    if not source_path.is_dir():
        raise ValueError("copy source must be a regular file or directory")
    for each_path in source_path.rglob("*"):
        if each_path.is_symlink() or _is_reparse_point(each_path):
            raise ValueError("copy source tree contains a symlink or reparse point")
        if not each_path.is_file() and not each_path.is_dir():
            raise ValueError("copy source tree contains a non-regular entry")


def _verify_copy(source_path: Path, target_path: Path) -> bool:
    if source_path.is_file():
        return target_path.is_file() and filecmp.cmp(source_path, target_path, shallow=False)
    if not target_path.is_dir():
        return False
    all_source_files = {each_path.relative_to(source_path) for each_path in source_path.rglob("*") if each_path.is_file()}
    all_target_files = {each_path.relative_to(target_path) for each_path in target_path.rglob("*") if each_path.is_file()}
    return all_source_files == all_target_files and all(
        filecmp.cmp(source_path / each_file, target_path / each_file, shallow=False)
        for each_file in all_source_files
    )


def _copy_asset(source_path: Path, target_path: Path) -> None:
    _validate_copy_source(source_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists() or target_path.is_symlink():
        raise FileExistsError(target_path)
    with tempfile.TemporaryDirectory(dir=target_path.parent) as staging_directory:
        staging_path = Path(staging_directory) / target_path.name
        if source_path.is_file():
            shutil.copy2(source_path, staging_path)
        else:
            shutil.copytree(source_path, staging_path, symlinks=False)
        if not _verify_copy(source_path, staging_path):
            raise OSError("copied asset failed content verification")
        os.rename(staging_path, target_path)


def publish_link_plan(
    plan: LinkPlan,
    source_root: Path,
    target_root: Path,
    copier: Callable[[Path, Path], None] | None = None,
    symlink_creator: Callable[[Path, Path, bool], None] | None = None,
    junction_creator: Callable[[Path, Path], None] | None = None,
    materializer: Callable[[], object] | None = None,
) -> LinkReport:
    """Publish explicitly authorized decisions and report failures safely.

    Args:
        plan: Decisions produced by ``build_link_plan``.
        source_root: Source assets are read beneath this source_root_path.
        target_root: Root receiving managed targets.
        copier: Optional injected copy operation.
        symlink_creator: Optional injected symlink operation.
        junction_creator: Optional injected junction operation.
        materializer: Optional callback for materialization decisions.

    Returns:
        A report of applied, skipped, and failed decisions.

    Raises:
        ValueError: If a decision contains an unsafe rooted path.
    """
    report = LinkReport(list(plan.decisions), errors=list(plan.errors), is_reconcile_required=bool(plan.errors))
    try:
        source_base = _validate_source_root(source_root)
    except ValueError as error:
        report.errors.append(str(error))
        report.is_reconcile_required = True
        return report
    copy_asset = copier or _copy_asset
    create_symlink = symlink_creator or os.symlink
    create_junction = junction_creator or _report_unsupported_junction
    for each_decision in plan.decisions:
        if each_decision.action != "apply":
            report.skipped += 1
            continue
        try:
            source_path = _validate_source_path(source_base, each_decision.source)
            _validate_publication_source(source_path)
            if each_decision.kind == _WatcherConfiguration.materialize_link_kind:
                if materializer is None:
                    raise RuntimeError("materializer callback is required")
                materializer()
            else:
                _apply_decision(each_decision, source_base, target_root, copy_asset, create_symlink, create_junction)
            report.applied += 1
        except (OSError, RuntimeError, ValueError) as error:
            report.errors.append(str(error))
            report.is_reconcile_required = True
            report.reconcile_reasons.append(type(error).__name__)
            report.reconcile_paths.append(each_decision.target)
    return report


class DebouncedReconciler:
    """Coalesce scoped watcher events and serialize reconciliation callbacks.

    The reconciler accepts events from five configured source roots, suppresses
    self-generated events first, and adds sorted unsafe-event details to reports.
    """

    default_debounce_seconds = 0.25

    def __init__(
        self,
        reconcile: Callable[[], object],
        debounce_seconds: float | None = None,
        all_configured_roots: Iterable[str] | None = None,
    ) -> None:
        self._reconcile = reconcile
        self._debounce_seconds = (
            debounce_seconds
            if debounce_seconds is not None
            else self.default_debounce_seconds
        )
        self._lock = threading.Lock()
        self._pending = False
        self._last_event = 0.0
        self._running = False
        self._stopped = False
        self._reconcile_reasons: list[str] = []
        self._reconcile_paths: list[str] = []
        self._configured_roots = self._normalize_configured_roots(
            all_configured_roots or _WatcherConfiguration.all_configured_root_names
        )

    @staticmethod
    def _normalize_configured_roots(all_configured_roots: Iterable[str]) -> frozenset[str]:
        normalized_roots: set[str] = set()
        for each_root in all_configured_roots:
            normalized_roots.add(each_root.casefold())
            normalized_roots.add(Path(each_root).expanduser().resolve().as_posix().casefold())
        return frozenset(normalized_roots)

    def start(self) -> None:
        with self._lock:
            self._stopped = False

    def stop(self) -> None:
        with self._lock:
            self._stopped = True
            self._pending = False
            self._reconcile_reasons.clear()
            self._reconcile_paths.clear()

    def notify(self, event: WatchEvent) -> None:
        """Record a scoped filesystem event for later reconciliation.

        Args:
            event: Filesystem event to coalesce or classify.
        """
        if event.is_self_event:
            return
        source_root_name = event.source_root.casefold()
        source_root_path = Path(event.source_root).expanduser().resolve().as_posix().casefold()
        if source_root_name not in self._configured_roots and source_root_path not in self._configured_roots:
            return
        if event.kind in _WatcherConfiguration.all_unsafe_event_kinds:
            with self._lock:
                if not self._stopped:
                    self._pending = True
                    self._reconcile_reasons.append(event.kind)
                    self._reconcile_paths.append(event.path or event.source_root)
                    self._last_event = time.monotonic()
            return
        with self._lock:
            if not self._stopped:
                self._pending = True
                self._last_event = time.monotonic()

    def flush(self, should_force: bool = False) -> object | None:
        """Run the pending reconciliation when debounce and state allow it.

        Args:
            should_force: Whether to bypass the debounce interval.

        Returns:
            The reconciliation report, or ``None`` when no run is eligible.
        """
        with self._lock:
            if self._stopped or not self._pending or self._running or (not should_force and time.monotonic() - self._last_event < self._debounce_seconds):
                return None
            self._pending = False
            self._running = True
        try:
            reconciliation_report = self._reconcile()
            return self._report_with_event_details(reconciliation_report)
        except (OSError, RuntimeError, ValueError) as error:
            return self._report_with_event_details({"reconcile_required": True, "errors": [str(error)]})
        finally:
            with self._lock:
                self._running = False

    def _report_with_event_details(self, reconciliation_report: object) -> object:
        with self._lock:
            event_reasons = sorted(self._reconcile_reasons)
            event_paths = sorted(self._reconcile_paths)
            self._reconcile_reasons.clear()
            self._reconcile_paths.clear()
        if isinstance(reconciliation_report, dict):
            reconciliation_report = dict(reconciliation_report)
            if event_reasons:
                reconciliation_report["reconcile_required"] = True
            reconciliation_report["reconcile_reasons"] = event_reasons
            reconciliation_report["reconcile_paths"] = event_paths
            return reconciliation_report
        if not event_reasons:
            return reconciliation_report
        return {"reconciliation": reconciliation_report, "reconcile_required": True, "reconcile_reasons": event_reasons, "reconcile_paths": event_paths}


def reconcile_materialized_agents(materializer_config: MaterializerConfig) -> object:
    """Run the materializer's complete deterministic public reconciliation.

    Args:
        materializer_config: Configuration for the materialized compatibility files.

    Returns:
        The materializer publication report.
    """
    planned_files, publication_report = build_plan(materializer_config)
    return publish_plan(materializer_config, planned_files, publication_report)
