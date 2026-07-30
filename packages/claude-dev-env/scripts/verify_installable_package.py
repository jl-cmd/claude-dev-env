#!/usr/bin/env python3
"""Verify the npm package delivers every installable surface users need.

Runs real ``npm pack``, reads the generated tarball member list, and checks
each directory and root file from ``installable-surfaces.manifest.json``.
Also walks ``hooks/hooks.json`` for ``command`` fields, requires each ``.py``
script path to be tracked by ``git ls-files``, and smoke-compiles those scripts.

::

    python verify_installable_package.py
    -> exit 0 when the packed tarball holds every manifest surface
    flag: missing package/hooks/ in the tarball fails the run

Call the public helpers from tests so the suite exercises shipped code rather
than reimplementing pack or path logic inside the test module.
"""

from __future__ import annotations

import json
import py_compile
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Mapping

from dev_env_scripts_constants.verify_installable_package_constants import (
    CLASS_CONTRADICTORY,
    CLASS_PACKAGED,
    CLASS_SOURCE_ONLY,
    EXIT_CODE_FAILURE,
    EXIT_CODE_SUCCESS,
    GIT_BINARY_NAME,
    GIT_LS_FILES_SUBCOMMAND,
    HOOKS_JSON_RELATIVE_PATH,
    INSTALL_ENTRYPOINT_RELATIVE_PATH,
    INSTALL_ENTRYPOINT_SMOKE_FAILURE_HEADER,
    MANIFEST_DIRECTORIES_KEY,
    MANIFEST_FILENAME,
    MANIFEST_ROOT_FILES_KEY,
    MISSING_MANIFEST_SURFACES_HEADER,
    NEWLINE_JOIN_SEPARATOR,
    NODE_BINARY_NAME,
    NODE_CHECK_FLAG,
    NPM_BINARY_NAME,
    NPM_CMD_BINARY_NAME,
    NPM_PACK_DESTINATION_FLAG,
    NPM_PACK_FILENAME_KEY,
    NPM_PACK_JSON_FLAG,
    NPM_PACK_SUBCOMMAND,
    PACKAGE_JSON_EXCLUDE_PREFIX,
    PACKAGE_JSON_FILENAME,
    PACKAGE_JSON_FILES_KEY,
    PACKAGE_PATH_FROM_REPOSITORY,
    PLUGIN_ROOT_TOKEN,
    PYTHON_FILE_SUFFIX,
    SMOKE_COMPILE_FAILURES_HEADER,
    TARBALL_PACKAGE_PREFIX,
    UNTRACKED_HOOK_SCRIPTS_HEADER,
    UTF8_ENCODING,
    VERIFICATION_PASSED_MESSAGE,
)


def package_root_path() -> Path:
    """Return the claude-dev-env package root that holds package.json."""
    return Path(__file__).resolve().parent.parent


def repository_root_path() -> Path:
    """Return the monorepo root two levels above the package root."""
    return package_root_path().parent.parent


def resolve_npm_executable() -> str:
    """Resolve the npm launcher path for the host platform.

    Returns:
        Absolute path to ``npm.cmd`` on Windows or ``npm`` on POSIX.

    Raises:
        FileNotFoundError: When neither launcher is on PATH.
    """
    for each_binary_name in (NPM_CMD_BINARY_NAME, NPM_BINARY_NAME):
        maybe_path = shutil.which(each_binary_name)
        if maybe_path is not None:
            return maybe_path
    raise FileNotFoundError(
        f"neither {NPM_CMD_BINARY_NAME!r} nor {NPM_BINARY_NAME!r} found on PATH"
    )


def load_installable_surfaces_manifest(from_package_root: Path) -> Mapping[str, object]:
    """Load the committed installable-surfaces manifest.

    Args:
        from_package_root: Package directory that holds the manifest file.

    Returns:
        Parsed JSON object with directories and root_files lists.
    """
    manifest_path = from_package_root / MANIFEST_FILENAME
    return json.loads(manifest_path.read_text(encoding=UTF8_ENCODING))


