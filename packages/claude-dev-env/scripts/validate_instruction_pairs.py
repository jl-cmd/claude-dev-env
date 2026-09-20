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

from dev_env_scripts_constants.followup_constants import (
    FILENAME_RULE_ID,
    GATE_FAILED_EXIT_CODE,
    GATE_PASSED_EXIT_CODE,
    GIT_MODE_RULE_ID,
    IMPORT_TEXT_RULE_ID,
    MISSING_AGENTS_RULE_ID,
    RECORDED_SMELL_TEMPLATE,
    REGULAR_FILE_RULE_ID,
    SEVERITY_BY_RULE_ID,
)
from followup_ledger import FollowupFinding, record_followup_finding
from hooks_constants.followup_ledger_constants import SEVERITY_BREAKING

class InstructionFinding(NamedTuple):
    """One instruction-pair finding and the severity that decides the gate.

    Attributes:
        rule_id: Stable identifier of the check that raised the finding.
        file_path: Repository-relative path the finding names.
        message: The text a reader acts on.
        severity: The severity SEVERITY_BY_RULE_ID declares for rule_id.
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


def _all_file_check_rows(
    instruction_path: Path, all_tracked_modes: set[str]
) -> tuple[tuple[str, bool, str], ...]:
    """Pair each per-file rule with whether it failed and the text it reports.

    Args:
        instruction_path: The AGENTS.md or CLAUDE.md to check.
        all_tracked_modes: Committed Git modes this path carries.

    Returns:
        One row per per-file rule, each holding its rule identifier, whether
        the check failed, and its message prefix.
    """
    return (
        (
            FILENAME_RULE_ID,
            instruction_path.name not in canonical_instruction_names,
            "Use the canonical filename",
        ),
        (
            REGULAR_FILE_RULE_ID,
            not _is_regular_file(instruction_path),
            "Use a regular file",
        ),
        (
            GIT_MODE_RULE_ID,
            all_tracked_modes != {regular_git_file_mode},
            "Commit the instruction file with Git mode 100644",
        ),
    )


def _instruction_file_findings(
    instruction_path: Path,
    repository_root: Path,
    all_tracked_modes: set[str],
) -> list[InstructionFinding]:
    """Check one instruction file's name, kind, and committed Git mode.

    Args:
        instruction_path: The AGENTS.md or CLAUDE.md to check.
        repository_root: The resolved repository root.
        all_tracked_modes: Committed Git modes this path carries.

    Returns:
        Every finding these three checks raise for this file.
    """
    relative_path = instruction_path.relative_to(repository_root)
    return [
        _finding(each_rule_id, relative_path, f"{each_text}: {relative_path}")
        for each_rule_id, each_check_failed, each_text in _all_file_check_rows(
            instruction_path, all_tracked_modes
        )
        if each_check_failed
    ]


def _import_text_finding(
    claude_path: Path, agents_path: Path, repository_root: Path
) -> InstructionFinding | None:
    """Compare one CLAUDE.md against the import text its AGENTS.md requires.

    Args:
        claude_path: The CLAUDE.md to read.
        agents_path: The AGENTS.md it must import.
        repository_root: The resolved repository root.

    Returns:
        The finding, or None when the import text is exact.
    """
    if not _is_regular_file(claude_path):
        return None
    if claude_path.read_bytes() == _expected_import_text(claude_path, agents_path):
        return None
    relative_claude_path = claude_path.relative_to(repository_root)
    relative_import_path = _relative_import_path(claude_path, agents_path)
    relative_agents_path = agents_path.relative_to(repository_root)
    return _finding(
        IMPORT_TEXT_RULE_ID,
        relative_claude_path,
        f"Make {relative_claude_path} exactly import "
        f"@{relative_import_path} for {relative_agents_path}",
    )


def _import_finding(
    claude_path: Path,
    repository_root: Path,
    agents_by_directory: dict[Path, Path],
) -> InstructionFinding | None:
    """Check one CLAUDE.md against the AGENTS.md it must import.

    Args:
        claude_path: The CLAUDE.md to check.
        repository_root: The resolved repository root.
        agents_by_directory: Discovered AGENTS.md paths keyed by directory.

    Returns:
        The finding this file raises, or None when its import text is exact.
    """
    agents_path = _find_nearest_agents_path(
        claude_path, repository_root, agents_by_directory
    )
    if agents_path is None:
        relative_claude_path = claude_path.relative_to(repository_root)
        return _finding(
            MISSING_AGENTS_RULE_ID,
            relative_claude_path,
            f"Add the nearest governing AGENTS.md: {relative_claude_path}",
        )
    return _import_text_finding(claude_path, agents_path, repository_root)


def _agents_paths_by_directory(all_agents_paths: list[Path]) -> dict[Path, Path]:
    """Key each discovered AGENTS.md by the directory that holds it.

    Args:
        all_agents_paths: Every AGENTS.md discovered in the tree.

    Returns:
        The AGENTS.md path for each directory that holds one.
    """
    return {
        each_path.parent: each_path
        for each_path in all_agents_paths
        if each_path.name == "AGENTS.md"
    }


def _all_file_findings(
    all_instruction_paths: tuple[Path, ...],
    repository_root: Path,
    modes_by_path: dict[Path, set[str]],
) -> list[InstructionFinding]:
    """Run the per-file checks over every discovered instruction file.

    Args:
        all_instruction_paths: Every AGENTS.md and CLAUDE.md discovered.
        repository_root: The resolved repository root.
        modes_by_path: Committed Git modes keyed by absolute path.

    Returns:
        Every per-file finding, in discovery order.
    """
    all_findings: list[InstructionFinding] = []
    for each_instruction_path in all_instruction_paths:
        all_findings.extend(
            _instruction_file_findings(
                each_instruction_path,
                repository_root,
                modes_by_path.get(each_instruction_path, set()),
            )
        )
    return all_findings


def all_instruction_findings(repository_root: Path) -> tuple[InstructionFinding, ...]:
    """Collect every instruction-pair finding with the severity that decides the gate.

    Args:
        repository_root: Repository directory containing the Git metadata.

    Returns:
        Every finding in discovery order, each carrying its rule identifier,
        the repository-relative path it names, its text, and its severity.
    """
    repository_root = repository_root.resolve()
    all_git_paths, modes_by_path = _read_git_paths_and_modes(repository_root)
    all_agents_paths = _discover_named_files(repository_root, all_git_paths, "AGENTS.md")
    all_claude_paths = _discover_named_files(repository_root, all_git_paths, "CLAUDE.md")
    agents_by_directory = _agents_paths_by_directory(all_agents_paths)

    all_findings = _all_file_findings(
        (*all_agents_paths, *all_claude_paths), repository_root, modes_by_path
    )
    for each_claude_path in all_claude_paths:
        each_finding = _import_finding(
            each_claude_path, repository_root, agents_by_directory
        )
        if each_finding is not None:
            all_findings.append(each_finding)
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


def _record_smell(repository_root: Path, finding: InstructionFinding) -> None:
    """Record one smell finding in the repository's follow-up ledger.

    Args:
        repository_root: The repository whose ledger receives the finding.
        finding: The non-breaking finding to record.
    """
    record_followup_finding(
        repository_root,
        FollowupFinding(finding.rule_id, finding.file_path, finding.message),
    )
    logger.warning(RECORDED_SMELL_TEMPLATE, finding.message)


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
    all_breaking_messages: list[str] = []

    for each_finding in all_instruction_findings(resolved_root):
        if each_finding.severity == SEVERITY_BREAKING:
            all_breaking_messages.append(each_finding.message)
            continue
        _record_smell(resolved_root, each_finding)

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
