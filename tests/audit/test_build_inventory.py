"""Behavior tests for build_inventory on a small temporary git repository."""

from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

PACKAGE = "packages/claude-dev-env"


def load_builder() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "build_inventory_under_test", Path(__file__).with_name("build_inventory.py")
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


builder = load_builder()

FIXTURE_FILES: dict[str, str] = {
    "README.md": "# fixture\n",
    f"{PACKAGE}/package.json": json.dumps(
        {"files": ["bin/", "rules/", "hooks/", ".agents/", "scripts/", "ghost/"]}
    ),
    f"{PACKAGE}/installable-surfaces.manifest.json": json.dumps(
        {"directories": ["bin", "rules", "hooks"], "root_files": []}
    ),
    f"{PACKAGE}/bin/install.mjs": "export const CONTENT_DIRECTORIES = ['rules'];\n",
    f"{PACKAGE}/rules/alpha.md": "Run `python hooks/blocking/used_hook.py`.\nSee the fixture-skill skill.\n",
    f"{PACKAGE}/rules-archived/old.md": "old\n",
    f"{PACKAGE}/hooks/hooks.json": json.dumps(
        {"command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/blocking/used_hook.py"}
    ),
    f"{PACKAGE}/hooks/blocking/used_hook.py": (
        "from helper_library import answer\nfrom hook_parts import (\n    piece,\n)\n"
    ),
    f"{PACKAGE}/hooks/blocking/hook_parts/piece.py": "PIECE = 1\n",
    f"{PACKAGE}/hooks/blocking/helper_library.py": "def answer() -> int:\n    return 1\n",
    f"{PACKAGE}/hooks/blocking/stray_hook.py": "print('stray')\n",
    f"{PACKAGE}/hooks/blocking/test_used_hook.py": "import used_hook\n",
    f"{PACKAGE}/hooks/blocking/test_vanished.py": "import os\n",
    f"{PACKAGE}/.agents/skills/fixture-skill/SKILL.md": "skill body\n",
    f"{PACKAGE}/.agents/skills/fixture-skill/reference/more.md": "more\n",
    f"{PACKAGE}/.agents/skills-archived/retired-skill/SKILL.md": "retired\n",
    f"{PACKAGE}/scripts/copy_one.py": "VALUE = 'same bytes'\n",
    f"{PACKAGE}/scripts/copy_two.py": "VALUE = 'same bytes'\n",
}


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[str]]:
    repository = tmp_path_factory.mktemp("fixture_repository")
    for each_path, each_text in FIXTURE_FILES.items():
        target = repository / each_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(each_text.encode("utf-8"))
    (repository / "untracked.txt").write_text("ignored", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "add", "--", *FIXTURE_FILES], check=True
    )
    output_directory = repository / "out"
    return output_directory, builder.build(repository, output_directory)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t", quoting=csv.QUOTE_NONE))


def inventory_by_path(output_directory: Path) -> dict[str, dict[str, str]]:
    return {
        each_row["path"]: each_row
        for each_row in read_rows(output_directory / "inventory.tsv")
    }


def edge_set(output_directory: Path) -> set[tuple[str, str, str]]:
    return {
        (
            each_row["source_id"].split(":", 1)[1],
            each_row["relation"],
            each_row["target_id"].split(":", 1)[1],
        )
        for each_row in read_rows(output_directory / "dependencies.tsv")
    }


def should_group_a_skill_directory_into_one_row(built: tuple[Path, list[str]]) -> None:
    skill_row = inventory_by_path(built[0])[f"{PACKAGE}/.agents/skills/fixture-skill"]
    assert skill_row["kind"] == "skill"
    assert skill_row["proof_class"] == "OUTPUT"
    assert skill_row["bytes"] == str(len("skill body\n") + len("more\n"))
    assert skill_row["lines"] == "2"


def should_cover_every_tracked_path_and_skip_untracked(
    built: tuple[Path, list[str]],
) -> None:
    all_rows = inventory_by_path(built[0])
    assert f"files\t{len(FIXTURE_FILES)}" in built[1]
    assert "untracked.txt" not in all_rows
    assert sum(int(each_row["bytes"]) for each_row in all_rows.values()) == sum(
        len(each_text.encode("utf-8")) for each_text in FIXTURE_FILES.values()
    )