def _string_names_from_manifest_key(
    all_manifest_entries: Mapping[str, object],
    from_key: str,
) -> list[str]:
    """Return non-empty string entries for one manifest list key.

    Args:
        all_manifest_entries: Parsed installable-surfaces manifest.
        from_key: JSON key whose value is a list of surface names.

    Returns:
        String basenames from the list, or an empty list when the key is absent
        or not a list.
    """
    all_names = all_manifest_entries.get(from_key, [])
    if not isinstance(all_names, list):
        return []
    return [each for each in all_names if isinstance(each, str) and each]


def required_directory_names(all_manifest_entries: Mapping[str, object]) -> list[str]:
    """Return required top-level directory names from the manifest.

    Args:
        all_manifest_entries: Parsed installable-surfaces manifest.

    Returns:
        Directory basenames the packed package must deliver.
    """
    return _string_names_from_manifest_key(
        all_manifest_entries,
        MANIFEST_DIRECTORIES_KEY,
    )


def required_root_file_names(all_manifest_entries: Mapping[str, object]) -> list[str]:
    """Return required package-root file names from the manifest.

    Args:
        all_manifest_entries: Parsed installable-surfaces manifest.

    Returns:
        File basenames the packed package must deliver at package root.
    """
    return _string_names_from_manifest_key(
        all_manifest_entries,
        MANIFEST_ROOT_FILES_KEY,
    )


def load_package_json_file_entries(from_package_root: Path) -> set[str]:
    """Load positive ``files`` entries from package.json without bang-excludes.

    Args:
        from_package_root: Package directory that holds package.json.

    Returns:
        Basename entries with trailing slashes stripped.
    """
    package_json_path = from_package_root / PACKAGE_JSON_FILENAME
    payload = json.loads(package_json_path.read_text(encoding=UTF8_ENCODING))
    all_entries = payload.get(PACKAGE_JSON_FILES_KEY, [])
    if not isinstance(all_entries, list):
        return set()
    return {
        each.rstrip("/")
        for each in all_entries
        if isinstance(each, str) and not each.startswith(PACKAGE_JSON_EXCLUDE_PREFIX)
    }


def classify_surface(
    directory_name: str,
    all_packaged_names: set[str],
    from_package_root: Path,
) -> str:
    """Classify one top-level surface against on-disk state and package.json.

    ::

        classify_surface("hooks", {"hooks", "rules"}, package_root) -> packaged
        classify_surface("scratch", {"hooks"}, package_root) -> source_only
        flag: package.json lists missing_dir with no on-disk folder -> contradictory

    Args:
        directory_name: Top-level package directory basename.
        all_packaged_names: Positive package.json files basenames.
        from_package_root: Package directory used for the on-disk check.

    Returns:
        One of packaged, source_only, or contradictory.
    """
    is_on_disk = (from_package_root / directory_name).is_dir()
    is_packaged = directory_name in all_packaged_names
    if is_on_disk and is_packaged:
        return CLASS_PACKAGED
    if is_on_disk and not is_packaged:
        return CLASS_SOURCE_ONLY
    if not is_on_disk and is_packaged:
        return CLASS_CONTRADICTORY
    return CLASS_SOURCE_ONLY


def tarball_member_prefix_for_surface(surface_name: str) -> str:
    """Build the npm-pack member prefix for one surface path.

    Args:
        surface_name: Directory or root-file path relative to the package root.

    Returns:
        Prefix such as ``package/hooks`` used to match tarball members.
    """
    return f"{TARBALL_PACKAGE_PREFIX}{surface_name}"


def surface_appears_in_tarball_members(
    surface_name: str,
    all_tarball_members: frozenset[str],
) -> bool:
    """Report whether a surface path appears among packed tarball members.

    Args:
        surface_name: Directory or root-file path relative to the package root.
        all_tarball_members: Normalized member paths from the pack tarball.

    Returns:
        True when the exact member or a child path under the surface exists.
    """
    member_prefix = tarball_member_prefix_for_surface(surface_name)
    if member_prefix in all_tarball_members:
        return True
    child_prefix = f"{member_prefix}/"
    return any(each_member.startswith(child_prefix) for each_member in all_tarball_members)


