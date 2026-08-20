"""Unit tests for verify_installable_package helpers.

Covers path extraction, manifest loading, tarball surface matching, and
command walking without requiring a full npm pack on every case.
"""

from __future__ import annotations

import sys
import tarfile
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import verify_installable_package as mod
from dev_env_scripts_constants.verify_installable_package_constants import (
    CLASS_PACKAGED,
    MANIFEST_FILENAME,
    PLUGIN_ROOT_TOKEN,
    TARBALL_PACKAGE_PREFIX,
)

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def test_load_manifest_lists_hooks_and_claude_md() -> None:
    manifest = mod.load_installable_surfaces_manifest(from_package_root=PACKAGE_ROOT)
    all_directories = mod.required_directory_names(manifest)
    all_root_files = mod.required_root_file_names(manifest)
    assert "hooks" in all_directories
    assert "output-styles" in all_directories
    assert ".agents" in all_directories
    assert "AGENTS.md" in all_root_files
    assert ".claude/CLAUDE.md" in all_root_files
    assert MANIFEST_FILENAME in all_root_files


def test_extract_python_script_token_from_plugin_root_command() -> None:
    command = (
        f"python3 {PLUGIN_ROOT_TOKEN}hooks/blocking/pre_tool_use_dispatcher.py"
    )
    script_token = mod.extract_python_script_token(command)
    assert script_token == f"{PLUGIN_ROOT_TOKEN}hooks/blocking/pre_tool_use_dispatcher.py"


def test_package_relative_hook_script_path_strips_plugin_root() -> None:
    script_token = f"{PLUGIN_ROOT_TOKEN}hooks/blocking/stop_dispatcher.py"
    relative_path = mod.package_relative_hook_script_path(script_token)
    assert relative_path == "hooks/blocking/stop_dispatcher.py"


def test_extract_python_script_token_skips_inline_c_command() -> None:
    command = 'python3 -c "import sys; print(1)"'
    assert mod.extract_python_script_token(command) is None


def test_surface_appears_in_tarball_members_for_directory_children() -> None:
    all_members = frozenset(
        {
            f"{TARBALL_PACKAGE_PREFIX}hooks/hooks.json",
            f"{TARBALL_PACKAGE_PREFIX}AGENTS.md",
            f"{TARBALL_PACKAGE_PREFIX}CLAUDE.md",
        }
    )
    assert mod.surface_appears_in_tarball_members("hooks", all_members)
    assert mod.surface_appears_in_tarball_members("AGENTS.md", all_members)
    assert mod.surface_appears_in_tarball_members("CLAUDE.md", all_members)
    assert not mod.surface_appears_in_tarball_members("missing-dir", all_members)


def test_missing_manifest_surfaces_in_tarball_reports_absent_root_file() -> None:
    manifest = {
        "directories": ["hooks"],
        "root_files": ["AGENTS.md", "CLAUDE.md", "codex-capability-map.json"],
    }
    all_members = frozenset(
        {
            f"{TARBALL_PACKAGE_PREFIX}hooks/hooks.json",
            f"{TARBALL_PACKAGE_PREFIX}AGENTS.md",
            f"{TARBALL_PACKAGE_PREFIX}CLAUDE.md",
        }
    )
    missing = mod.missing_manifest_surfaces_in_tarball(manifest, all_members)
    assert missing == ["codex-capability-map.json"]


def test_walk_json_command_fields_collects_nested_commands() -> None:
    payload = {
        "hooks": {
            "PreToolUse": [
                {"hooks": [{"type": "command", "command": "python3 a.py"}]},
            ],
            "Stop": [{"hooks": [{"command": "python3 b.py"}]}],
        }
    }
    all_commands = mod.walk_json_command_fields(payload)
    assert all_commands == ["python3 a.py", "python3 b.py"]


def test_list_npm_pack_tarball_members_reads_archive(tmp_path: Path) -> None:
    tarball_path = tmp_path / "sample.tgz"
    with tarfile.open(tarball_path, mode="w:gz") as archive:
        member_path = tmp_path / "member.txt"
        member_path.write_text("ok", encoding="utf-8")
        archive.add(member_path, arcname=f"{TARBALL_PACKAGE_PREFIX}hooks/hooks.json")
    all_members = mod.list_npm_pack_tarball_members(from_tarball_path=tarball_path)
    assert f"{TARBALL_PACKAGE_PREFIX}hooks/hooks.json" in all_members


