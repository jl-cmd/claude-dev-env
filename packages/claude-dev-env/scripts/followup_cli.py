#!/usr/bin/env python3
"""Read and brief the follow-up ledger of non-breaking findings.

A gate that finds a non-breaking smell records it rather than stopping the
work. This command reads those records back.

::

    $ cde followup list
    instruction-git-mode    CLAUDE.md    Commit the instruction file with Git mode 100644

``list`` names what is outstanding, ``ingest`` adds the diagnostics from a
policy-lint JSON report, ``brief`` writes the task an agent works from, and
``clear`` empties the ledger once the follow-up pull request carries the
fixes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

from dev_env_scripts_constants.followup_constants import (
    ABSENT_LOCATION_PATH,
    ALL_COMMAND_NAMES,
    BRIEF_COMMAND_NAME,
    BRIEF_FINDING_TEMPLATE,
    BRIEF_FOOTER_TEMPLATE,
    BRIEF_HEADER,
    DIAGNOSTIC_LOCATION_KEY,
    DIAGNOSTIC_MESSAGE_KEY,
    DIAGNOSTIC_RULE_ID_KEY,
    DIAGNOSTICS_KEY,
    EMPTY_LEDGER_MESSAGE,
    INGEST_COMMAND_NAME,
    INVALID_INPUT_EXIT_CODE,
    LINE_SEPARATOR,
    LIST_COMMAND_NAME,
    LIST_FINDING_TEMPLATE,
    LOCATION_PATH_KEY,
    SUCCESS_EXIT_CODE,
    UNREADABLE_REPORT_TEMPLATE,
    USAGE_TEXT,
)

_hooks_directory = str(Path(__file__).resolve().parents[1] / "hooks")
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from followup_ledger import (
    FollowupFinding,
    all_recorded_findings,
    followup_ledger_path,
    record_followup_finding,
)


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
        stdout.write(EMPTY_LEDGER_MESSAGE + LINE_SEPARATOR)
        return SUCCESS_EXIT_CODE
    for each_finding in all_findings:
        stdout.write(_formatted_finding(LIST_FINDING_TEMPLATE, each_finding) + LINE_SEPARATOR)
    return SUCCESS_EXIT_CODE


def _formatted_finding(finding_template: str, finding: FollowupFinding) -> str:
    """Fill one template with a finding's fields.

    Args:
        finding_template: A template naming rule_id, file_path, and message.
        finding: The finding whose fields fill the template.

    Returns:
        The filled line.
    """
    return finding_template.format(
        rule_id=finding.rule_id,
        file_path=finding.file_path,
        message=finding.message,
    )


def _parsed_lint_report(report_path: Path) -> dict[str, object] | None:
    """Read one policy-lint JSON report into a mapping.

    Args:
        report_path: Path of the JSON report to read.

    Returns:
        The report mapping, or None when the file cannot be read as one.
    """
    try:
        report_text = report_path.read_text(encoding="utf-8")
        parsed_report = json.loads(report_text)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed_report, dict):
        return None
    return parsed_report


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
        stdout.write(USAGE_TEXT + LINE_SEPARATOR)
        return INVALID_INPUT_EXIT_CODE
    parsed_report = _parsed_lint_report(report_path)
    if parsed_report is None:
        stdout.write(
            UNREADABLE_REPORT_TEMPLATE.format(report_path=report_path) + LINE_SEPARATOR
        )
        return INVALID_INPUT_EXIT_CODE

    all_diagnostics = parsed_report.get(DIAGNOSTICS_KEY, [])
    if not isinstance(all_diagnostics, list):
        return SUCCESS_EXIT_CODE
    for each_diagnostic in all_diagnostics:
        each_finding = _finding_from_diagnostic(each_diagnostic)
        if each_finding is not None:
            record_followup_finding(repository_root, each_finding)
    return SUCCESS_EXIT_CODE


def _finding_from_diagnostic(diagnostic_by_key: object) -> FollowupFinding | None:
    """Convert one lint diagnostic into a ledger finding.

    Args:
        diagnostic_by_key: One entry of the report's diagnostics list.

    Returns:
        The finding, or None when the entry carries no rule identifier and
        message.
    """
    if not isinstance(diagnostic_by_key, dict):
        return None
    rule_id = diagnostic_by_key.get(DIAGNOSTIC_RULE_ID_KEY)
    message = diagnostic_by_key.get(DIAGNOSTIC_MESSAGE_KEY)
    if not isinstance(rule_id, str) or not isinstance(message, str):
        return None
    return FollowupFinding(rule_id, _diagnostic_file_path(diagnostic_by_key), message)


def _diagnostic_file_path(diagnostic_by_key: dict[str, object]) -> str:
    """Return the path a diagnostic names, or an empty string.

    Args:
        diagnostic_by_key: One entry of the report's diagnostics list.

    Returns:
        The diagnostic's path, or ABSENT_LOCATION_PATH when it names none.
    """
    location_by_key = diagnostic_by_key.get(DIAGNOSTIC_LOCATION_KEY)
    if not isinstance(location_by_key, dict):
        return ABSENT_LOCATION_PATH
    location_path = location_by_key.get(LOCATION_PATH_KEY)
    if not isinstance(location_path, str):
        return ABSENT_LOCATION_PATH
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
        stdout.write(EMPTY_LEDGER_MESSAGE + LINE_SEPARATOR)
        return SUCCESS_EXIT_CODE

    all_lines = [BRIEF_HEADER, ""]
    all_lines.extend(
        _formatted_finding(BRIEF_FINDING_TEMPLATE, each_finding)
        for each_finding in all_findings
    )
    all_lines.append("")
    all_lines.append(BRIEF_FOOTER_TEMPLATE.format(command_path=Path(__file__).resolve()))
    stdout.write(LINE_SEPARATOR.join(all_lines) + LINE_SEPARATOR)
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
        stdout.write(USAGE_TEXT + LINE_SEPARATOR)
        return INVALID_INPUT_EXIT_CODE

    repository_root = parsed_arguments.repository_root.resolve()
    if parsed_arguments.command == LIST_COMMAND_NAME:
        return _run_list(repository_root, stdout)
    if parsed_arguments.command == INGEST_COMMAND_NAME:
        raw_report_path = parsed_arguments.report_path
        report_path = None if raw_report_path is None else Path(raw_report_path)
        return _run_ingest(repository_root, report_path, stdout)
    if parsed_arguments.command == BRIEF_COMMAND_NAME:
        return _run_brief(repository_root, stdout)
    return _run_clear(repository_root)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
