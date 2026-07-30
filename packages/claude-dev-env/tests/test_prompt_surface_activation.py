"""Assert installable surfaces ship in the real npm pack tarball.

Drives ``verify_installable_package`` helpers so the suite proves what users
receive from the packed package: every manifest directory and root file is a
tarball member, every hooks.json ``.py`` command resolves to a git-tracked
file, and those scripts pass ``py_compile``.
"""

from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PACKAGE_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import verify_installable_package as verify
from dev_env_scripts_constants.verify_installable_package_constants import (
    CLASS_CONTRADICTORY,
    CLASS_PACKAGED,
    CLASS_SOURCE_ONLY,
    MANIFEST_FILENAME,
)


def test_manifest_file_is_listed_in_package_json_files() -> None:
    packaged_names = verify.load_package_json_file_entries(from_package_root=PACKAGE_ROOT)
    assert MANIFEST_FILENAME in packaged_names


def test_output_styles_is_packaged_not_source_only() -> None:
    packaged_names = verify.load_package_json_file_entries(from_package_root=PACKAGE_ROOT)
    classification = verify.classify_surface(
        "output-styles",
        packaged_names,
        from_package_root=PACKAGE_ROOT,
    )
    assert classification == CLASS_PACKAGED


def test_every_manifest_directory_has_non_contradictory_classification() -> None:
    manifest = verify.load_installable_surfaces_manifest(from_package_root=PACKAGE_ROOT)
    packaged_names = verify.load_package_json_file_entries(from_package_root=PACKAGE_ROOT)
    classification_by_directory = {
        each_name: verify.classify_surface(
            each_name,
            packaged_names,
            from_package_root=PACKAGE_ROOT,
        )
        for each_name in verify.required_directory_names(manifest)
    }
    assert classification_by_directory
    assert CLASS_CONTRADICTORY not in classification_by_directory.values()
    for each_name, each_class in classification_by_directory.items():
        assert each_class in {CLASS_PACKAGED, CLASS_SOURCE_ONLY}, (
            f"{each_name}={each_class}"
        )


def test_npm_pack_tarball_contains_every_manifest_surface() -> None:
    missing_surfaces = verify.verify_packed_manifest_surfaces(
        from_package_root=PACKAGE_ROOT,
    )
    assert missing_surfaces == [], (
        "Manifest surfaces missing from npm pack tarball:\n"
        + "\n".join(missing_surfaces)
    )


def test_hook_commands_resolve_to_git_tracked_files() -> None:
    all_hook_scripts = verify.load_hook_python_script_paths(
        from_package_root=PACKAGE_ROOT,
    )
    assert all_hook_scripts
    missing_scripts = verify.untracked_or_missing_hook_scripts(
        all_package_relative_scripts=all_hook_scripts,
        from_package_root=PACKAGE_ROOT,
        from_repository_root=verify.repository_root_path(),
    )
    assert missing_scripts == [], (
        "Hook scripts missing from git index or disk:\n" + "\n".join(missing_scripts)
    )


def test_hook_scripts_pass_py_compile_smoke() -> None:
    all_hook_scripts = verify.load_hook_python_script_paths(
        from_package_root=PACKAGE_ROOT,
    )
    compile_failures = verify.smoke_compile_python_scripts(
        all_package_relative_scripts=all_hook_scripts,
        from_package_root=PACKAGE_ROOT,
    )
    assert compile_failures == [], (
        "Hook scripts failed py_compile:\n" + "\n".join(compile_failures)
    )


def test_install_entrypoint_passes_node_check_smoke() -> None:
    entrypoint_failure = verify.smoke_check_install_entrypoint(
        from_package_root=PACKAGE_ROOT,
    )
    assert entrypoint_failure is None, entrypoint_failure
