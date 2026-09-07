#!/usr/bin/env python3
"""Print a bounded, nonblocking local verification reminder for native Git."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Never, TextIO

from git_hooks_constants.verification_notice_constants import (
    ALL_NOTICE_EVENTS,
    BASE_ARGUMENT,
    BASE_REFERENCE,
    COMMAND_SEPARATOR,
    EXECUTOR_ARGUMENT,
    EXECUTOR_DIRECTORY_NAME,
    EXECUTOR_FILE_NAME,
    GIT_COMMAND_SUCCESS_EXIT_CODE,
    GIT_DIRECTORY_NAME,
    JSON_ENCODING,
    LOCAL_VERIFICATION_DIRECTORY_NAME,
    LOCAL_VERIFICATION_PACKAGE_DIRECTORY_NAME,
    NO_VERIFIED_SHA,
    NOTICE_ADVISORY_LINE,
    NOTICE_HEADER,
    NOTICE_LINE_SEPARATOR,
    NOTICE_RUN_LINE,
    OUTPUT_ARGUMENT,
    PACKAGE_ROOT_PARENT_INDEX,
    POWERSHELL_CALL_OPERATOR,
    POWERSHELL_ESCAPED_QUOTE,
    POWERSHELL_QUOTE,
    PYTHON_COMMAND,
    REPORT_FILE_NAME,
    SCOPED_VERIFICATION_SCRIPT_PATH,
    TARGET_REPOSITORY_REMOTE,
    UNKNOWN_SHA,
)

verification_scripts_directory = (
    Path(__file__).resolve().parents[PACKAGE_ROOT_PARENT_INDEX] / EXECUTOR_DIRECTORY_NAME
)
if str(verification_scripts_directory) not in sys.path:
    sys.path.insert(0, str(verification_scripts_directory))

from verification_notice_context import (
    VerificationNoticeContext,
    _load_notice_context,
    _run_git_query,
)
from verification_start import load_runner_configuration, start_automatic_advisory
from verification_notice_state import (
    _build_state_message,
    _evaluate_context,
)


class _NoticeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        raise ValueError(message)


def build_verification_notice(context: VerificationNoticeContext) -> str:
    """Render the advisory for one normalized repository context.

    Args:
        context: Repository fields that define the rendered notice.

    Returns:
        The formatted advisory text, or an empty string for another repository.
    """
    if context.repository_remote != TARGET_REPOSITORY_REMOTE:
        return ""
    current_head = context.current_head or UNKNOWN_SHA
    state, verified_head = _evaluate_context(context, _run_git_query)
    all_notice_lines = (
        NOTICE_HEADER,
        f"Repository remote: {context.repository_remote}",
        f"Event: {context.event}",
        f"Current SHA: {current_head}",
        f"Verified SHA: {verified_head or NO_VERIFIED_SHA}",
        f"State: {state}",
        _build_state_message(state, context.manifest_is_available),
        NOTICE_ADVISORY_LINE,
        NOTICE_RUN_LINE,
        _build_canonical_command(context),
    )
    return NOTICE_LINE_SEPARATOR.join(all_notice_lines) + NOTICE_LINE_SEPARATOR


def main(
    all_arguments: Sequence[str] | None = None,
    *,
    stdout: TextIO = sys.stdout,
) -> int:
    """Read Git metadata and print a reminder without affecting the Git action.

    Args:
        all_arguments: Optional command arguments for the notice CLI.
        stdout: Stream receiving the rendered notice.

    Returns:
        Zero so the native Git action continues.
    """
    parsed_arguments = _parse_arguments(all_arguments)
    if parsed_arguments is None:
        return GIT_COMMAND_SUCCESS_EXIT_CODE
    try:
        _write_parsed_notice(parsed_arguments, stdout)
    except (OSError, UnicodeError, ValueError):
        return GIT_COMMAND_SUCCESS_EXIT_CODE
    return GIT_COMMAND_SUCCESS_EXIT_CODE


def _write_parsed_notice(parsed_arguments: argparse.Namespace, stdout: TextIO) -> None:
    notice_context = _load_notice_context(
        parsed_arguments.event,
        Path(parsed_arguments.repository),
    )
    if notice_context is None:
        return
    _write_notice(stdout, build_verification_notice(notice_context))
    if parsed_arguments.notice_only:
        return
    start_automatic_advisory(notice_context)


def _parse_arguments(
    all_arguments: Sequence[str] | None,
) -> argparse.Namespace | None:
    argument_parser = _NoticeArgumentParser(add_help=True)
    argument_parser.add_argument("--event", required=True)
    argument_parser.add_argument("--notice-only", action="store_true")
    argument_parser.add_argument("--repo", dest="repository", required=True)
    try:
        parsed_arguments, unknown_arguments = argument_parser.parse_known_args(all_arguments)
    except (SystemExit, ValueError):
        return None
    if unknown_arguments or parsed_arguments.event not in ALL_NOTICE_EVENTS:
        return None
    return parsed_arguments


def _write_notice(stdout: TextIO, notice_text: str) -> None:
    try:
        stdout.write(notice_text)
    except UnicodeError:
        stream_encoding = getattr(stdout, "encoding", None) or JSON_ENCODING
        safe_notice_text = notice_text.encode(
            stream_encoding,
            errors="replace",
        ).decode(stream_encoding, errors="replace")
        stdout.write(safe_notice_text)


def _build_canonical_command(context: VerificationNoticeContext) -> str:
    git_directory = context.git_directory or context.repository_root / GIT_DIRECTORY_NAME
    report_path = git_directory / LOCAL_VERIFICATION_DIRECTORY_NAME / REPORT_FILE_NAME
    executor_path = (
        Path(__file__).resolve().parents[PACKAGE_ROOT_PARENT_INDEX]
        / EXECUTOR_DIRECTORY_NAME
        / LOCAL_VERIFICATION_PACKAGE_DIRECTORY_NAME
        / EXECUTOR_FILE_NAME
    )
    all_command_parts = (
        _build_python_command(context),
        _quote_windows_path(context.repository_root / SCOPED_VERIFICATION_SCRIPT_PATH),
        f"{BASE_ARGUMENT} {BASE_REFERENCE}",
        f"{EXECUTOR_ARGUMENT} {_quote_windows_path(executor_path)}",
        f"{OUTPUT_ARGUMENT} {_quote_windows_path(report_path)}",
    )
    return COMMAND_SEPARATOR.join(all_command_parts)


def _build_python_command(context: VerificationNoticeContext) -> str:
    runner_configuration = load_runner_configuration(context)
    if runner_configuration is None:
        return PYTHON_COMMAND
    python_path, _ = runner_configuration
    return POWERSHELL_CALL_OPERATOR + _quote_windows_path(Path(python_path))


def _quote_windows_path(path: Path) -> str:
    path_text = str(path)
    escaped_path = path_text.replace(POWERSHELL_QUOTE, POWERSHELL_ESCAPED_QUOTE)
    return f"{POWERSHELL_QUOTE}{escaped_path}{POWERSHELL_QUOTE}"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
