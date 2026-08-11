"""Validate exact Claude instruction imports and regular Git file modes."""

from __future__ import annotations

import argparse
import os
import stat
import subprocess
import sys
from pathlib import Path


git_directory_name = ".git"
git_list_files_command = ("git", "ls-files", "--stage", "-z")
utf8_encoding_name = "utf-8"
ascii_encoding_name = "ascii"
regular_git_file_mode = "100644"
canonical_instruction_names = frozenset(("AGENTS.md", "CLAUDE.md"))


def _discover_named_files(repository_root: Path, expected_name: str) -> list[Path]:
    return sorted(
        each_path
        for each_path in repository_root.rglob("*")
        if git_directory_name not in each_path.parts
        and each_path.is_file()
        and each_path.name.casefold() == expected_name.casefold()
    )


def _read_git_modes(repository_root: Path) -> dict[Path, str]:
    completed_process = subprocess.run(
        git_list_files_command,
        cwd=repository_root,
        capture_output=True,
        check=True,
    )
    modes_by_path: dict[Path, str] = {}
    for each_record in completed_process.stdout.split(b"\0"):
        if not each_record:
            continue
        each_header, each_path_bytes = each_record.split(b"\t", 1)
        each_mode = each_header.split(b" ", 1)[0].decode(ascii_encoding_name)
        modes_by_path[Path(each_path_bytes.decode(utf8_encoding_name))] = each_mode
    return modes_by_path


def _find_nearest_agents_path(
    claude_path: Path, repository_root: Path
) -> Path | None:
    each_directory = claude_path.parent
    while True:
        each_agents_path = each_directory / "AGENTS.md"
        if each_agents_path.exists():
            return each_agents_path
        if each_directory == repository_root:
            return None
        each_directory = each_directory.parent


def _expected_import_text(claude_path: Path, agents_path: Path) -> bytes:
    relative_import_path = Path(
        os.path.relpath(agents_path, claude_path.parent)
    ).as_posix()
    return f"@{relative_import_path}\n".encode(utf8_encoding_name)


def validate_repository(repository_root: Path) -> list[str]:
    """Validate instruction filenames, modes, and exact Claude imports.

    Args:
        repository_root: Repository directory containing the Git metadata.

    Returns:
        Human-readable validation errors, with an empty list for a valid tree.
    """
    all_errors: list[str] = []
    modes_by_path = _read_git_modes(repository_root)
    all_agents_paths = _discover_named_files(repository_root, "AGENTS.md")
    all_claude_paths = _discover_named_files(repository_root, "CLAUDE.md")

    for each_instruction_path in (*all_agents_paths, *all_claude_paths):
        relative_path = each_instruction_path.relative_to(repository_root)
        tracked_mode = modes_by_path.get(relative_path)
        if each_instruction_path.name not in canonical_instruction_names:
            all_errors.append(f"Use the canonical filename: {relative_path}")
        if each_instruction_path.is_symlink() or not stat.S_ISREG(
            each_instruction_path.stat(follow_symlinks=False).st_mode
        ):
            all_errors.append(f"Use a regular file: {relative_path}")
        if tracked_mode != regular_git_file_mode:
            all_errors.append(
                f"Commit the instruction file with Git mode 100644: {relative_path}"
            )

    for each_claude_path in all_claude_paths:
        relative_claude_path = each_claude_path.relative_to(repository_root)
        each_agents_path = _find_nearest_agents_path(each_claude_path, repository_root)
        if each_agents_path is None:
            all_errors.append(f"Add the nearest governing AGENTS.md: {relative_claude_path}")
            continue
        expected_bytes = _expected_import_text(each_claude_path, each_agents_path)
        actual_bytes = each_claude_path.read_bytes()
        if actual_bytes != expected_bytes:
            relative_agents_path = each_agents_path.relative_to(repository_root)
            all_errors.append(
                f"Make {relative_claude_path} exactly import "
                f"@{each_agents_path.relative_to(each_claude_path.parent).as_posix()} "
                f"for {relative_agents_path}"
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
            sys.stderr.write(f"{each_error}\n")
        return 1
    sys.stdout.write(
        f"Validated {len(_discover_named_files(repository_root, 'CLAUDE.md'))} "
        "exact instruction imports.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
