"""Validate exact Claude instruction imports and regular Git file modes."""

from __future__ import annotations

import argparse
import logging
import os
import stat
import subprocess
from pathlib import Path

git_directory_name = ".git"
git_listing_commands = (
    (("git", "ls-files", "--stage", "-z"), True),
    (("git", "ls-files", "--others", "--exclude-standard", "-z"), False),
)
ascii_encoding_name = "ascii"
utf8_encoding_name = "utf-8"
regular_git_file_mode = "100644"
canonical_instruction_names = frozenset(("AGENTS.md", "CLAUDE.md"))
logger = logging.getLogger(__name__)


def _read_git_paths_and_modes(
    repository_root: Path,
) -> tuple[set[Path], dict[Path, set[str]]]:
    all_git_paths: set[Path] = set()
    modes_by_path: dict[Path, set[str]] = {}
    for each_command, each_has_git_mode in git_listing_commands:
        completed_process = subprocess.run(
            each_command,
            cwd=repository_root,
            capture_output=True,
            check=True,
        )
        for each_record in completed_process.stdout.split(b"\0"):
            if not each_record:
                continue
            if each_has_git_mode:
                each_header, each_path_bytes = each_record.split(b"\t", 1)
                each_mode = each_header.split(b" ", 1)[0].decode(ascii_encoding_name)
                each_path = repository_root / Path(os.fsdecode(each_path_bytes))
                modes_by_path.setdefault(each_path, set()).add(each_mode)
            else:
                each_path = repository_root / Path(os.fsdecode(each_record))
            all_git_paths.add(each_path)
    return all_git_paths, modes_by_path


def _discover_named_files(
    repository_root: Path,
    all_git_paths: set[Path],
    expected_name: str,
) -> list[Path]:
    all_candidate_paths = set(all_git_paths)
    all_candidate_paths.update(repository_root.rglob("*"))
    return sorted(
        each_path
        for each_path in all_candidate_paths
        if git_directory_name not in each_path.parts
        and each_path.name.casefold() == expected_name.casefold()
    )


def _find_nearest_agents_path(
    claude_path: Path,
    repository_root: Path,
    agents_by_directory: dict[Path, Path],
) -> Path | None:
    each_directory = claude_path.parent
    while True:
        each_agents_path = agents_by_directory.get(each_directory)
        if each_agents_path is not None:
            return each_agents_path
        if each_directory == repository_root:
            return None
        each_directory = each_directory.parent


def _relative_import_path(claude_path: Path, agents_path: Path) -> str:
    return Path(os.path.relpath(agents_path, claude_path.parent)).as_posix()


def _expected_import_text(claude_path: Path, agents_path: Path) -> bytes:
    return f"@{_relative_import_path(claude_path, agents_path)}\n".encode(
        utf8_encoding_name
    )


def _is_regular_file(each_path: Path) -> bool:
    try:
        return stat.S_ISREG(each_path.lstat().st_mode)
    except FileNotFoundError:
        return False


def validate_repository(repository_root: Path) -> list[str]:
    """Validate instruction filenames, modes, and exact Claude imports.

    Args:
        repository_root: Repository directory containing the Git metadata.

    Returns:
        Human-readable validation errors, with an empty list for a valid tree.
    """
    repository_root = repository_root.resolve()
    all_errors: list[str] = []
    all_git_paths, modes_by_path = _read_git_paths_and_modes(repository_root)
    all_agents_paths = _discover_named_files(
        repository_root, all_git_paths, "AGENTS.md"
    )
    all_claude_paths = _discover_named_files(
        repository_root, all_git_paths, "CLAUDE.md"
    )
    agents_by_directory = {
        each_path.parent: each_path
        for each_path in all_agents_paths
        if each_path.name == "AGENTS.md"
    }

    for each_instruction_path in (*all_agents_paths, *all_claude_paths):
        relative_path = each_instruction_path.relative_to(repository_root)
        tracked_modes = modes_by_path.get(each_instruction_path, set())
        if each_instruction_path.name not in canonical_instruction_names:
            all_errors.append(f"Use the canonical filename: {relative_path}")
        if not _is_regular_file(each_instruction_path):
            all_errors.append(f"Use a regular file: {relative_path}")
        if tracked_modes != {regular_git_file_mode}:
            all_errors.append(
                f"Commit the instruction file with Git mode 100644: {relative_path}"
            )

    for each_claude_path in all_claude_paths:
        relative_claude_path = each_claude_path.relative_to(repository_root)
        each_agents_path = _find_nearest_agents_path(
            each_claude_path, repository_root, agents_by_directory
        )
        if each_agents_path is None:
            all_errors.append(f"Add the nearest governing AGENTS.md: {relative_claude_path}")
            continue
        if not _is_regular_file(each_claude_path):
            continue
        expected_bytes = _expected_import_text(each_claude_path, each_agents_path)
        actual_bytes = each_claude_path.read_bytes()
        if actual_bytes != expected_bytes:
            relative_import_path = _relative_import_path(
                each_claude_path, each_agents_path
            )
            relative_agents_path = each_agents_path.relative_to(repository_root)
            all_errors.append(
                f"Make {relative_claude_path} exactly import "
                f"@{relative_import_path} for {relative_agents_path}"
            )

    return all_errors


def _parse_arguments() -> argparse.Namespace:
    argument_parser = argparse.ArgumentParser(
        description="Validate exact CLAUDE.md imports and regular AGENTS.md files."
    )
    argument_parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root containing the .git directory.",
    )
    return argument_parser.parse_args()


def _main() -> int:
    parsed_arguments = _parse_arguments()
    repository_root = parsed_arguments.repository_root.resolve()
    all_errors = validate_repository(repository_root)
    if all_errors:
        for each_error in all_errors:
            logger.error("%s", each_error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