def list_npm_pack_tarball_members(from_tarball_path: Path) -> frozenset[str]:
    """List normalized member paths inside an npm pack tarball.

    Args:
        from_tarball_path: Path to a ``.tgz`` produced by ``npm pack``.

    Returns:
        Forward-slash member names as stored in the archive.
    """
    with tarfile.open(from_tarball_path, mode="r:gz") as archive:
        return frozenset(
            each_member.name.replace("\\", "/") for each_member in archive.getmembers()
        )


def _npm_pack_filename_from_json(stdout_text: str) -> str:
    payload = json.loads(stdout_text)
    if isinstance(payload, list) and payload:
        first_record = payload[0]
        if isinstance(first_record, dict):
            filename = first_record.get(NPM_PACK_FILENAME_KEY)
            if isinstance(filename, str) and filename:
                return filename
    if isinstance(payload, dict):
        filename = payload.get(NPM_PACK_FILENAME_KEY)
        if isinstance(filename, str) and filename:
            return filename
    raise RuntimeError(f"npm pack --json missing {NPM_PACK_FILENAME_KEY}: {stdout_text!r}")


def run_npm_pack(into_directory: Path, from_package_root: Path) -> Path:
    """Run ``npm pack --json`` and return the written tarball path.

    Args:
        into_directory: Directory that receives the generated ``.tgz``.
        from_package_root: Package directory npm packs.

    Returns:
        Absolute path of the generated tarball.
    """
    completed = subprocess.run(
        [
            resolve_npm_executable(),
            NPM_PACK_SUBCOMMAND,
            NPM_PACK_JSON_FLAG,
            NPM_PACK_DESTINATION_FLAG,
            str(into_directory),
        ],
        cwd=str(from_package_root),
        check=True,
        capture_output=True,
        text=True,
        encoding=UTF8_ENCODING,
    )
    tarball_name = _npm_pack_filename_from_json(completed.stdout)
    return into_directory / tarball_name


def missing_manifest_surfaces_in_tarball(
    all_manifest_entries: Mapping[str, object],
    all_tarball_members: frozenset[str],
) -> list[str]:
    """List manifest surfaces absent from the packed tarball.

    Args:
        all_manifest_entries: Parsed installable-surfaces manifest.
        all_tarball_members: Member paths from ``npm pack``.

    Returns:
        Surface names (directories and root files) missing from the tarball.
    """
    all_required = required_directory_names(all_manifest_entries) + required_root_file_names(
        all_manifest_entries
    )
    return [
        each_surface
        for each_surface in all_required
        if not surface_appears_in_tarball_members(each_surface, all_tarball_members)
    ]


def walk_json_command_fields(node: object) -> list[str]:
    """Collect every non-empty string under a ``command`` key in JSON.

    Args:
        node: Arbitrary JSON-decoded object.

    Returns:
        Command strings in depth-first encounter order.
    """
    all_commands: list[str] = []
    if isinstance(node, dict):
        command = node.get("command")
        if isinstance(command, str) and command.strip():
            all_commands.append(command)
        for each_child in node.values():
            all_commands.extend(walk_json_command_fields(each_child))
        return all_commands
    if isinstance(node, list):
        for each_child in node:
            all_commands.extend(walk_json_command_fields(each_child))
    return all_commands


def extract_python_script_token(command: str) -> str | None:
    """Extract a ``.py`` path token from a hook command string.

    Handles ``${CLAUDE_PLUGIN_ROOT}/hooks/...py`` shapes and absolute paths
    that end with a Python script segment.

    Args:
        command: Full hook command line from hooks.json.

    Returns:
        The ``.py`` token, or None when the command has no script path.
    """
    if PYTHON_FILE_SUFFIX not in command:
        return None
    for each_part in command.replace("\\", "/").split():
        if each_part.endswith(PYTHON_FILE_SUFFIX):
            return each_part
    return None


