"""Validate exact Claude instruction imports and regular Git file modes."""

from __future__ import annotations

import argparse
import logging
import os
import stat
import subprocess
import sys
from pathlib import Path

from typing import NamedTuple

from subprocess_window_access import hidden_window_creation_flags

_hooks_directory = str(Path(__file__).resolve().parents[1] / "hooks")
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from followup_ledger import FollowupFinding, record_followup_finding
from hooks_constants.followup_ledger_constants import SEVERITY_BREAKING, SEVERITY_SMELL

FILENAME_RULE_ID = "instruction-filename"
REGULAR_FILE_RULE_ID = "instruction-regular-file"
GIT_MODE_RULE_ID = "instruction-git-mode"
MISSING_AGENTS_RULE_ID = "instruction-missing-agents"
IMPORT_TEXT_RULE_ID = "instruction-import-text"

SEVERITY_BY_RULE_ID = {
    FILENAME_RULE_ID: SEVERITY_SMELL,
    REGULAR_FILE_RULE_ID: SEVERITY_BREAKING,
    GIT_MODE_RULE_ID: SEVERITY_SMELL,
    MISSING_AGENTS_RULE_ID: SEVERITY_BREAKING,
    IMPORT_TEXT_RULE_ID: SEVERITY_BREAKING,
}

GATE_PASSED_EXIT_CODE = 0
GATE_FAILED_EXIT_CODE = 1
RECORDED_SMELL_TEMPLATE = "recorded for follow-up: %s"


class InstructionFinding(NamedTuple):
    """One instruction-pair finding and the severity that decides the gate.

    Attributes:
        rule_id: Stable identifier of the check that raised the finding.
        file_path: Repository-relative path the finding names.
        message: The text a reader acts on.
        severity: Either SEVERITY_BREAKING or SEVERITY_SMELL.
    """

    rule_id: str
    file_path: str
    message: str
    severity: str


def _finding(rule_id: str, relative_path: Path, message: str) -> InstructionFinding:
    """Build one finding carrying the severity its rule identifier declares.

    Args:
        rule_id: The check's stable identifier.
        relative_path: Repository-relative path the finding names.
        message: The text a reader acts on.

    Returns:
        The finding with its declared severity attached.
    """
    return InstructionFinding(
        rule_id, relative_path.as_posix(), message, SEVERITY_BY_RULE_ID[rule_id]
    )


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
            creationflags=hidden_window_creation_flags(),
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


def all_instruction_findings(repository_root: Path) -> tuple[InstructionFinding, ...]:
    """Collect every instruction-pair finding with the severity that decides the gate.

    Args:
        repository_root: Repository directory containing the Git metadata.

    Returns:
        Every finding in discovery order, each carrying its rule identifier,
        the repository-relative path it names, its text, and its severity.
    """
    repository_root = repository_root.resolve()
    all_findings: list[InstructionFinding] = []
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
            all_findings.append(
                _finding(
                    FILENAME_RULE_ID,
                    relative_path,
                    f"Use the canonical filename: {relative_path}",
                )
            )
        if not _is_regular_file(each_instruction_path):
            all_findings.append(
                _finding(
                    REGULAR_FILE_RULE_ID,
                    relative_path,
                    f"Use a regular file: {relative_path}",
                )
            )
        if tracked_modes != {regular_git_file_mode}:
            all_findings.append(
                _finding(
                    GIT_MODE_RULE_ID,
                    relative_path,
                    f"Commit the instruction file with Git mode 100644: {relative_path}",
                )
            )

    for each_claude_path in all_claude_paths:
        relative_claude_path = each_claude_path.relative_to(repository_root)
        each_agents_path = _find_nearest_agents_path(
            each_claude_path, repository_root, agents_by_directory
        )
        if each_agents_path is None:
            all_findings.append(
                _finding(
                    MISSING_AGENTS_RULE_ID,
                    relative_claude_path,
                    f"Add the nearest governing AGENTS.md: {relative_claude_path}",
                )
            )
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
            all_findings.append(
                _finding(
                    IMPORT_TEXT_RULE_ID,
                    relative_claude_path,
                    f"Make {relative_claude_path} exactly import "
                    f"@{relative_import_path} for {relative_agents_path}",
                )
            )

    return tuple(all_findings)


def validate_repository(repository_root: Path) -> list[str]:
    """Validate instruction filenames, modes, and exact Claude imports.

    Args:
        repository_root: Repository directory containing the Git metadata.

    Returns:
        Human-readable validation errors, with an empty list for a valid tree.
    """
    return [
        each_finding.message
        for each_finding in all_instruction_findings(repository_root)
    ]


def run_gate(repository_root: Path) -> int:
    """Report breaking findings, record smells, and return the gate exit code.

    A breaking finding means the instruction files do not load as written, so
    the gate fails. A smell is recorded in the repository's follow-up ledger
    and leaves the gate passing, so a later pull request resolves it.

    Args:
        repository_root: Repository directory containing the Git metadata.

    Returns:
        GATE_FAILED_EXIT_CODE when any breaking finding is present, otherwise
        GATE_PASSED_EXIT_CODE.
    """
    resolved_root = repository_root.resolve()
    all_findings = all_instruction_findings(resolved_root)
    all_breaking_messages: list[str] = []

    for each_finding in all_findings:
        if each_finding.severity == SEVERITY_BREAKING:
            all_breaking_messages.append(each_finding.message)
            continue
        record_followup_finding(
            resolved_root,
            FollowupFinding(
                each_finding.rule_id, each_finding.file_path, each_finding.message
            ),
        )
        logger.warning(RECORDED_SMELL_TEMPLATE, each_finding.message)

    for each_message in all_breaking_messages:
        logger.error("%s", each_message)

    if all_breaking_messages:
        return GATE_FAILED_EXIT_CODE
    return GATE_PASSED_EXIT_CODE


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
    return run_gate(parsed_arguments.repository_root)


if __name__ == "__main__":
    raise SystemExit(_main())
