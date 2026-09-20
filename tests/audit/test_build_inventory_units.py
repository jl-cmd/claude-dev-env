"""Unit behavior for the inventory builder's classification and ship-list helpers.

The end-to-end suite beside this one drives the whole builder over a temporary
git repository. These cases drive one helper at a time, so a break names the
helper that changed rather than the table it fed.

::

    is_test_path("packages/claude-dev-env/hooks/blocking/test_x.py") -> True
    ok:   classify_package_path(".../rules/alpha.md")  -> the rule kind
    flag: classify_package_path(".../rules-archived/old.md") -> the archive kind
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.audit import build_inventory as builder
from tests.audit.config import build_inventory_constants as inventory_constants

PACKAGE = "packages/claude-dev-env"
RULE_PATH = f"{PACKAGE}/rules/alpha.md"
ARCHIVED_RULE_PATH = f"{PACKAGE}/rules-archived/old.md"
HOOK_PATH = f"{PACKAGE}/hooks/blocking/used_hook.py"
SKILL_PATH = f"{PACKAGE}/.agents/skills/fixture-skill/SKILL.md"
SCRIPT_PATH = f"{PACKAGE}/scripts/copy_one.py"
TEST_PATH = f"{PACKAGE}/hooks/blocking/test_used_hook.py"
FILE_MODE = "100644"
BLOB_ID = "0" * 40


def _tracked(path: str, content: bytes = b"body\n", mode: str = FILE_MODE):
    return builder.TrackedFile(path=path, mode=mode, blob_id=BLOB_ID, content=content)


def _inner(path: str) -> str:
    return path[len(inventory_constants.PACKAGE_ROOT) :]


@pytest.fixture(name="repository")
def repository_fixture(tmp_path: Path) -> Path:
    builder.run_git(tmp_path, ("init", "-q", "-b", "main"), None)
    builder.run_git(tmp_path, ("config", "user.email", "audit@example.com"), None)
    builder.run_git(tmp_path, ("config", "user.name", "Audit"), None)
    (tmp_path / "README.md").write_text("# fixture\n", encoding="utf-8", newline="\n")
    nested_directory = tmp_path / "src"
    nested_directory.mkdir()
    (nested_directory / "app.py").write_text(
        "VALUE = 1\n", encoding="utf-8", newline="\n"
    )
    builder.run_git(tmp_path, ("add", "-A"), None)
    builder.run_git(tmp_path, ("commit", "-q", "-m", "fixture"), None)
    return tmp_path


def test_run_git_returns_the_command_output(repository: Path) -> None:
    branch_bytes = builder.run_git(
        repository, ("rev-parse", "--abbrev-ref", "HEAD"), None
    )

    assert branch_bytes.decode("utf-8").strip() == "main"


def test_read_index_entries_parses_one_triple_per_tracked_file(
    repository: Path,
) -> None:
    listing = builder.run_git(repository, ("ls-files", "-s", "-z"), None).decode(
        "utf-8"
    )

    all_entries = builder.read_index_entries(listing)

    assert sorted(each_entry[0] for each_entry in all_entries) == [
        "README.md",
        "src/app.py",
    ]
    assert all(each_entry[1] == FILE_MODE for each_entry in all_entries)


def test_split_blob_stream_pairs_each_body_with_its_entry(repository: Path) -> None:
    listing = builder.run_git(repository, ("ls-files", "-s", "-z"), None).decode(
        "utf-8"
    )
    all_entries = builder.read_index_entries(listing)
    request = "".join(f"{each_entry[2]}\n" for each_entry in all_entries).encode(
        "utf-8"
    )
    blob_stream = builder.run_git(repository, ("cat-file", "--batch"), request)

    all_tracked = builder.split_blob_stream(blob_stream, all_entries)

    by_path = {each_file.path: each_file.content for each_file in all_tracked}
    assert by_path["README.md"] == b"# fixture\n"
    assert by_path["src/app.py"] == b"VALUE = 1\n"


def test_read_tracked_files_reads_every_path_sorted(repository: Path) -> None:
    all_tracked = builder.read_tracked_files(repository)

    assert [each_file.path for each_file in all_tracked] == ["README.md", "src/app.py"]


def test_is_test_path_separates_a_test_module_from_production(repository: Path) -> None:
    assert builder.is_test_path(TEST_PATH) is True
    assert builder.is_test_path(HOOK_PATH) is False


def test_directory_group_takes_the_first_segment_under_the_prefix() -> None:
    grouped = builder.directory_group("rules/nested/deep.md", "rules/")

    assert grouped == "rules/nested"


def test_package_prefix_kind_matches_the_longest_declared_prefix() -> None:
    cursor_kind = builder.package_prefix_kind("scripts/sync_to_cursor/project.py")
    script_kind = builder.package_prefix_kind("scripts/copy_one.py")

    assert cursor_kind == inventory_constants.CURSOR_PROJECTION_KIND
    assert script_kind == inventory_constants.SCRIPTS_MODULE_KIND
    assert builder.package_prefix_kind("unlisted/thing.md") == ""


def test_classify_package_archive_names_an_archived_rule() -> None:
    archived = builder.classify_package_archive(
        ARCHIVED_RULE_PATH, _inner(ARCHIVED_RULE_PATH)
    )
    live = builder.classify_package_archive(RULE_PATH, _inner(RULE_PATH))

    assert archived is not None
    assert archived[0] == inventory_constants.ARCHIVE_ITEM_KIND
    assert live is None


def test_classify_package_agent_asset_groups_a_skill_under_its_directory() -> None:
    classified = builder.classify_package_agent_asset(SKILL_PATH, _inner(SKILL_PATH))

    assert classified is not None
    assert classified[0] == inventory_constants.SKILL_KIND
    assert classified[1].endswith("fixture-skill")


def test_classify_package_hook_names_a_hook_module() -> None:
    classified = builder.classify_package_hook(HOOK_PATH, _inner(HOOK_PATH))

    assert classified is not None
    assert classified[0] in {
        inventory_constants.HOOK_MODULE_KIND,
        inventory_constants.HOOK_SUPPORT_KIND,
    }
    assert builder.classify_package_hook(RULE_PATH, _inner(RULE_PATH)) is None


def test_classify_package_path_separates_a_rule_from_its_archive() -> None:
    live_kind, _ = builder.classify_package_path(RULE_PATH, _inner(RULE_PATH))
    archived_kind, _ = builder.classify_package_path(
        ARCHIVED_RULE_PATH, _inner(ARCHIVED_RULE_PATH)
    )

    assert live_kind == inventory_constants.RULE_KIND
    assert archived_kind == inventory_constants.ARCHIVE_ITEM_KIND


def test_classify_archive_path_stays_quiet_on_a_live_path() -> None:
    assert builder.classify_archive_path(RULE_PATH) is None


def test_classify_client_path_names_a_continuous_integration_workflow() -> None:
    classified = builder.classify_client_path(
        ".github/workflows/check.yml", "check.yml"
    )

    assert classified is not None
    assert classified[0] == inventory_constants.CI_WORKFLOW_KIND
    assert builder.classify_client_path(RULE_PATH, "alpha.md") is None


def test_classify_path_reads_the_mode_for_a_symlink() -> None:
    link_kind, _ = builder.classify_path(_tracked("link.md", b"target.md", "120000"))
    rule_kind, _ = builder.classify_path(_tracked(RULE_PATH))

    assert link_kind == inventory_constants.SYMLINK_KIND
    assert rule_kind == inventory_constants.RULE_KIND


def test_build_components_collects_a_skill_directory_into_one_component() -> None:
    all_files = [
        _tracked(SKILL_PATH),
        _tracked(f"{PACKAGE}/.agents/skills/fixture-skill/reference/more.md"),
        _tracked(RULE_PATH),
    ]

    component_by_id = builder.build_components(all_files)

    all_skill_components = [
        each_component
        for each_component in component_by_id.values()
        if each_component.kind == inventory_constants.SKILL_KIND
    ]
    assert len(all_skill_components) == 1
    assert len(all_skill_components[0].all_files) == 2


def test_decode_text_returns_text_for_source_and_nothing_for_binary() -> None:
    source_text = builder.decode_text(_tracked(SCRIPT_PATH, b"VALUE = 1\n"))
    binary_text = builder.decode_text(_tracked("logo.png", b"\x89PNG\r\n\x1a\n"))

    assert source_text == "VALUE = 1\n"
    assert binary_text == ""


def test_find_tracked_json_parses_a_tracked_document() -> None:
    manifest_path = f"{PACKAGE}/package.json"
    all_files = [
        _tracked(manifest_path, json.dumps({"files": ["bin/"]}).encode("utf-8"))
    ]

    parsed = builder.find_tracked_json(all_files, manifest_path)
    absent = builder.find_tracked_json(all_files, f"{PACKAGE}/missing.json")

    assert parsed == {"files": ["bin/"]}
    assert absent == {}


def test_string_entries_keeps_only_string_members() -> None:
    assert builder.string_entries(["bin/", 3, "rules/"]) == ("bin/", "rules/")
    assert builder.string_entries("bin/") == ()


def test_installer_content_directories_reads_the_declared_names() -> None:
    all_files = [
        _tracked(
            f"{PACKAGE}/bin/install.mjs",
            b"export const CONTENT_DIRECTORIES = ['rules', 'hooks'];\n",
        )
    ]

    all_directories = builder.installer_content_directories(all_files)

    assert all_directories == ("rules", "hooks")


def test_read_ship_lists_collects_the_three_sources() -> None:
    all_files = [
        _tracked(
            f"{PACKAGE}/package.json",
            json.dumps({"files": ["rules/", "!rules/draft.md"]}).encode("utf-8"),
        ),
        _tracked(
            f"{PACKAGE}/installable-surfaces.manifest.json",
            json.dumps({"directories": ["rules"], "root_files": ["README.md"]}).encode(
                "utf-8"
            ),
        ),
        _tracked(
            f"{PACKAGE}/bin/install.mjs",
            b"export const CONTENT_DIRECTORIES = ['rules'];\n",
        ),
    ]

    ship_lists = builder.read_ship_lists(all_files)

    assert "rules/" in ship_lists.package_files
    assert ship_lists.manifest_directories == ("rules",)
    assert ship_lists.manifest_root_files == ("README.md",)
    assert ship_lists.content_directories == ("rules",)


def test_matches_ship_entry_covers_a_directory_prefix_and_a_file() -> None:
    assert builder.matches_ship_entry("rules/alpha.md", ("rules/",)) is True
    assert builder.matches_ship_entry("rules/alpha.md", ("rules/alpha.md",)) is True
    assert builder.matches_ship_entry("docs/alpha.md", ("rules/",)) is False


def test_shipped_status_separates_a_shipped_rule_from_an_unshipped_doc() -> None:
    ship_lists = builder.ShipLists(
        package_files=("rules/",),
        package_negations=(),
        manifest_directories=("rules",),
        manifest_root_files=(),
        content_directories=("rules",),
    )
    shipped_component = builder.Component(
        component_id=RULE_PATH,
        path=RULE_PATH,
        kind=inventory_constants.RULE_KIND,
        all_files=[_tracked(RULE_PATH)],
    )
    unshipped_path = f"{PACKAGE}/docs/note.md"
    unshipped_component = builder.Component(
        component_id=unshipped_path,
        path=unshipped_path,
        kind=inventory_constants.DOC_KIND,
        all_files=[_tracked(unshipped_path)],
    )

    assert builder.shipped_status(shipped_component, ship_lists) == (
        inventory_constants.SHIPPED_YES
    )
    assert builder.shipped_status(unshipped_component, ship_lists) == (
        inventory_constants.SHIPPED_NO
    )


def test_context_status_follows_the_kind_and_the_shipped_verdict() -> None:
    rule_component = builder.Component(
        component_id=RULE_PATH, path=RULE_PATH, kind=inventory_constants.RULE_KIND
    )
    test_component = builder.Component(
        component_id=TEST_PATH, path=TEST_PATH, kind=inventory_constants.TEST_KIND
    )

    assert builder.context_status(rule_component, inventory_constants.SHIPPED_YES) == (
        inventory_constants.SHIPPED_YES
    )
    assert builder.context_status(test_component, inventory_constants.SHIPPED_NO) == (
        inventory_constants.SHIPPED_NO
    )


def test_resolve_python_module_finds_a_sibling_module() -> None:
    all_files = [
        _tracked(HOOK_PATH),
        _tracked(f"{PACKAGE}/hooks/blocking/helper_library.py"),
    ]
    component_by_id = builder.build_components(all_files)
    index = builder.MentionIndex(component_by_id)

    all_targets = builder.resolve_python_module("helper_library", HOOK_PATH, index)

    assert any("helper_library" in each_target for each_target in all_targets)


def test_module_tail_targets_resolves_a_package_file_tail() -> None:
    package_module_path = f"{PACKAGE}/hooks/blocking/hook_parts/piece.py"
    component_by_id = builder.build_components(
        [_tracked(HOOK_PATH), _tracked(package_module_path)]
    )
    index = builder.MentionIndex(component_by_id)

    all_targets = builder.module_tail_targets("hook_parts/piece.py", HOOK_PATH, index)

    assert any("piece" in each_target for each_target in all_targets)


def _import_index() -> tuple[object, str]:
    package_module_path = f"{PACKAGE}/hooks/blocking/hook_parts/piece.py"
    helper_path = f"{PACKAGE}/hooks/blocking/helper_library.py"
    component_by_id = builder.build_components(
        [_tracked(HOOK_PATH), _tracked(package_module_path), _tracked(helper_path)]
    )
    return builder.MentionIndex(component_by_id), package_module_path


def test_named_import_targets_resolves_a_submodule_name() -> None:
    index, package_module_path = _import_index()

    all_targets = builder.named_import_targets(
        "hook_parts", "piece", HOOK_PATH, index
    )

    assert any(package_module_path in each_target for each_target in all_targets)


def test_import_match_targets_reads_a_plain_import_statement() -> None:
    index, _ = _import_index()

    all_targets = builder.import_match_targets(
        "", "", "helper_library", HOOK_PATH, index
    )

    assert any("helper_library" in each_target for each_target in all_targets)


def test_python_import_targets_finds_every_import_in_a_file() -> None:
    index, package_module_path = _import_index()
    source_text = "from hook_parts import piece\nimport helper_library\n"

    all_targets = builder.python_import_targets(source_text, HOOK_PATH, index)

    assert any(package_module_path in each_target for each_target in all_targets)
    assert any("helper_library" in each_target for each_target in all_targets)
