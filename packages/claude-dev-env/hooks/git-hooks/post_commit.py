#!/usr/bin/env python3
"""Show the local verification reminder after a native Git commit."""

from __future__ import annotations

import sys
from pathlib import Path

from verification_notice import main as verification_notice_main
from git_hooks_constants.verification_notice_constants import (
    NOTICE_EVENT_COMMIT,
    REPOSITORY_ARGUMENT,
)


def main() -> int:
    try:
        verification_notice_main(
            [
                "--event",
                NOTICE_EVENT_COMMIT,
                REPOSITORY_ARGUMENT,
                str(Path.cwd()),
            ],
            stdout=sys.stdout,
        )
        return 0
    except (OSError, UnicodeError, ValueError):
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