def should_reconcile_shipped_against_package_files(
    built: tuple[Path, list[str]],
) -> None:
    all_rows = inventory_by_path(built[0])
    assert all_rows[f"{PACKAGE}/rules/alpha.md"]["shipped"] == "yes"
    assert all_rows[f"{PACKAGE}/rules-archived/old.md"]["shipped"] == "no"
    assert all_rows["README.md"]["shipped"] == "no"


def should_record_registration_import_invoke_and_test_edges(
    built: tuple[Path, list[str]],
) -> None:
    all_edges = edge_set(built[0])
    hook = f"{PACKAGE}/hooks/blocking/used_hook.py"
    assert (f"{PACKAGE}/hooks/hooks.json", "registers", hook) in all_edges
    assert (hook, "imports", f"{PACKAGE}/hooks/blocking/helper_library.py") in all_edges
    assert (
        hook,
        "imports",
        f"{PACKAGE}/hooks/blocking/hook_parts/piece.py",
    ) in all_edges
    assert (f"{PACKAGE}/rules/alpha.md", "invokes", hook) in all_edges
    assert (
        f"{PACKAGE}/rules/alpha.md",
        "references",
        f"{PACKAGE}/.agents/skills/fixture-skill",
    ) in all_edges
    assert (f"{PACKAGE}/hooks/blocking/test_used_hook.py", "tests", hook) in all_edges
    assert (
        f"{PACKAGE}/bin/install.mjs",
        "installs",
        f"{PACKAGE}/rules/alpha.md",
    ) in all_edges
    assert (
        inventory_by_path(built[0])[hook]["registered_in"]
        == f"{PACKAGE}/hooks/hooks.json"
    )


def should_flag_each_no_budget_removal_candidate(built: tuple[Path, list[str]]) -> None:
    all_flags = {tuple(each_line.split("\t")[:2]) for each_line in built[1]}
    assert (
        "unreachable_module",
        f"hook_module:{PACKAGE}/hooks/blocking/stray_hook.py",
    ) in all_flags
    assert (
        "hook_unregistered",
        f"hook_module:{PACKAGE}/hooks/blocking/stray_hook.py",
    ) in all_flags
    assert (
        "archive_in_shipped_path",
        f"archive_item:{PACKAGE}/.agents/skills-archived/retired-skill",
    ) in all_flags
    assert (
        "test_subject_gone",
        f"test:{PACKAGE}/hooks/blocking/test_vanished.py",
    ) in all_flags
    assert ("exact_duplicate", f"{PACKAGE}/scripts/copy_one.py") in all_flags


def should_not_flag_registered_or_imported_modules(
    built: tuple[Path, list[str]],
) -> None:
    all_flagged_ids = {
        each_line.split("\t")[1]
        for each_line in built[1]
        if each_line.startswith("unreachable_module")
    }
    assert f"hook_module:{PACKAGE}/hooks/blocking/used_hook.py" not in all_flagged_ids
    assert (
        f"hook_module:{PACKAGE}/hooks/blocking/helper_library.py" not in all_flagged_ids
    )
    assert (
        "archive_in_shipped_path\t" + f"archive_item:{PACKAGE}/rules-archived/old.md"
    ) not in "\n".join(built[1])


def should_report_ship_list_mismatches(built: tuple[Path, list[str]]) -> None:
    all_mismatches = [
        each_line for each_line in built[1] if each_line.startswith("mismatch\t")
    ]
    assert any(
        "'scripts'" in each_line and "manifest does not" in each_line
        for each_line in all_mismatches
    )
    assert any(
        "'ghost'" in each_line and "no tracked file" in each_line
        for each_line in all_mismatches
    )
    assert any(
        "'rules-archived' is outside package.json files" in each_line
        for each_line in all_mismatches
    )


def should_regenerate_byte_identical_tables(built: tuple[Path, list[str]]) -> None:
    output_directory = built[0]
    first = [
        (output_directory / each_name).read_bytes()
        for each_name in ("inventory.tsv", "dependencies.tsv")
    ]
    builder.build(output_directory.parent, output_directory)
    second = [
        (output_directory / each_name).read_bytes()
        for each_name in ("inventory.tsv", "dependencies.tsv")
    ]
    assert first == second
    assert b"\r" not in first[0]
