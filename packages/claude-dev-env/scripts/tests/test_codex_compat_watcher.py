from pathlib import Path
from threading import Event, Lock, Thread

import pytest

from codex_compat_watcher import (
    DebouncedReconciler,
    LinkCapabilities,
    LinkDecision,
    LinkSpec,
    LinkPlan,
    LinkReport,
    WatchEvent,
    build_link_plan,
    publish_link_plan,
    probe_link_capabilities,
)


def test_junction_capability_without_creator_fails_truthfully(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "source").write_text("source", encoding="utf-8")
    plan = build_link_plan(
        [LinkSpec("source", "target", requested_kind="junction")],
        source_root,
        tmp_path / "target",
        LinkCapabilities(False, True),
        should_apply=True,
        should_allow_links=True,
    )

    report = publish_link_plan(plan, source_root, tmp_path / "target")

    assert report.applied == 0
    assert report.is_reconcile_required
    assert "unsupported" in report.errors[0]
    assert not (tmp_path / "target").exists()


def test_link_report_preserves_reconcile_required_read_write_api() -> None:
    report = LinkReport()

    assert report.reconcile_required is False
    report.reconcile_required = True
    assert report.is_reconcile_required is True


def test_unavailable_junction_capability_falls_back_to_copy(tmp_path: Path) -> None:
    plan = build_link_plan(
        [LinkSpec("source", "target", requested_kind="junction")],
        tmp_path / "source",
        tmp_path / "target",
        LinkCapabilities(False, False),
    )

    assert [(decision.kind, decision.reason) for decision in plan.decisions] == [
        ("copy", "link capability unavailable")
    ]


def test_default_copier_publishes_file_and_directory(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    source_root.mkdir()
    (source_root / "file.txt").write_text("file", encoding="utf-8")
    (source_root / "tree").mkdir()
    (source_root / "tree" / "nested.txt").write_text("nested", encoding="utf-8")
    plan = build_link_plan(
        [LinkSpec("file.txt", "file.txt"), LinkSpec("tree", "tree")],
        source_root,
        target_root,
        LinkCapabilities(False, False),
        should_apply=True,
        should_allow_links=True,
    )

    report = publish_link_plan(plan, source_root, target_root)

    assert report.applied == 2
    assert (target_root / "file.txt").read_text(encoding="utf-8") == "file"
    assert (target_root / "tree" / "nested.txt").read_text(encoding="utf-8") == "nested"


def test_default_copier_rejects_reparse_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "file.txt").write_text("file", encoding="utf-8")
    plan = build_link_plan(
        [LinkSpec("file.txt", "file.txt")],
        source_root,
        tmp_path / "target",
        LinkCapabilities(False, False),
        should_apply=True,
        should_allow_links=True,
    )
    monkeypatch.setattr("codex_compat_watcher._is_reparse_point", lambda source_path: True)

    report = publish_link_plan(plan, source_root, tmp_path / "target")

    assert report.applied == 0
    assert report.is_reconcile_required
    assert not (tmp_path / "target" / "file.txt").exists()


def test_link_publication_rejects_source_symlink_without_callback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_path = source_root / "linked.txt"
    source_path.write_text("source", encoding="utf-8")
    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda each_path: each_path == source_path or original_is_symlink(each_path),
    )
    publication_calls: list[tuple[Path, Path]] = []
    plan = LinkPlan([LinkDecision("linked.txt", "linked.txt", "symlink", "apply", "test")], is_dry_run=False)

    report = publish_link_plan(
        plan,
        source_root,
        tmp_path / "target",
        symlink_creator=lambda source, target, is_directory: publication_calls.append((source, target)),
    )

    assert report.applied == 0
    assert report.is_reconcile_required
    assert publication_calls == []
    assert not (tmp_path / "target").exists()


def test_link_publication_rejects_source_tree_reparse_without_callback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "tree").mkdir()
    nested_path = source_root / "tree" / "nested.txt"
    nested_path.write_text("source", encoding="utf-8")
    monkeypatch.setattr(
        "codex_compat_watcher._is_reparse_point",
        lambda each_path: each_path == nested_path,
    )
    publication_calls: list[tuple[Path, Path]] = []
    plan = LinkPlan([LinkDecision("tree", "tree", "junction", "apply", "test")], is_dry_run=False)

    report = publish_link_plan(
        plan,
        source_root,
        tmp_path / "target",
        junction_creator=lambda source, target: publication_calls.append((source, target)),
    )

    assert report.applied == 0
    assert report.is_reconcile_required
    assert publication_calls == []
    assert not (tmp_path / "target").exists()


