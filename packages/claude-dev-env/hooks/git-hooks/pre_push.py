#!/usr/bin/env python3
"""Show the local verification reminder before a native Git push."""

from __future__ import annotations

import sys
from pathlib import Path

from git_hooks_constants import (
    ALL_PROTECTED_BRANCH_PUSH_NAMES,
    ALL_ZEROS_OBJECT_NAME_CHARACTER,
    LOCAL_BRANCH_REFERENCE_PREFIX,
    LOCAL_REFERENCE_FIELD_INDEX,
    LOCAL_SHA_FIELD_INDEX,
    REMOTE_REFERENCE_FIELD_INDEX,
    STDIN_LINE_FIELD_COUNT,
)
from git_hooks_constants.verification_notice_constants import (
    NOTICE_EVENT_PUSH,
    PROTECTED_BRANCH_PUSH_ADVISORY_MESSAGE,
    REPOSITORY_ARGUMENT,
)
from verification_notice import main as verification_notice_main


def find_protected_branch_push_violation(
    stdin_text: str,
) -> tuple[str, str] | None:
    for each_line in stdin_text.splitlines():
        all_fields = each_line.split()
        if len(all_fields) < STDIN_LINE_FIELD_COUNT:
            continue
        local_object_name = all_fields[LOCAL_SHA_FIELD_INDEX]
        local_branch_name = all_fields[LOCAL_REFERENCE_FIELD_INDEX].removeprefix(
            LOCAL_BRANCH_REFERENCE_PREFIX
        )
        remote_branch_name = all_fields[REMOTE_REFERENCE_FIELD_INDEX].removeprefix(
            LOCAL_BRANCH_REFERENCE_PREFIX
        )
        if not local_object_name.strip(ALL_ZEROS_OBJECT_NAME_CHARACTER):
            continue
        if (
            remote_branch_name in ALL_PROTECTED_BRANCH_PUSH_NAMES
            and local_branch_name != remote_branch_name
        ):
            return local_branch_name, remote_branch_name
    return None


def main() -> int:
    try:
        stdin_text = sys.stdin.read()
        branch_violation = find_protected_branch_push_violation(stdin_text)
        if branch_violation is not None:
            local_branch_name, remote_branch_name = branch_violation
            _write_advisory(
                PROTECTED_BRANCH_PUSH_ADVISORY_MESSAGE.format(
                    local_branch=local_branch_name,
                    remote_branch=remote_branch_name,
                )
            )
        verification_notice_main(
            [
                "--event",
                NOTICE_EVENT_PUSH,
                REPOSITORY_ARGUMENT,
                str(Path.cwd()),
            ],
            stdout=sys.stdout,
        )
        return 0
    except (OSError, UnicodeError, ValueError):
        return 0


def _write_advisory(advisory_text: str) -> None:
    try:
        sys.stderr.write(advisory_text + "\n")
    except UnicodeError:
        return


if __name__ == "__main__":
    raise SystemExit(main())