def package_relative_hook_script_path(script_token: str) -> str | None:
    """Normalize a hook script token to a package-relative ``hooks/...`` path.

    Args:
        script_token: Path token extracted from a hook command.

    Returns:
        Package-relative path, or None when the token is not under hooks/.
    """
    normalized = script_token.replace("\\", "/")
    if normalized.startswith(PLUGIN_ROOT_TOKEN):
        normalized = normalized[len(PLUGIN_ROOT_TOKEN) :]
    package_marker = f"{PACKAGE_PATH_FROM_REPOSITORY}/"
    if package_marker in normalized:
        normalized = normalized.split(package_marker, 1)[1]
    if normalized.startswith("hooks/"):
        return normalized
    return None


def load_hook_python_script_paths(from_package_root: Path) -> list[str]:
    """Load package-relative ``.py`` paths referenced by hooks.json commands.

    Args:
        from_package_root: Package directory that holds hooks/hooks.json.

    Returns:
        Deduplicated package-relative script paths in first-seen order.
    """
    hooks_json_path = from_package_root / HOOKS_JSON_RELATIVE_PATH
    payload = json.loads(hooks_json_path.read_text(encoding=UTF8_ENCODING))
    seen_paths: set[str] = set()
    all_paths: list[str] = []
    for each_command in walk_json_command_fields(payload):
        script_token = extract_python_script_token(each_command)
        if script_token is None:
            continue
        relative_path = package_relative_hook_script_path(script_token)
        if relative_path is None or relative_path in seen_paths:
            continue
        seen_paths.add(relative_path)
        all_paths.append(relative_path)
    return all_paths


def list_git_tracked_paths_under(
    under_relative_path: str,
    from_repository_root: Path,
) -> frozenset[str]:
    """List git-tracked paths under a repository-relative prefix.

    Args:
        under_relative_path: Repository-relative directory or file prefix.
        from_repository_root: Repository root for ``git ls-files``.

    Returns:
        Forward-slash repository-relative paths present in the index.
    """
    completed = subprocess.run(
        [GIT_BINARY_NAME, GIT_LS_FILES_SUBCOMMAND, "--", under_relative_path],
        cwd=str(from_repository_root),
        check=True,
        capture_output=True,
        text=True,
        encoding=UTF8_ENCODING,
    )
    return frozenset(
        each_line.replace("\\", "/")
        for each_line in completed.stdout.splitlines()
        if each_line.strip()
    )


def untracked_or_missing_hook_scripts(
    all_package_relative_scripts: list[str],
    from_package_root: Path,
    from_repository_root: Path,
) -> list[str]:
    """Return hook scripts that are missing on disk or absent from the git index.

    Args:
        all_package_relative_scripts: Paths relative to the package root.
        from_package_root: Package directory for on-disk existence checks.
        from_repository_root: Repository root for ``git ls-files``.

    Returns:
        Package-relative script paths that fail the committed-file check.
    """
    hooks_prefix = f"{PACKAGE_PATH_FROM_REPOSITORY}/hooks"
    all_tracked = list_git_tracked_paths_under(
        under_relative_path=hooks_prefix,
        from_repository_root=from_repository_root,
    )
    missing_scripts: list[str] = []
    for each_script in all_package_relative_scripts:
        on_disk_path = from_package_root / each_script
        repository_relative = f"{PACKAGE_PATH_FROM_REPOSITORY}/{each_script}".replace(
            "\\", "/"
        )
        if not on_disk_path.is_file():
            missing_scripts.append(each_script)
            continue
        if repository_relative not in all_tracked:
            missing_scripts.append(each_script)
    return missing_scripts


def smoke_compile_python_scripts(
    all_package_relative_scripts: list[str],
    from_package_root: Path,
) -> list[str]:
    """Run ``py_compile`` on each package-relative script and collect failures.

    Args:
        all_package_relative_scripts: Paths relative to the package root.
        from_package_root: Package directory that holds the scripts.

    Returns:
        Package-relative paths that failed to compile, with error text.
    """
    all_failures: list[str] = []
    for each_script in all_package_relative_scripts:
        script_path = from_package_root / each_script
        try:
            py_compile.compile(str(script_path), doraise=True)
        except py_compile.PyCompileError as compile_error:
            all_failures.append(f"{each_script}: {compile_error}")
    return all_failures