def test_link_publication_rejects_symlink_source_root_without_callback(tmp_path: Path) -> None:
    real_source_root = tmp_path / "real-source"
    real_source_root.mkdir()
    (real_source_root / "source.txt").write_text("source", encoding="utf-8")
    linked_source_root = tmp_path / "source"
    try:
        linked_source_root.symlink_to(real_source_root, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlinks unavailable: {error}")
    publication_calls: list[str] = []
    plan = build_link_plan(
        [LinkSpec("source.txt", "target.txt")],
        linked_source_root,
        tmp_path / "target",
        LinkCapabilities(False, False),
        should_apply=True,
        should_allow_links=True,
    )

    report = publish_link_plan(
        plan,
        linked_source_root,
        tmp_path / "target",
        copier=lambda source_path, target_path: publication_calls.append("copy"),
    )

    assert report.applied == 0
    assert report.is_reconcile_required
    assert "source_root_path cannot be a symlink or reparse point" in report.errors
    assert publication_calls == []
    assert not (tmp_path / "target").exists()


@pytest.mark.parametrize("publication_kind", ["copy", "symlink", "junction", "materialize"])
def test_link_publication_rejects_missing_source_without_callback(
    tmp_path: Path, publication_kind: str
) -> None:
    publication_calls: list[str] = []
    plan = LinkPlan(
        [LinkDecision("missing", "target", publication_kind, "apply", "test")],
        is_dry_run=False,
    )

    report = publish_link_plan(
        plan,
        tmp_path / "source",
        tmp_path / "target",
        copier=lambda source_path, target_path: publication_calls.append("copy"),
        symlink_creator=lambda source_path, target_path, is_directory: publication_calls.append(
            "symlink"
        ),
        junction_creator=lambda source_path, target_path: publication_calls.append("junction"),
        materializer=lambda: publication_calls.append("materialize"),
    )

    assert report.applied == 0
    assert report.is_reconcile_required
    assert "publication source does not exist" in report.errors
    assert publication_calls == []
    assert not (tmp_path / "target").exists()


def test_default_copier_reports_copy_failure_without_application(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "file.txt").write_text("file", encoding="utf-8")
    plan = build_link_plan(
        [LinkSpec("file.txt", "file.txt")],
        source_root,
        tmp_path / "target",
        LinkCapabilities(False, False),
        should_apply=True,
        should_allow_links=True,
    )

    def fail_copy(source_path: Path, target_path: Path) -> None:
        raise OSError("copy failed")

    report = publish_link_plan(plan, source_root, tmp_path / "target", copier=fail_copy)

    assert report.applied == 0
    assert report.reconcile_required
    assert "copy failed" in report.errors


def test_default_copier_never_overwrites_unmanaged_target(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    source_root.mkdir()
    target_root.mkdir()
    (source_root / "file.txt").write_text("new", encoding="utf-8")
    (target_root / "file.txt").write_text("existing", encoding="utf-8")
    plan = LinkPlan([LinkDecision("file.txt", "file.txt", "copy", "apply", "test")], is_dry_run=False)

    report = publish_link_plan(plan, source_root, target_root)

    assert report.applied == 0
    assert (target_root / "file.txt").read_text(encoding="utf-8") == "existing"


def test_explicit_materialize_invokes_materializer_once(tmp_path: Path) -> None:
    calls: list[str] = []
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "converted").write_text("source", encoding="utf-8")
    plan = LinkPlan(
        decisions=[
            LinkDecision(
                "converted", "target", "materialize", "apply", "explicit materialization"
            )
        ],
        is_dry_run=False,
    )

    report = publish_link_plan(
        plan,
        source_root,
        tmp_path / "target",
        materializer=lambda: calls.append("materialize"),
    )

    assert report.applied == 1
    assert calls == ["materialize"]


def test_source_only_and_unsupported_never_invoke_materializer(tmp_path: Path) -> None:
    calls: list[str] = []
    plan = build_link_plan(
        [
            LinkSpec("source", "source", classification="source_only"),
            LinkSpec("unsupported", "unsupported", classification="unsupported"),
        ],
        tmp_path / "source",
        tmp_path / "target",
        LinkCapabilities(True, True),
        should_apply=True,
        should_allow_links=True,
        should_allow_activation=True,
    )

    report = publish_link_plan(
        plan,
        tmp_path / "source",
        tmp_path / "target",
        materializer=lambda: calls.append("materialize"),
    )

    assert report.applied == 0
    assert report.skipped == 2
    assert calls == []


def test_capability_fallback_and_classification(tmp_path: Path) -> None:
    plan = build_link_plan(
        [
            LinkSpec("source.txt", "target.txt"),
            LinkSpec("converted.md", "converted.toml", is_byte_compatible=False),
        ],
        tmp_path / "source",
        tmp_path / "target",
        LinkCapabilities(False, False),
    )

    assert [(decision.kind, decision.reason) for decision in plan.decisions] == [
        ("copy", "link capability unavailable"),
        ("materialize", "converted asset requires materializer"),
    ]


def test_source_only_and_unsupported_assets_never_activate_or_link(tmp_path: Path) -> None:
    plan = build_link_plan(
        [
            LinkSpec("source.md", "source.md", classification="source_only"),
            LinkSpec("unsupported.md", "unsupported.md", classification="unsupported"),
        ],
        tmp_path / "source",
        tmp_path / "target",
        LinkCapabilities(True, True),
        should_apply=True,
        should_allow_links=True,
        should_allow_activation=True,
    )

    assert [decision.action for decision in plan.decisions] == ["report", "report"]
    assert publish_link_plan(plan, tmp_path / "source", tmp_path / "target").applied == 0


def test_default_capability_probe_uses_copy_fallback() -> None:
    assert probe_link_capabilities() == LinkCapabilities(False, False)


def test_capability_probe_uses_injected_results_only_when_opted_in() -> None:
    assert probe_link_capabilities(lambda: True, lambda: True) == LinkCapabilities(False, False)
    assert probe_link_capabilities(lambda: True, lambda: True, should_allow_temporary_probe=True) == LinkCapabilities(True, True)


def test_build_link_plan_forwards_optional_capability_probes(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()

    plan = build_link_plan(
        [LinkSpec("source.txt", "target.txt")],
        source_root,
        tmp_path / "target",
        should_allow_temporary_probe=True,
        symlink_probe=lambda: True,
        junction_probe=lambda: True,
    )

    assert plan.decisions[0].kind == "symlink"


def test_dry_run_never_creates_links_or_activates(tmp_path: Path) -> None:
    plan = build_link_plan(
        [LinkSpec("hook.py", "hook.py", should_activate_hook=True)],
        tmp_path / "source",
        tmp_path / "target",
        LinkCapabilities(True, True),
        should_apply=True,
        should_allow_links=False,
        should_allow_activation=False,
    )
    report = publish_link_plan(plan, tmp_path / "source", tmp_path / "target")

    assert report.applied == 0
    assert report.skipped == 1
    assert not (tmp_path / "target" / "hook.py").exists()


def test_link_publication_requires_apply_and_both_permissions(tmp_path: Path) -> None:
    publication_calls: list[tuple[Path, Path]] = []

    def record_publication(source_path: Path, target_path: Path) -> None:
        publication_calls.append((source_path, target_path))

    for should_apply, should_allow_links, should_allow_activation in ((False, True, True), (True, False, True)):
        plan = build_link_plan(
            [LinkSpec("hook.py", "hook.py", should_activate_hook=True)],
            tmp_path / "source",
            tmp_path / "target",
            LinkCapabilities(True, True),
            should_apply=should_apply,
            should_allow_links=should_allow_links,
            should_allow_activation=should_allow_activation,
        )
        publish_link_plan(plan, tmp_path / "source", tmp_path / "target", copier=record_publication)

    assert publication_calls == []


def test_authorized_activation_reaches_injected_link_operation(tmp_path: Path) -> None:
    publication_calls: list[tuple[Path, Path]] = []
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "hook.py").write_text("hook", encoding="utf-8")

    plan = build_link_plan(
        [LinkSpec("hook.py", "hook.py", should_activate_hook=True)],
        source_root,
        tmp_path / "target",
        LinkCapabilities(True, True),
        should_apply=True,
        should_allow_links=True,
        should_allow_activation=True,
    )
    report = publish_link_plan(
        plan,
        source_root,
        tmp_path / "target",
        copier=lambda source_path, target_path: publication_calls.append((source_path, target_path)),
        symlink_creator=lambda source_path, target_path, is_directory: publication_calls.append((source_path, target_path)),
    )

    assert report.applied == 1
    assert len(publication_calls) == 1


def test_path_safety_and_unmanaged_collision(tmp_path: Path) -> None:
    target_root = tmp_path / "target"
    target_root.mkdir()
    (target_root / "existing.txt").write_text("owned by user", encoding="utf-8")
    plan = build_link_plan(
        [LinkSpec("../escape", "escape"), LinkSpec("source", "existing.txt")],
        tmp_path / "source",
        target_root,
        LinkCapabilities(True, False),
    )

    assert len(plan.errors) == 2
    assert all("\\" not in error for error in plan.errors)


def test_debounced_reconciler_coalesces_and_suppresses_self_events() -> None:
    calls: list[str] = []
    reconciler = DebouncedReconciler(lambda: calls.append("run"), debounce_seconds=60.0)

    reconciler.notify(WatchEvent("agents", is_self_event=True))
    assert reconciler.flush(should_force=True) is None
    reconciler.notify(WatchEvent("agents"))
    reconciler.notify(WatchEvent("skills"))
    assert reconciler.flush(should_force=True) is None
    assert calls == ["run"]


def test_each_configured_root_triggers_reconciliation() -> None:
    calls: list[str] = []
    reconciler = DebouncedReconciler(lambda: calls.append("run") or "run")

    for each_source_root in ("agents", "commands", "hooks", "rules", "skills"):
        reconciler.notify(WatchEvent(each_source_root))

    assert reconciler.flush(should_force=True) == "run"
    assert calls == ["run"]


def test_self_event_is_ignored_before_unsafe_event_handling() -> None:
    reconciler = DebouncedReconciler(lambda: "run")

    reconciler.notify(WatchEvent("hooks", kind="overflow", is_self_event=True, path="hooks/events"))

    assert reconciler.flush(should_force=True) is None


def test_flush_serializes_reconciliation_callbacks() -> None:
    callback_started = Event()
    release_callback = Event()
    callback_lock = Lock()
    active_callbacks = 0
    maximum_active_callbacks = 0

    def reconcile() -> str:
        nonlocal active_callbacks, maximum_active_callbacks
        with callback_lock:
            active_callbacks += 1
            maximum_active_callbacks = max(maximum_active_callbacks, active_callbacks)
        callback_started.set()
        release_callback.wait()
        with callback_lock:
            active_callbacks -= 1
        return "run"

    reconciler = DebouncedReconciler(reconcile)
    reconciler.notify(WatchEvent("hooks"))
    first_flush = Thread(target=reconciler.flush, kwargs={"should_force": True})
    first_flush.start()
    assert callback_started.wait()

    reconciler.notify(WatchEvent("rules"))
    assert reconciler.flush(should_force=True) is None
    release_callback.set()
    first_flush.join()

    assert reconciler.flush(should_force=True) == "run"
    assert maximum_active_callbacks == 1


def test_reconciler_failure_requests_reconciliation() -> None:
    def fail() -> None:
        raise OSError("inaccessible")

    reconciler = DebouncedReconciler(fail)
    reconciler.notify(WatchEvent("hooks"))

    assert reconciler.flush(should_force=True) == {
        "reconcile_required": True,
        "errors": ["inaccessible"],
        "reconcile_reasons": [],
        "reconcile_paths": [],
    }


def test_unsafe_event_is_reconciled_with_reason_and_path() -> None:
    reconciler = DebouncedReconciler(lambda: {"written": 1})

    reconciler.notify(WatchEvent("hooks", kind="overflow", path="hooks/events"))

    assert reconciler.flush(should_force=True) == {
        "written": 1,
        "reconcile_required": True,
        "reconcile_reasons": ["overflow"],
        "reconcile_paths": ["hooks/events"],
    }


def test_out_of_scope_unsafe_events_are_ignored() -> None:
    reconciler = DebouncedReconciler(lambda: {"written": 1})

    reconciler.notify(WatchEvent("private", kind="overflow", path="private/events"))

    assert reconciler.flush(should_force=True) is None


def test_unsafe_event_details_are_sorted() -> None:
    reconciler = DebouncedReconciler(lambda: {"written": 1})
    reconciler.notify(WatchEvent("hooks", kind="unknown", path="z"))
    reconciler.notify(WatchEvent("agents", kind="overflow", path="a"))

    assert reconciler.flush(should_force=True) == {
        "written": 1,
        "reconcile_required": True,
        "reconcile_reasons": ["overflow", "unknown"],
        "reconcile_paths": ["a", "z"],
    }


def test_materialized_reconciliation_delegates_to_materializer(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_build_plan(config: object) -> tuple[list[object], object]:
        calls.append("build")
        return [], "report"

    def fake_publish_plan(config: object, planned_files: list[object], report: object) -> object:
        calls.append("publish")
        return report

    monkeypatch.setattr("codex_compat_watcher.build_plan", fake_build_plan)
    monkeypatch.setattr("codex_compat_watcher.publish_plan", fake_publish_plan)

    assert __import__("codex_compat_watcher").reconcile_materialized_agents(object()) == "report"
    assert calls == ["build", "publish"]


def test_private_paths_are_rejected(tmp_path: Path) -> None:
    safe_plan = build_link_plan(
        [LinkSpec("safe/source", "safe")],
        tmp_path / "source",
        tmp_path / "target",
    )
    assert len(safe_plan.decisions) == 1

    with pytest.raises(ValueError):
        build_link_plan(
            [LinkSpec(str(tmp_path / "private" / "secret"), "safe")],
            tmp_path / "source",
            tmp_path / "target",
        )
