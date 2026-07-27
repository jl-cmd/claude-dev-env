import json
from pathlib import Path
import sys
import tomllib

import pytest

module_directory = str(Path(__file__).parents[1])
if module_directory not in sys.path:
    sys.path.insert(0, module_directory)

import codex_compat_materializer as materializer
from codex_compat_materializer import (
    MaterializationReport,
    MaterializerConfig,
    MaterializerError,
    PlannedFile,
    atomic_write,
    build_plan,
    convert_agent,
    content_to_bytes,
    hash_content,
    load_manifest,
    parse_frontmatter,
    publish_plan,
    save_manifest,
    validate_target_path,
)


def test_conversion_escapes_toml_content() -> None:
    agent = parse_frontmatter(Path("agent.md"), '---\nname: sample\ndescription: "say \\"hi\\""\ntools: ["Read", "Write"]\n---\n', "agent.md")
    converted = convert_agent(agent)
    assert 'description = "say \\"hi\\""' in converted
    assert tomllib.loads(converted)["name"] == "sample"


def test_malformed_and_unsupported_frontmatter() -> None:
    with pytest.raises(MaterializerError):
        parse_frontmatter(Path("bad.md"), "---\nname: x\n", "bad.md")
    agent = parse_frontmatter(Path("ok.md"), "---\nname: x\ndescription: y\nmodel: sonnet\ncolor: blue\n---\n", "ok.md")
    assert agent.unsupported == ("color", "model")


@pytest.mark.parametrize(
    "source_text",
    [
        "---\nname: x\ndescription: y\nunknown: z\n---\n",
        "---\nname: x\ndescription: 'unterminated\n---\n",
        "---\nname: x\ndescription: y\ntools: [Read, 'Write]\n---\n",
        "---\nname: x\nname: y\ndescription: z\n---\n",
        "---\nname: x\ndescription: y\n---\nbody\n---\n",
    ],
)
def test_frontmatter_rejects_invalid_syntax(source_text: str) -> None:
    with pytest.raises(MaterializerError):
        parse_frontmatter(Path("bad.md"), source_text, "bad.md")


def test_frontmatter_preserves_commas_inside_quoted_list_entries() -> None:
    agent = parse_frontmatter(
        Path("agent.md"),
        '---\nname: x\ndescription: y\ntools: ["Read,Only", Write]\n---\n',
        "agent.md",
    )
    assert agent.tools == ("Read,Only", "Write")


def test_discover_agents_returns_sorted_parsed_agents(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "zulu.md").write_text("---\nname: Zulu\ndescription: z\n---\n", encoding="utf-8")
    (source / "alpha.md").write_text("---\nname: Alpha\ndescription: a\n---\n", encoding="utf-8")

    agents = materializer.discover_agents(MaterializerConfig(source, tmp_path / "target"))

    assert [agent.name for agent in agents] == ["Alpha", "Zulu"]


def test_content_to_bytes_preserves_bytes_and_encodes_text() -> None:
    assert content_to_bytes(b"payload") == b"payload"
    assert content_to_bytes("payload") == b"payload"


def test_save_manifest_round_trips_manifest_content(tmp_path: Path) -> None:
    manifest_path = tmp_path / "target" / "manifest.json"
    manifest = {"version": 1, "files": {"agent.toml": {"hash": "abc"}}}

    save_manifest(manifest_path, manifest)

    assert load_manifest(manifest_path) == manifest


def test_create_argument_parser_reads_roots_and_apply_flag() -> None:
    arguments = materializer.create_argument_parser().parse_args(["source", "target", "--apply"])

    assert arguments.source_root == Path("source")
    assert arguments.target_root == Path("target")
    assert arguments.should_apply is True


def test_validation_rejects_overlap_and_unsafe_paths(tmp_path: Path) -> None:
    with pytest.raises(MaterializerError):
        MaterializerConfig(tmp_path, tmp_path / "target")
    config = MaterializerConfig(tmp_path / "source", tmp_path / "target")
    for name in ("../escape", "C:/escape", "\\\\server\\share", "/rooted"):
        with pytest.raises(MaterializerError):
            validate_target_path(config.target_root, name)


