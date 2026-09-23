"""Fail a GitHub event whose text or commits name a private organization.

The workflow ``private-terms.yml`` runs this on pull request, issue, comment,
review, and release events. Each finding names where the text sits and its
line number, never the name itself, so the public log stays clean::

    pull request body: Line 4 names a private organization. ...
    commit 3f2a9c1b77de identity: Line 1 names a private organization. ...
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from dev_env_scripts_constants.private_term_constants import (
    ALL_EVENT_TEXT_FIELDS,
    ALL_PRIVATE_TERM_DIGESTS,
    COMMIT_FIELD_SEPARATOR,
    COMMIT_FIELD_SPLIT_LIMIT,
    COMMIT_IDENTITY_PART,
    COMMIT_LABEL_TEMPLATE,
    COMMIT_LOG_FORMAT,
    COMMIT_MESSAGE_PART,
    COMMIT_RECORD_SEPARATOR,
    FINDING_LINE_TEMPLATE,
    GITHUB_NOREPLY_ADDRESS_PATTERN,
    MASKED_ADDRESS,
    PRIVATE_TERM_MESSAGE_TEMPLATE,
    PRIVATE_TERM_TEXT_ENCODING,
    SHORT_SHA_LENGTH,
)
from private_terms import private_term_line_numbers


def _findings_for(label: str, text: str) -> list[str]:
    return [
        FINDING_LINE_TEMPLATE.format(
            label=label,
            message=PRIVATE_TERM_MESSAGE_TEMPLATE.format(line_number=each_line_number),
        )
        for each_line_number in private_term_line_numbers(
            text, ALL_PRIVATE_TERM_DIGESTS
        )
    ]


def scan_event(event_path: Path) -> list[str]:
    """Return findings for the texts a GitHub event payload carries.

    Args:
        event_path: Path of the event JSON the runner writes.

    Returns:
        One finding per line that names a private organization.
    """
    event = json.loads(event_path.read_text(encoding=PRIVATE_TERM_TEXT_ENCODING))
    all_findings: list[str] = []
    for each_object_key, each_field, each_label in ALL_EVENT_TEXT_FIELDS:
        event_object = event.get(each_object_key)
        if not isinstance(event_object, dict):
            continue
        text = event_object.get(each_field)
        if isinstance(text, str):
            all_findings.extend(_findings_for(each_label, text))
    return all_findings


def _commit_findings(record: str) -> list[str]:
    full_sha, identity, message = record.split(
        COMMIT_FIELD_SEPARATOR, COMMIT_FIELD_SPLIT_LIMIT
    )
    short_sha = full_sha[:SHORT_SHA_LENGTH]
    return [
        *_findings_for(
            COMMIT_LABEL_TEMPLATE.format(short_sha=short_sha, part=COMMIT_IDENTITY_PART),
            re.sub(GITHUB_NOREPLY_ADDRESS_PATTERN, MASKED_ADDRESS, identity, flags=re.IGNORECASE),
        ),
        *_findings_for(
            COMMIT_LABEL_TEMPLATE.format(short_sha=short_sha, part=COMMIT_MESSAGE_PART),
            message,
        ),
    ]


def scan_commits(repository_root: Path, commit_range: str) -> list[str]:
    """Return findings for commit messages and identities in a range, oldest first.

    Args:
        repository_root: Git checkout holding the range.
        commit_range: A ``base..head`` revision range.

    Returns:
        One finding per commit identity or message line that names a private
        organization. An identity address ending in users.noreply.github.com
        is left out of the scan, since GitHub builds it from the account handle.
    """
    log_text = subprocess.run(
        ["git", "-C", str(repository_root), "log", "--reverse", COMMIT_LOG_FORMAT, commit_range],
        check=True,
        capture_output=True,
        encoding=PRIVATE_TERM_TEXT_ENCODING,
    ).stdout
    return [
        each_finding
        for each_record in log_text.split(COMMIT_RECORD_SEPARATOR)
        if each_record.strip()
        for each_finding in _commit_findings(each_record.strip())
    ]


def main(all_arguments: Sequence[str]) -> int:
    """Print every finding and return 1 when any text names a private organization.

    Args:
        all_arguments: Command-line arguments after the script name.

    Returns:
        0 for a clean event, 1 when any finding printed.
    """
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--event-path", type=Path, required=True)
    parser.add_argument("--commit-range")
    arguments = parser.parse_args(list(all_arguments))
    all_findings = scan_event(arguments.event_path)
    if arguments.commit_range:
        all_findings.extend(scan_commits(Path.cwd(), arguments.commit_range))
    for each_finding in all_findings:
        print(each_finding)
    return 1 if all_findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
