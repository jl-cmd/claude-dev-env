"""Append-only ledger of non-breaking findings awaiting a follow-up fix.

A gate that finds a breaking defect stops the commit, the push, or the tool
call. A gate that finds a non-breaking smell records the finding here and lets
the work proceed. ``cde followup`` reads the ledger and briefs the agent that
fixes the recorded smells in their own pull request.

Every write is fail-safe. A ledger that cannot be created or appended to leaves
the calling gate's decision unchanged, so recording a finding never becomes a
new way for a gate to fail.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import NamedTuple

_hooks_directory = str(Path(__file__).resolve().parent)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from hooks_constants.followup_ledger_constants import (
    FILE_PATH_KEY,
    ALL_FOLLOWUP_LEDGER_PATH_SEGMENTS,
    LEDGER_APPEND_MODE,
    LEDGER_ENCODING,
    MESSAGE_KEY,
    RULE_ID_KEY,
)


class FollowupFinding(NamedTuple):
    """One non-breaking finding a later pull request resolves.

    Attributes:
        rule_id: Stable identifier of the check that raised the finding.
        file_path: Repository-relative path the finding names.
        message: The text a reader acts on.
    """

    rule_id: str
    file_path: str
    message: str


def followup_ledger_path(repository_root: Path) -> Path:
    """Return the ledger path for one repository.

    Args:
        repository_root: The repository whose ledger to address.

    Returns:
        The absolute path of that repository's follow-up ledger.
    """
    return repository_root.joinpath(*ALL_FOLLOWUP_LEDGER_PATH_SEGMENTS)


def record_followup_finding(repository_root: Path, finding: FollowupFinding) -> None:
    """Append one finding to the repository's ledger, once.

    A finding already present in the ledger is left alone, so a gate that runs
    on every commit records a standing smell a single time. Every filesystem
    error is swallowed, so a ledger failure leaves the caller's gate decision
    unchanged.

    Args:
        repository_root: The repository whose ledger receives the finding.
        finding: The non-breaking finding to record.
    """
    if finding in all_recorded_findings(repository_root):
        return

    ledger_path = followup_ledger_path(repository_root)
    record_text = json.dumps(
        {
            RULE_ID_KEY: finding.rule_id,
            FILE_PATH_KEY: finding.file_path,
            MESSAGE_KEY: finding.message,
        }
    )
    try:
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open(LEDGER_APPEND_MODE, encoding=LEDGER_ENCODING) as ledger_file:
            ledger_file.write(record_text + "\n")
    except OSError:
        return


def all_recorded_findings(repository_root: Path) -> tuple[FollowupFinding, ...]:
    """Return every finding the repository's ledger holds, in record order.

    An absent or unreadable ledger reads as empty, and a line that does not
    parse into a complete record is skipped, so one damaged line never hides
    the findings around it.

    Args:
        repository_root: The repository whose ledger to read.

    Returns:
        The recorded findings, in the order they were appended.
    """
    ledger_path = followup_ledger_path(repository_root)
    try:
        ledger_text = ledger_path.read_text(encoding=LEDGER_ENCODING)
    except (OSError, UnicodeError):
        return ()

    all_findings: list[FollowupFinding] = []
    for each_line in ledger_text.splitlines():
        each_finding = _finding_from_line(each_line)
        if each_finding is not None:
            all_findings.append(each_finding)
    return tuple(all_findings)


def _finding_from_line(ledger_line: str) -> FollowupFinding | None:
    """Parse one ledger line into a finding.

    Args:
        ledger_line: One line of the ledger file.

    Returns:
        The parsed finding, or None when the line carries no complete record.
    """
    stripped_line = ledger_line.strip()
    if not stripped_line:
        return None
    try:
        parsed_record = json.loads(stripped_line)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed_record, dict):
        return None
    rule_id = parsed_record.get(RULE_ID_KEY)
    file_path = parsed_record.get(FILE_PATH_KEY)
    message = parsed_record.get(MESSAGE_KEY)
    if not isinstance(rule_id, str) or not isinstance(file_path, str):
        return None
    if not isinstance(message, str):
        return None
    return FollowupFinding(rule_id, file_path, message)
