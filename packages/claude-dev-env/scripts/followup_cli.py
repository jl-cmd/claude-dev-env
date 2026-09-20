#!/usr/bin/env python3
"""Read and brief the follow-up ledger of non-breaking findings.

A gate that finds a non-breaking smell records it rather than stopping the
work. This command reads those records back. ``list`` names what is
outstanding, ``ingest`` adds the diagnostics from a policy-lint JSON report,
``brief`` writes the task an agent works from, and ``clear`` empties the
ledger once the follow-up pull request carries the fixes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

_hooks_directory = str(Path(__file__).resolve().parents[1] / "hooks")
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from followup_ledger import (
    FollowupFinding,
    all_recorded_findings,
    followup_ledger_path,
    record_followup_finding,
)

LIST_COMMAND_NAME = "list"
INGEST_COMMAND_NAME = "ingest"
BRIEF_COMMAND_NAME = "brief"
CLEAR_COMMAND_NAME = "clear"
ALL_COMMAND_NAMES = (
    LIST_COMMAND_NAME,
    INGEST_COMMAND_NAME,
    BRIEF_COMMAND_NAME,
    CLEAR_COMMAND_NAME,
)

SUCCESS_EXIT_CODE = 0
INVALID_INPUT_EXIT_CODE = 2

DIAGNOSTICS_KEY = "diagnostics"
DIAGNOSTIC_RULE_ID_KEY = "rule_id"
DIAGNOSTIC_MESSAGE_KEY = "message"
DIAGNOSTIC_LOCATION_KEY = "location"
LOCATION_PATH_KEY = "path"

EMPTY_LEDGER_MESSAGE = "no follow-ups recorded"
UNREADABLE_REPORT_TEMPLATE = "cannot read the lint report: {report_path}"
USAGE_TEXT = (
    "Usage: followup_cli.py <list|ingest|brief|clear> [--repository-root PATH]\n"
    "  list              Name every recorded follow-up\n"
    "  ingest REPORT     Record every diagnostic in a policy-lint JSON report\n"
    "  brief             Write the task an agent works the follow-ups from\n"
    "  clear             Empty the ledger"
)

BRIEF_HEADER = (
    "Fix every finding below in one change, then open a draft pull request "
    "for it. Each finding is non-breaking, so the change that raised it "
    "already shipped. Keep the fixes mechanical, touch no behavior, and run "
    "the repository's own checks before pushing."
)
BRIEF_FINDING_TEMPLATE = "- [{rule_id}] {file_path}: {message}"
BRIEF_FOOTER_TEMPLATE = (
    "Once the pull request is open, empty the ledger with "
    "`python {command_path} clear`."
)
LIST_FINDING_TEMPLATE = "{rule_id}\t{file_path}\t{message}"


def _parse_arguments(all_arguments: list[str]) -> argparse.Namespace | None:
    """Parse the command arguments.

    Args:
        all_arguments: The argument list after the program name.

    Returns:
        The parsed arguments, or None when the command name is unknown.
    """
    if not all_arguments or all_arguments[0] not in ALL_COMMAND_NAMES:
        return None
    argument_parser = argparse.ArgumentParser(add_help=False)
    argument_parser.add_argument("command", choices=ALL_COMMAND_NAMES)
    argument_parser.add_argument("report_path", nargs="?", default=None)
    argument_parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    return argument_parser.parse_args(all_arguments)


def _run_list(repository_root: Path, stdout: TextIO) -> int:
    """Write one line per recorded finding.

    Args:
        repository_root: The repository whose ledger to read.
        stdout: The stream the lines go to.

    Returns:
        SUCCESS_EXIT_CODE.
    """
    all_findings = all_recorded_findings(repository_root)
    if not all_findings:
        stdout.write(EMPTY_LEDGER_MESSAGE + "\n")
        return SUCCESS_EXIT_CODE
    for each_finding in all_findings:
        stdout.write(
            LIST_FINDING_TEMPLATE.format(
                rule_id=each_finding.rule_id,
                file_path=each_finding.file_path,
                message=each_finding.message,
            )
            + "\n"
        )
    return SUCCESS_EXIT_CODE


def _run_ingest(repository_root: Path, report_path: Path | None, stdout: TextIO) -> int:
    """Record every diagnostic a policy-lint JSON report carries.

    Args:
        repository_root: The repository whose ledger receives the findings.
        report_path: Path of the JSON report to read.
        stdout: The stream messages go to.

    Returns:
        SUCCESS_EXIT_CODE once the report is recorded, or
        INVALID_INPUT_EXIT_CODE when the report cannot be read.
    """
    if report_path is None:
        stdout.write(USAGE_TEXT + "\n")
        return INVALID_INPUT_EXIT_CODE
    try:
        report_text = report_path.read_text(encoding="utf-8")
        parsed_report = json.loads(report_text)
    except (OSError, UnicodeError, json.JSONDecodeError):
        stdout.write(UNREADABLE_REPORT_TEMPLATE.format(report_path=report_path) + "\n")
        return INVALID_INPUT_EXIT_CODE
    if not isinstance(parsed_report, dict):
        stdout.write(UNREADABLE_REPORT_TEMPLATE.format(report_path=report_path) + "\n")
        return INVALID_INPUT_EXIT_CODE

    all_diagnostics = parsed_report.get(DIAGNOSTICS_KEY, [])
    if not isinstance(all_diagnostics, list):
        return SUCCESS_EXIT_CODE
    for each_diagnostic in all_diagnostics:
        each_finding = _finding_from_diagnostic(each_diagnostic)
        if each_finding is not None:
            record_followup_finding(repository_root, each_finding)
    return SUCCESS_EXIT_CODE


def _finding_from_diagnostic(diagnostic: object) -> FollowupFinding | None:
    """Convert one lint diagnostic into a ledger finding.

    Args:
        diagnostic: One entry of the report's diagnostics list.

    Returns:
        The finding, or None when the entry carries no rule identifier and
        message.
    """
    if not isinstance(diagnostic, dict):
        return None
    rule_id = diagnostic.get(DIAGNOSTIC_RULE_ID_KEY)
    message = diagnostic.get(DIAGNOSTIC_MESSAGE_KEY)
    if not isinstance(rule_id, str) or not isinstance(message, str):
        return None
    return FollowupFinding(rule_id, _diagnostic_file_path(diagnostic), message)


def _diagnostic_file_path(diagnostic: dict[str, object]) -> str:
    """Return the path a diagnostic names, or an empty string.

    Args:
        diagnostic: One entry of the report's diagnostics list.

    Returns:
        The diagnostic's path, or an empty string when it names none.
    """
    location = diagnostic.get(DIAGNOSTIC_LOCATION_KEY)
    if not isinstance(location, dict):
        return ""
    location_path = location.get(LOCATION_PATH_KEY)
    if not isinstance(location_path, str):
        return ""
    return location_path


def _run_brief(repository_root: Path, stdout: TextIO) -> int:
    """Write the task an agent works the recorded follow-ups from.

    Args:
        repository_root: The repository whose ledger to read.
        stdout: The stream the brief goes to.

    Returns:
        SUCCESS_EXIT_CODE.
    """
    all_findings = all_recorded_findings(repository_root)
    if not all_findings:
        stdout.write(EMPTY_LEDGER_MESSAGE + "\n")
        return SUCCESS_EXIT_CODE

    all_lines = [BRIEF_HEADER, ""]
    for each_finding in all_findings:
        all_lines.append(
            BRIEF_FINDING_TEMPLATE.format(
                rule_id=each_finding.rule_id,
                file_path=each_finding.file_path,
                message=each_finding.message,
            )
        )
    all_lines.append("")
    all_lines.append(
        BRIEF_FOOTER_TEMPLATE.format(command_path=Path(__file__).resolve())
    )
    stdout.write("\n".join(all_lines) + "\n")
    return SUCCESS_EXIT_CODE


def _run_clear(repository_root: Path) -> int:
    """Empty the repository's ledger.

    Args:
        repository_root: The repository whose ledger to empty.

    Returns:
        SUCCESS_EXIT_CODE.
    """
    try:
        followup_ledger_path(repository_root).unlink(missing_ok=True)
    except OSError:
        return SUCCESS_EXIT_CODE
    return SUCCESS_EXIT_CODE


def main(all_arguments: list[str], stdout: TextIO = sys.stdout) -> int:
    """Run one follow-up command.

    Args:
        all_arguments: The argument list after the program name.
        stdout: The stream every message goes to.

    Returns:
        The command's exit code.
    """
    parsed_arguments = _parse_arguments(all_arguments)
    if parsed_arguments is None:
        stdout.write(USAGE_TEXT + "\n")
        return INVALID_INPUT_EXIT_CODE

    repository_root = parsed_arguments.repository_root.resolve()
    if parsed_arguments.command == LIST_COMMAND_NAME:
        return _run_list(repository_root, stdout)
    if parsed_arguments.command == INGEST_COMMAND_NAME:
        report_path = (
            None
            if parsed_arguments.report_path is None
            else Path(parsed_arguments.report_path)
        )
        return _run_ingest(repository_root, report_path, stdout)
    if parsed_arguments.command == BRIEF_COMMAND_NAME:
        return _run_brief(repository_root, stdout)
    return _run_clear(repository_root)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
