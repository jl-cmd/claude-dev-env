from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from submodule_sync import (
    SyncReport,
    SyncStatus,
    sync_repository,
)
from submodule_sync_constants.config.constants import (
    DEFAULT_REPOSITORY_ARGUMENT,
    DIAGNOSTIC_PREFIX,
    EXIT_CODE_FAILURE,
    EXIT_CODE_INVALID_ARGUMENTS,
    EXIT_CODE_SUCCESS,
    INVALID_ARGUMENT_MESSAGE_TEMPLATE,
    JSON_LINE_SEPARATOR,
    REPOSITORY_ARGUMENT_NAME,
)


class _InvalidCommandArguments(ValueError):
    pass


class _SyncArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        """Reject invalid command arguments.

        Args:
            message: Parser diagnostic.

        Raises:
            _InvalidCommandArguments: Always raised with the parser diagnostic.
        """
        raise _InvalidCommandArguments(message)


def _parse_arguments(all_arguments: Sequence[str]) -> Path:
    parser = _SyncArgumentParser(add_help=False)
    parser.add_argument(
        REPOSITORY_ARGUMENT_NAME,
        default=DEFAULT_REPOSITORY_ARGUMENT,
    )
    parsed_arguments = parser.parse_args(all_arguments)
    return Path(str(parsed_arguments.repository))


def _emit_report(sync_report: SyncReport) -> None:
    sys.stdout.write(json.dumps(sync_report.as_record()) + JSON_LINE_SEPARATOR)


def main(all_arguments: Sequence[str]) -> int:
    """Run the parent-pointer synchronization command.

    Args:
        all_arguments: Command arguments without the executable name.

    Returns:
        Zero for completed states, one for Git failures, or two for bad arguments.
    """
    try:
        repository = _parse_arguments(all_arguments)
    except _InvalidCommandArguments as error:
        diagnostic = INVALID_ARGUMENT_MESSAGE_TEMPLATE.format(error=error)
        sync_report = SyncReport(
            status=SyncStatus.ERROR,
            repository=Path(DEFAULT_REPOSITORY_ARGUMENT).resolve().as_posix(),
            diagnostic=diagnostic,
        )
        _emit_report(sync_report)
        print(f"{DIAGNOSTIC_PREFIX}{diagnostic}", file=sys.stderr)
        return EXIT_CODE_INVALID_ARGUMENTS
    sync_report = sync_repository(repository)
    _emit_report(sync_report)
    if sync_report.status is SyncStatus.ERROR:
        print(f"{DIAGNOSTIC_PREFIX}{sync_report.diagnostic}", file=sys.stderr)
        return EXIT_CODE_FAILURE
    return EXIT_CODE_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