def test_classify_surface_marks_hooks_packaged() -> None:
    packaged_names = mod.load_package_json_file_entries(from_package_root=PACKAGE_ROOT)
    classification = mod.classify_surface(
        "hooks",
        packaged_names,
        from_package_root=PACKAGE_ROOT,
    )
    assert classification == CLASS_PACKAGED


def test_load_hook_python_script_paths_returns_committed_hooks_paths() -> None:
    all_paths = mod.load_hook_python_script_paths(from_package_root=PACKAGE_ROOT)
    assert all_paths
    assert all(each_path.startswith("hooks/") for each_path in all_paths)
    assert all(each_path.endswith(".py") for each_path in all_paths)


def test_package_root_path_points_at_package_json() -> None:
    package_root = mod.package_root_path()
    assert (package_root / "package.json").is_file()
    assert package_root.name == "claude-dev-env"


def test_repository_root_path_contains_packages_directory() -> None:
    repository_root = mod.repository_root_path()
    assert (repository_root / "packages" / "claude-dev-env").is_dir()


def test_resolve_npm_executable_returns_existing_path() -> None:
    npm_path = mod.resolve_npm_executable()
    assert Path(npm_path).exists()
    assert "npm" in Path(npm_path).name.lower()


def test_tarball_member_prefix_for_surface_uses_package_prefix() -> None:
    member_prefix = mod.tarball_member_prefix_for_surface("hooks")
    assert member_prefix == f"{TARBALL_PACKAGE_PREFIX}hooks"


def test_run_npm_pack_writes_tarball(tmp_path: Path) -> None:
    tarball_path = mod.run_npm_pack(
        into_directory=tmp_path,
        from_package_root=PACKAGE_ROOT,
    )
    assert tarball_path.is_file()
    assert tarball_path.suffix == ".tgz"
    all_members = mod.list_npm_pack_tarball_members(from_tarball_path=tarball_path)
    assert any(each_member.startswith(f"{TARBALL_PACKAGE_PREFIX}hooks/") for each_member in all_members)


def test_list_git_tracked_paths_under_includes_hooks_json() -> None:
    all_tracked = mod.list_git_tracked_paths_under(
        under_relative_path="packages/claude-dev-env/hooks",
        from_repository_root=mod.repository_root_path(),
    )
    assert "packages/claude-dev-env/hooks/hooks.json" in all_tracked


def test_untracked_or_missing_hook_scripts_empty_for_live_hooks() -> None:
    all_hook_scripts = mod.load_hook_python_script_paths(from_package_root=PACKAGE_ROOT)
    missing_scripts = mod.untracked_or_missing_hook_scripts(
        all_package_relative_scripts=all_hook_scripts,
        from_package_root=PACKAGE_ROOT,
        from_repository_root=mod.repository_root_path(),
    )
    assert missing_scripts == []


def test_untracked_or_missing_hook_scripts_flags_unknown_path() -> None:
    missing_scripts = mod.untracked_or_missing_hook_scripts(
        all_package_relative_scripts=["hooks/does_not_exist_anywhere.py"],
        from_package_root=PACKAGE_ROOT,
        from_repository_root=mod.repository_root_path(),
    )
    assert missing_scripts == ["hooks/does_not_exist_anywhere.py"]


def test_smoke_compile_python_scripts_accepts_live_hooks() -> None:
    all_hook_scripts = mod.load_hook_python_script_paths(from_package_root=PACKAGE_ROOT)
    compile_failures = mod.smoke_compile_python_scripts(
        all_package_relative_scripts=all_hook_scripts,
        from_package_root=PACKAGE_ROOT,
    )
    assert compile_failures == []


def test_smoke_check_install_entrypoint_passes() -> None:
    entrypoint_failure = mod.smoke_check_install_entrypoint(from_package_root=PACKAGE_ROOT)
    assert entrypoint_failure is None


def test_verify_packed_manifest_surfaces_finds_no_gaps() -> None:
    missing_surfaces = mod.verify_packed_manifest_surfaces(from_package_root=PACKAGE_ROOT)
    assert missing_surfaces == []


def test_run_all_installable_package_checks_passes_on_live_package() -> None:
    all_failures = mod.run_all_installable_package_checks(
        from_package_root=PACKAGE_ROOT,
        from_repository_root=mod.repository_root_path(),
    )
    assert all_failures == []