def test_validation_rejects_reparse_point_from_portable_attribute_seam(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_root = tmp_path / "target"
    target_root.mkdir()
    monkeypatch.setattr(materializer, "_is_reparse_point", lambda path: path == target_root)

    with pytest.raises(MaterializerError, match="reparse"):
        validate_target_path(target_root, "agent.toml")


def test_private_source_identity_is_rejected_before_manifest_serialization(
    tmp_path: Path,
) -> None:
    config = MaterializerConfig(tmp_path / "source", tmp_path / "target")
    with pytest.raises(MaterializerError):
        build_plan(config, [
            parse_frontmatter(Path("agent.md"), "---\nname: x\ndescription: y\n---\n", "C:/private.md")
        ])


def test_case_folded_target_collisions_include_existing_and_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (target / "LUNA.toml").write_text("unmanaged", encoding="utf-8")
    with pytest.raises(MaterializerError):
        build_plan(MaterializerConfig(source, target), [
            parse_frontmatter(Path("a.md"), "---\nname: Luna\ndescription: y\n---\n", "a.md")
        ])


def test_manifest_target_collision_is_rejected(tmp_path: Path) -> None:
    config = MaterializerConfig(tmp_path / "source", tmp_path / "target", should_apply=True)
    planned = [PlannedFile("a.md", "Luna.toml", "managed", "hash")]
    atomic_write(config.manifest_path, '{"files": {"luna.TOML": {}}, "version": 1}\n')
    with pytest.raises(MaterializerError):
        publish_plan(config, planned)


def test_first_run_manifest_target_collision_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    config = MaterializerConfig(source, target, should_apply=True)
    planned = [PlannedFile("a.md", config.manifest_path.name, "managed", "hash")]

    with pytest.raises(MaterializerError, match="compatibility manifest"):
        publish_plan(config, planned)

    assert not config.manifest_path.exists()
    assert not config.target_root.exists()


def test_publish_rejects_planned_case_fold_collision(tmp_path: Path) -> None:
    config = MaterializerConfig(tmp_path / "source", tmp_path / "target", should_apply=True)
    planned = [
        PlannedFile("a.md", "Luna.toml", "first", hash_content("first")),
        PlannedFile("b.md", "luna.toml", "second", hash_content("second")),
    ]
    with pytest.raises(MaterializerError, match="case-fold collision"):
        publish_plan(config, planned)


def test_dry_run_is_non_mutating_and_writes_are_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    (source / "agent.md").write_text("---\nname: Luna\ndescription: Light\n---\n", encoding="utf-8")
    dry_config = MaterializerConfig(source, target)
    planned, report = build_plan(dry_config)
    publish_plan(dry_config, planned, report)
    assert not target.exists()
    apply_config = MaterializerConfig(source, target, should_apply=True)
    planned, report = build_plan(apply_config)
    publish_plan(apply_config, planned, report)
    first = (target / "Luna.toml").read_text(encoding="utf-8")
    first_manifest = apply_config.manifest_path.read_bytes()
    planned, report = build_plan(apply_config)
    second_report = publish_plan(apply_config, planned, report)
    assert (target / "Luna.toml").read_text(encoding="utf-8") == first
    assert apply_config.manifest_path.read_bytes() == first_manifest
    assert second_report.written == 0
    assert second_report.deleted == 0
    assert second_report.errors == 0
    assert second_report.details["unchanged"] == ["Luna.toml"]


def test_atomic_write_and_unmanaged_collision_are_safe(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    existing = target / "Luna.toml"
    existing.write_text("unmanaged", encoding="utf-8")
    planned = PlannedFile("agent.md", "Luna.toml", "managed", "hash")
    report = MaterializationReport()
    publish_plan(MaterializerConfig(tmp_path / "source", target, should_apply=True), [planned], report)
    assert existing.read_text(encoding="utf-8") == "unmanaged"
    atomic_write(existing, "updated")
    assert existing.read_text(encoding="utf-8") == "updated"


def test_generic_publication_accepts_non_toml_managed_bytes(tmp_path: Path) -> None:
    config = MaterializerConfig(tmp_path / "source", tmp_path / "target", should_apply=True)
    managed_content = b"managed binary payload\x00"
    planned = [PlannedFile("watcher", "watcher.bin", managed_content, hash_content(managed_content))]

    report = publish_plan(config, planned)

    assert report.written == 1
    assert (config.target_root / "watcher.bin").read_bytes() == managed_content


def test_atomic_write_failure_preserves_previous_target_bytes(tmp_path: Path) -> None:
    target = tmp_path / "Luna.toml"
    target.write_bytes(b"previous bytes")

    def fail_before_replace(target_name: str) -> None:
        assert target_name == str(target)
        raise RuntimeError("injected atomic write failure")

    with pytest.raises(RuntimeError, match="injected"):
        atomic_write(target, "replacement", fail_before_replace)

    assert target.read_bytes() == b"previous bytes"


def test_manifest_is_published_last_and_previous_manifest_survives_failure(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    config = MaterializerConfig(source, target, should_apply=True)
    manifest = config.manifest_path
    manifest.parent.mkdir()
    atomic_write(manifest, '{"files": {}, "version": 1}\n')
    planned = [PlannedFile("agent.md", "Luna.toml", "managed", "hash")]
    with pytest.raises(RuntimeError):
        publish_plan(config, planned, failure_injector=lambda _: (_ for _ in ()).throw(RuntimeError("stop")))
    assert load_manifest(manifest)["files"] == {}
    assert not (target / "Luna.toml").exists()


def test_partial_publication_rolls_back_all_files_and_reports_incomplete_generation(
    tmp_path: Path,
) -> None:
    config = MaterializerConfig(tmp_path / "source", tmp_path / "target", should_apply=True)
    planned = [
        PlannedFile("a.md", "Luna.toml", "luna", hash_content("luna")),
        PlannedFile("b.md", "Nova.toml", "nova", hash_content("nova")),
    ]
    call_count = 0

    def fail_on_second_write(target_name: str) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("second write failed")

    with pytest.raises(RuntimeError, match="second write failed"):
        publish_plan(config, planned, failure_injector=fail_on_second_write)

    assert not (config.target_root / "Luna.toml").exists()
    assert not (config.target_root / "Nova.toml").exists()


def test_rollback_failure_requires_reconcile_and_has_deterministic_details(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = MaterializerConfig(tmp_path / "source", tmp_path / "target", should_apply=True)
    report = MaterializationReport()
    planned = [
        PlannedFile("a.md", "Luna.toml", "luna", hash_content("luna")),
        PlannedFile("b.md", "Nova.toml", "nova", hash_content("nova")),
    ]

    def fail_later_publication(target_name: str) -> None:
        if target_name.endswith("Nova.toml"):
            raise RuntimeError("later publication failed")

    original_unlink = Path.unlink

    def fail_rollback(target_path: Path, missing_ok: bool = False) -> None:
        if target_path == config.target_root / "Luna.toml":
            raise OSError("rollback")
        original_unlink(target_path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_rollback)
    with pytest.raises(RuntimeError, match="later publication failed"):
        publish_plan(config, planned, report, failure_injector=fail_later_publication)

    assert report.incomplete_generation is True
    assert report.reconcile_required is True
    assert report.details["errors"] == [
        "rollback failed: " + str(config.target_root / "Luna.toml"),
        "incomplete_generation/reconcile_required",
    ]


def test_modified_and_deleted_managed_outputs_are_preserved_or_deleted(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    config = MaterializerConfig(source, target, should_apply=True)
    first = [PlannedFile("a.md", "Luna.toml", "managed", hash_content("managed"))]
    publish_plan(config, first)
    (target / "Luna.toml").write_text("changed", encoding="utf-8")
    second = [PlannedFile("a.md", "Nova.toml", "new", hash_content("new"))]
    report = publish_plan(config, second)
    assert (target / "Luna.toml").read_text(encoding="utf-8") == "changed"
    assert report.preserved == 1
    assert report.modified_managed == 1
    assert report.details["modified_managed"] == ["Luna.toml"]
    assert report.details["stale_managed"] == []


def test_report_contains_deterministic_category_details_and_error_count(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    config = MaterializerConfig(tmp_path / "source", target, should_apply=True)
    managed_content = "managed"
    initial = [PlannedFile("a.md", "Luna.toml", managed_content, hash_content(managed_content))]
    publish_plan(config, initial)
    modified_report = publish_plan(
        config, [PlannedFile("a.md", "Luna.toml", "new", hash_content("new"))]
    )
    assert modified_report.details["modified_managed"] == ["Luna.toml"]
    assert modified_report.conflicted == 1
    assert modified_report.details["conflicted"] == ["Luna.toml"]

    (target / "Luna.toml").write_text("changed", encoding="utf-8")
    atomic_write(config.manifest_path, json.dumps({"version": 1, "files": {
        "Luna.toml": {"hash": hash_content(managed_content)}
    }}))
    stale_report = publish_plan(config, [])
    assert stale_report.details["modified_managed"] == ["Luna.toml"]
    assert stale_report.details["stale_managed"] == []

    (target / "Luna.toml").write_text(managed_content, encoding="utf-8")
    atomic_write(config.manifest_path, json.dumps({"version": 1, "files": {
        "Luna.toml": {"hash": hash_content(managed_content)}
    }}))
    deleted_report = publish_plan(config, [])
    assert deleted_report.details["deleted"] == ["Luna.toml"]

    collision_target = target / "Nova.toml"
    collision_target.write_text("unmanaged", encoding="utf-8")
    collision_report = publish_plan(
        config, [PlannedFile("b.md", "Nova.toml", "new", hash_content("new"))]
    )
    assert collision_report.details["unmanaged_collision"] == ["Nova.toml"]
    assert collision_report.conflicted == 1
    assert collision_report.details["conflicted"] == ["Nova.toml"]

    manifest = {"version": 1, "files": {"Missing.toml": {"hash": hash_content("missing")}}}
    atomic_write(config.manifest_path, json.dumps(manifest))
    error_report = publish_plan(config, [])
    assert error_report.errors == 1
    assert error_report.error_details == ["missing managed path: Missing.toml"]


def test_cli_reports_unmanaged_collision_as_json_without_private_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (target / "Luna.toml").write_text("unmanaged", encoding="utf-8")
    planned = [PlannedFile("a.md", "Luna.toml", "new", hash_content("new"))]
    monkeypatch.setattr(materializer, "build_plan", lambda _, all_agents=None: (planned, MaterializationReport()))

    exit_code = materializer.main([str(source), str(target), "--apply"])

    printed_report = capsys.readouterr().out
    report = json.loads(printed_report)
    assert exit_code != 0
    assert report["written"] == 0
    assert report["unmanaged_collision"] == 1
    assert report["errors"] == 0
    assert str(tmp_path) not in printed_report


def test_cli_reports_overlapping_roots_as_complete_redacted_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source_root = tmp_path / "private-source"
    target_root = source_root / "private-target"

    exit_code = materializer.main([str(source_root), str(target_root)])

    printed_lines = capsys.readouterr().out.splitlines()
    assert len(printed_lines) == 1
    report = json.loads(printed_lines[0])
    expected_fields = {
        *materializer.REPORT_CATEGORIES,
        "details",
        "dry_run",
        "error_details",
        "incomplete_generation",
        "reconcile_required",
    }
    assert set(report) == expected_fields
    assert exit_code != 0
    assert report["errors"] == 1
    assert report["dry_run"] is True
    assert str(tmp_path) not in printed_lines[0]


def test_cli_reports_argument_errors_as_complete_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = materializer.main(["only-source"])

    report = json.loads(capsys.readouterr().out)

    assert exit_code != 0
    assert report["errors"] == 1
    assert report["dry_run"] is True
    assert len(report["error_details"]) == 1
    assert set(report) == {
        *materializer.REPORT_CATEGORIES,
        "details",
        "dry_run",
        "error_details",
        "incomplete_generation",
        "reconcile_required",
    }


def test_cli_reports_publication_and_rollback_failure_as_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    planned = [PlannedFile("a.md", "Luna.toml", "luna", hash_content("luna"))]

    def fail_publication(*args: object, **kwargs: object) -> MaterializationReport:
        report = args[2] if len(args) > 2 else kwargs.get("report")
        assert isinstance(report, MaterializationReport)
        report.reconcile_required = True
        report.incomplete_generation = True
        report.add_error(f"rollback failed: {target / 'Luna.toml'}")
        raise RuntimeError("publication failed")

    monkeypatch.setattr(materializer, "build_plan", lambda _, all_agents=None: (planned, MaterializationReport()))
    monkeypatch.setattr(materializer, "publish_plan", fail_publication)

    exit_code = materializer.main([str(source), str(target), "--apply"])

    report = json.loads(capsys.readouterr().out)
    assert exit_code != 0
    assert report["written"] == 0
    assert report["incomplete_generation"] is True
    assert report["reconcile_required"] is True
    assert report["errors"] == 2
    assert all(str(tmp_path) not in message for message in report["error_details"])
