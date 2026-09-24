"""Build and write a headless Claude worker's JSON report."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from dev_env_scripts_constants.claude_account_worker_constants import (
    DURATION_DECIMAL_PLACES,
    JSON_IS_ERROR_KEY,
    JSON_RESULT_KEY,
    REPORT_ACCOUNT_KEY,
    REPORT_DURATION_SECONDS_KEY,
    REPORT_EXIT_CODE_KEY,
    REPORT_INDENT,
    REPORT_IS_ERROR_KEY,
    REPORT_REASON_KEY,
    REPORT_RESULT_KEY,
    STDOUT_TAIL_CHARACTER_LIMIT,
    SUMMARY_LINE_TEMPLATE,
    UTF8_ENCODING,
    WAIT_DURATION_SECONDS,
    WAIT_EXIT_CODE,
)


@dataclass(frozen=True)
class WorkerReport:
    account: str
    reason: str
    exit_code: int
    duration_seconds: float
    payload: object
    is_error: bool


def _bounded_stdout_tail(stdout_text: str) -> str:
    return stdout_text[-STDOUT_TAIL_CHARACTER_LIMIT:]


def _extract_payload(stdout_text: str) -> tuple[object, bool]:
    try:
        parsed_stdout = json.loads(stdout_text)
    except json.JSONDecodeError:
        return _bounded_stdout_tail(stdout_text), True
    if not isinstance(parsed_stdout, dict) or JSON_RESULT_KEY not in parsed_stdout:
        return None, True
    return parsed_stdout[JSON_RESULT_KEY], parsed_stdout.get(JSON_IS_ERROR_KEY) is True


def wait_report(account: str, reason: str) -> WorkerReport:
    """Build the report for an account decision that says to wait.

    Args:
        account: The chosen account slot.
        reason: Why the picker chose to wait.

    Returns:
        A report carrying the wait exit code and no payload.
    """
    return WorkerReport(
        account=account,
        reason=reason,
        exit_code=WAIT_EXIT_CODE,
        duration_seconds=WAIT_DURATION_SECONDS,
        payload=None,
        is_error=True,
    )


def make_report(
    account: str,
    reason: str,
    *,
    exit_code: int,
    duration_seconds: float,
    stdout_text: str,
) -> WorkerReport:
    """Build the report for a worker that ran, from its captured stdout.

    Args:
        account: The chosen account slot.
        reason: Why the picker chose that account.
        exit_code: The worker process's exit code.
        duration_seconds: How long the worker ran.
        stdout_text: The worker's captured stdout text.

    Returns:
        A report carrying the parsed payload, or the stdout tail when the
        payload does not parse as the expected JSON shape.
    """
    payload, has_payload_error = _extract_payload(stdout_text)
    return WorkerReport(
        account=account,
        reason=reason,
        exit_code=exit_code,
        duration_seconds=round(duration_seconds, DURATION_DECIMAL_PLACES),
        payload=payload,
        is_error=(exit_code != 0 or has_payload_error),
    )


def pre_launch_failure_report(
    account: str, reason: str, exit_code: int
) -> WorkerReport:
    """Build the report for a failure that happened before the worker launched.

    Args:
        account: The chosen account slot.
        reason: Why the picker chose that account.
        exit_code: The failure's exit code.

    Returns:
        A report with no payload and a zero duration.
    """
    return make_report(
        account,
        reason,
        exit_code=exit_code,
        duration_seconds=WAIT_DURATION_SECONDS,
        stdout_text="",
    )


def write_report(report_file: Path, report: WorkerReport) -> None:
    """Write a worker report to disk as indented JSON.

    Args:
        report_file: Where the JSON report is written.
        report: The report to serialize.
    """
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_payload = {
        REPORT_ACCOUNT_KEY: report.account,
        REPORT_REASON_KEY: report.reason,
        REPORT_EXIT_CODE_KEY: report.exit_code,
        REPORT_DURATION_SECONDS_KEY: report.duration_seconds,
        REPORT_RESULT_KEY: report.payload,
        REPORT_IS_ERROR_KEY: report.is_error,
    }
    report_file.write_text(
        json.dumps(report_payload, ensure_ascii=False, indent=REPORT_INDENT) + "\n",
        encoding=UTF8_ENCODING,
    )


def _print_summary(report: WorkerReport, report_file: Path) -> None:
    print(
        SUMMARY_LINE_TEMPLATE.format(
            account=report.account,
            exit_code=report.exit_code,
            report_file=report_file,
        )
    )


def finalize_report(report_file: Path, report: WorkerReport) -> int:
    """Write a worker report to disk and print its one-line summary.

    Args:
        report_file: Where the JSON report is written.
        report: The report to write and summarize.

    Returns:
        The report's exit code.
    """
    write_report(report_file, report)
    _print_summary(report, report_file)
    return report.exit_code