def smoke_check_install_entrypoint(from_package_root: Path) -> str | None:
    """Run ``node --check`` on the install entrypoint.

    Args:
        from_package_root: Package directory that holds bin/install.mjs.

    Returns:
        Error text when the check fails, otherwise None.
    """
    entrypoint_path = from_package_root / INSTALL_ENTRYPOINT_RELATIVE_PATH
    completed = subprocess.run(
        [NODE_BINARY_NAME, NODE_CHECK_FLAG, str(entrypoint_path)],
        cwd=str(from_package_root),
        capture_output=True,
        text=True,
        encoding=UTF8_ENCODING,
    )
    if completed.returncode == 0:
        return None
    return completed.stderr.strip() or completed.stdout.strip() or f"exit {completed.returncode}"


def verify_packed_manifest_surfaces(from_package_root: Path) -> list[str]:
    """Pack the package and list manifest surfaces missing from the tarball.

    Args:
        from_package_root: Package directory to pack and verify.

    Returns:
        Missing surface names, empty when the tarball is complete.
    """
    all_manifest_entries = load_installable_surfaces_manifest(
        from_package_root=from_package_root
    )
    with tempfile.TemporaryDirectory() as temporary_directory:
        tarball_path = run_npm_pack(
            into_directory=Path(temporary_directory),
            from_package_root=from_package_root,
        )
        all_members = list_npm_pack_tarball_members(from_tarball_path=tarball_path)
    return missing_manifest_surfaces_in_tarball(all_manifest_entries, all_members)


def run_all_installable_package_checks(
    from_package_root: Path,
    from_repository_root: Path,
) -> list[str]:
    """Run pack, git-index, and smoke checks; return human-readable failures.

    Args:
        from_package_root: Package directory under verification.
        from_repository_root: Repository root for git index checks.

    Returns:
        Failure lines; empty when every check passes.
    """
    all_failures: list[str] = []
    missing_surfaces = verify_packed_manifest_surfaces(from_package_root=from_package_root)
    if missing_surfaces:
        all_failures.append(MISSING_MANIFEST_SURFACES_HEADER)
        all_failures.extend(missing_surfaces)

    all_hook_scripts = load_hook_python_script_paths(from_package_root=from_package_root)
    missing_hooks = untracked_or_missing_hook_scripts(
        all_package_relative_scripts=all_hook_scripts,
        from_package_root=from_package_root,
        from_repository_root=from_repository_root,
    )
    if missing_hooks:
        all_failures.append(UNTRACKED_HOOK_SCRIPTS_HEADER)
        all_failures.extend(missing_hooks)

    compile_failures = smoke_compile_python_scripts(
        all_package_relative_scripts=all_hook_scripts,
        from_package_root=from_package_root,
    )
    if compile_failures:
        all_failures.append(SMOKE_COMPILE_FAILURES_HEADER)
        all_failures.extend(compile_failures)

    entrypoint_failure = smoke_check_install_entrypoint(from_package_root=from_package_root)
    if entrypoint_failure is not None:
        all_failures.append(INSTALL_ENTRYPOINT_SMOKE_FAILURE_HEADER)
        all_failures.append(entrypoint_failure)
    return all_failures


def main() -> int:
    """CLI entry: verify pack surfaces, hook scripts, and smoke checks.

    Returns:
        ``0`` when every check passes, ``1`` when any check fails.
    """
    all_failures = run_all_installable_package_checks(
        from_package_root=package_root_path(),
        from_repository_root=repository_root_path(),
    )
    if all_failures:
        print(NEWLINE_JOIN_SEPARATOR.join(all_failures))
        return EXIT_CODE_FAILURE
    print(VERIFICATION_PASSED_MESSAGE)
    return EXIT_CODE_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
