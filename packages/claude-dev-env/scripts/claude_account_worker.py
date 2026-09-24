"""Run a headless Claude worker on the account chosen by the usage picker."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from claude_account_choice import choose_account, decision_payload, read_account_meters
from claude_account_profile import default_profile_home
from dev_env_scripts_constants.claude_account_worker_constants import (
    CHOICE_MAIN,
    CHOICE_SECOND,
    CHOICE_WAIT,
    CLAUDE_BINARY_NAME,
    CLAUDE_CONFIG_DIR_ENV_VAR,
    CLI_DESCRIPTION,
    CREATION_FLAGS_KEY,
    CREDENTIALS_FILE_NAME,
    CWD_FLAG,
    DECODE_ERRORS_KEY,
    DEFAULT_PERMISSION_MODE,
    DEFAULT_TIMEOUT_MINUTES,
    DRAIN_ATTEMPT_LIMIT,
    DRAIN_GRACE_TIMEOUT_SECONDS,
    DURATION_DECIMAL_PLACES,
    ENCODING_KEY,
    ENVIRONMENT_KEY,
    INVALID_TIMEOUT_MESSAGE,
    JSON_ACCOUNT_KEY,
    JSON_CONFIG_DIRECTORY_KEY,
    JSON_IS_ERROR_KEY,
    JSON_REASON_KEY,
    JSON_RESULT_KEY,
    LAUNCH_FAILURE_EXIT_CODE,
    MAIN_CLAUDE_HOME_DIRECTORY_NAME,
    MISSING_BINARY_EXIT_CODE,
    MINIMUM_TIMEOUT_MINUTES,
    MODEL_FLAG,
    OUTPUT_FORMAT_FLAG,
    OUTPUT_FORMAT_JSON,
    PERMISSION_MODE_FLAG,
    PROMPT_FILE_FLAG,
    REPORT_ACCOUNT_KEY,
    REPORT_DURATION_SECONDS_KEY,
    REPORT_EXIT_CODE_KEY,
    REPORT_FILE_FLAG,
    REPORT_INDENT,
    REPORT_IS_ERROR_KEY,
    REPORT_REASON_KEY,
    REPORT_RESULT_KEY,
    SINGLE_PROMPT_FLAG,
    START_NEW_SESSION_KEY,
    STDERR_PIPE_NAME,
    STDOUT_PIPE_NAME,
    STDOUT_TAIL_CHARACTER_LIMIT,
    STDIN_PIPE_NAME,
    SUMMARY_LINE_TEMPLATE,
    TEXT_MODE_KEY,
    TIMEOUT_EXIT_CODE,
    TIMEOUT_MINUTES_FLAG,
    UTF8_DECODE_ERRORS,
    UTF8_ENCODING,
    WAIT_DURATION_SECONDS,
    WAIT_EXIT_CODE,
)
from shared_tree_paths import resolve_shared_process_tree_scripts_directory
from subprocess_window_access import hidden_window_creation_flags

_process_tree_scripts_directory = resolve_shared_process_tree_scripts_directory(
    __file__, all_environment=os.environ
)
if str(_process_tree_scripts_directory) not in sys.path:
    sys.path.insert(0, str(_process_tree_scripts_directory))

_process_tree_kill = importlib.import_module("process_tree_kill")
_should_start_new_session = _process_tree_kill.should_start_new_session
_terminate_process_tree = _process_tree_kill.terminate_process_tree


class WorkerProcess(Protocol):
    returncode: int | None

    pid: int

    def communicate(
        self,
        input: str | None = None,
        timeout: float | None = None,
    ) -> tuple[str | bytes | None, str | bytes | None]: ...

    def poll(self) -> int | None: ...

    def kill(self) -> None: ...


@dataclass(frozen=True)
class AccountSelection:
    account: str
    config_dir: Path | None
    reason: str


@dataclass(frozen=True)
class WorkerReport:
    account: str
    reason: str
    exit_code: int
    duration_seconds: float
    result: object
    is_error: bool


def select_account() -> AccountSelection:
    main_config_dir = Path.home() / MAIN_CLAUDE_HOME_DIRECTORY_NAME
    second_config_dir = default_profile_home()
    config_directory_by_account = {
        CHOICE_MAIN: main_config_dir,
        CHOICE_SECOND: second_config_dir,
    }
    main_meters = read_account_meters(main_config_dir / CREDENTIALS_FILE_NAME)
    second_meters = read_account_meters(second_config_dir / CREDENTIALS_FILE_NAME)
    decision = choose_account(
        main_meters=main_meters,
        second_meters=second_meters,
        now=datetime.now().astimezone(),
    )
    selected_config_dir = config_directory_by_account.get(decision.account)
    payload = decision_payload(decision, config_directory=selected_config_dir)
    account = payload[JSON_ACCOUNT_KEY]
    reason = payload[JSON_REASON_KEY]
    config_dir_text = payload[JSON_CONFIG_DIRECTORY_KEY]
    if account is None or reason is None:
        raise ValueError("account picker returned an incomplete decision")
    return AccountSelection(
        account=account,
        config_dir=Path(config_dir_text) if config_dir_text is not None else None,
        reason=reason,
    )


def _positive_timeout_minutes(value: str) -> int:
    timeout_minutes = int(value)
    if timeout_minutes < MINIMUM_TIMEOUT_MINUTES:
        raise argparse.ArgumentTypeError(INVALID_TIMEOUT_MESSAGE)
    return timeout_minutes


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=CLI_DESCRIPTION)
    parser.add_argument(PROMPT_FILE_FLAG, type=Path, required=True)
    parser.add_argument(CWD_FLAG, type=Path, default=Path.cwd())
    parser.add_argument(REPORT_FILE_FLAG, type=Path, required=True)
    parser.add_argument(MODEL_FLAG)
    parser.add_argument(
        PERMISSION_MODE_FLAG,
        default=DEFAULT_PERMISSION_MODE,
    )
    parser.add_argument(
        TIMEOUT_MINUTES_FLAG,
        type=_positive_timeout_minutes,
        default=DEFAULT_TIMEOUT_MINUTES,
    )
    return parser


def _child_environment(
    selection: AccountSelection,
    parent_environment: Mapping[str, str],
) -> dict[str, str]:
    child_environment = dict(parent_environment)
    if selection.account == CHOICE_MAIN:
        child_environment.pop(CLAUDE_CONFIG_DIR_ENV_VAR, None)
    elif selection.account == CHOICE_SECOND:
        if selection.config_dir is None:
            raise ValueError("second account selection needs a config directory")
        child_environment[CLAUDE_CONFIG_DIR_ENV_VAR] = str(selection.config_dir)
    else:
        raise ValueError(f"unsupported account selection: {selection.account}")
    return child_environment


def _invocation(
    executable: str,
    *,
    model: str | None,
    permission_mode: str,
) -> list[str]:
    all_arguments = [
        executable,
        SINGLE_PROMPT_FLAG,
        OUTPUT_FORMAT_FLAG,
        OUTPUT_FORMAT_JSON,
        PERMISSION_MODE_FLAG,
        permission_mode,
    ]
    if model is not None:
        all_arguments.extend([MODEL_FLAG, model])
    return all_arguments


def _text_value(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(UTF8_ENCODING, errors=UTF8_DECODE_ERRORS)
    return value


def _bounded_stdout_tail(stdout_text: str) -> str:
    return stdout_text[-STDOUT_TAIL_CHARACTER_LIMIT:]


def _parse_result(stdout_text: str) -> tuple[object, bool]:
    try:
        payload = json.loads(stdout_text)
    except json.JSONDecodeError:
        return _bounded_stdout_tail(stdout_text), True
    if not isinstance(payload, dict) or JSON_RESULT_KEY not in payload:
        return None, True
    return payload[JSON_RESULT_KEY], payload.get(JSON_IS_ERROR_KEY) is True


def _write_report(report_file: Path, report: WorkerReport) -> None:
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_payload = {
        REPORT_ACCOUNT_KEY: report.account,
        REPORT_REASON_KEY: report.reason,
        REPORT_EXIT_CODE_KEY: report.exit_code,
        REPORT_DURATION_SECONDS_KEY: report.duration_seconds,
        REPORT_RESULT_KEY: report.result,
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


def _drain_after_termination(
    process: WorkerProcess,
    process_terminator: Callable[[WorkerProcess], None],
    initial_stdout: str,
) -> str:
    latest_stdout = initial_stdout
    for _ in range(DRAIN_ATTEMPT_LIMIT):
        process_terminator(process)
        try:
            captured_stdout, _ = process.communicate(
                timeout=DRAIN_GRACE_TIMEOUT_SECONDS
            )
        except subprocess.TimeoutExpired as timeout_error:
            timed_out_stdout = _text_value(timeout_error.output)
            if timed_out_stdout:
                latest_stdout = timed_out_stdout
            continue
        drained_stdout = _text_value(captured_stdout)
        return drained_stdout if drained_stdout else latest_stdout
    return latest_stdout


def _make_report(
    selection: AccountSelection,
    *,
    exit_code: int,
    duration_seconds: float,
    stdout_text: str,
    failed_before_output: bool = False,
) -> WorkerReport:
    result, output_error = _parse_result(stdout_text)
    return WorkerReport(
        account=selection.account,
        reason=selection.reason,
        exit_code=exit_code,
        duration_seconds=round(duration_seconds, DURATION_DECIMAL_PLACES),
        result=result,
        is_error=(exit_code != 0 or output_error or failed_before_output),
    )


def run_worker(
    *,
    prompt_file: Path,
    cwd: Path,
    report_file: Path,
    model: str | None = None,
    permission_mode: str = DEFAULT_PERMISSION_MODE,
    timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES,
    decision_selector: Callable[[], AccountSelection] = select_account,
    process_factory: Callable[..., WorkerProcess] | None = None,
    parent_environment: Mapping[str, str] | None = None,
    binary_resolver: Callable[[str], str | None] = shutil.which,
    process_terminator: Callable[[WorkerProcess], None] = _terminate_process_tree,
    monotonic_clock: Callable[[], float] = time.monotonic,
) -> int:
    selection = decision_selector()
    if selection.account == CHOICE_WAIT:
        report = WorkerReport(
            account=selection.account,
            reason=selection.reason,
            exit_code=WAIT_EXIT_CODE,
            duration_seconds=WAIT_DURATION_SECONDS,
            result=None,
            is_error=True,
        )
        _write_report(report_file, report)
        _print_summary(report, report_file)
        return report.exit_code

    environment_source = os.environ if parent_environment is None else parent_environment
    try:
        child_environment = _child_environment(selection, environment_source)
        prompt_text = prompt_file.read_text(encoding=UTF8_ENCODING)
    except (OSError, ValueError):
        report = _make_report(
            selection,
            exit_code=LAUNCH_FAILURE_EXIT_CODE,
            duration_seconds=WAIT_DURATION_SECONDS,
            stdout_text="",
            failed_before_output=True,
        )
        _write_report(report_file, report)
        _print_summary(report, report_file)
        return report.exit_code

    claude_binary = binary_resolver(CLAUDE_BINARY_NAME)
    if claude_binary is None:
        report = _make_report(
            selection,
            exit_code=MISSING_BINARY_EXIT_CODE,
            duration_seconds=WAIT_DURATION_SECONDS,
            stdout_text="",
            failed_before_output=True,
        )
        _write_report(report_file, report)
        _print_summary(report, report_file)
        return report.exit_code

    selected_process_factory = subprocess.Popen if process_factory is None else process_factory
    all_arguments = _invocation(
        claude_binary,
        model=model,
        permission_mode=permission_mode,
    )
    process_start = monotonic_clock()
    try:
        process = selected_process_factory(
            all_arguments,
            cwd=str(cwd),
            env=child_environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=UTF8_ENCODING,
            errors=UTF8_DECODE_ERRORS,
            start_new_session=_should_start_new_session(),
            creationflags=hidden_window_creation_flags(),
        )
    except OSError:
        report = _make_report(
            selection,
            exit_code=LAUNCH_FAILURE_EXIT_CODE,
            duration_seconds=monotonic_clock() - process_start,
            stdout_text="",
            failed_before_output=True,
        )
        _write_report(report_file, report)
        _print_summary(report, report_file)
        return report.exit_code

    try:
        captured_stdout, _ = process.communicate(
            input=prompt_text,
            timeout=timeout_minutes * 60,
        )
    except subprocess.TimeoutExpired as timeout_error:
        initial_stdout = _text_value(timeout_error.output)
        captured_stdout_text = _drain_after_termination(
            process,
            process_terminator,
            initial_stdout,
        )
        report = _make_report(
            selection,
            exit_code=TIMEOUT_EXIT_CODE,
            duration_seconds=monotonic_clock() - process_start,
            stdout_text=captured_stdout_text,
            failed_before_output=True,
        )
        _write_report(report_file, report)
        _print_summary(report, report_file)
        return report.exit_code

    process_exit_code = process.returncode
    if process_exit_code is None:
        process_exit_code = LAUNCH_FAILURE_EXIT_CODE
    stdout_text = _text_value(captured_stdout)
    report = _make_report(
        selection,
        exit_code=process_exit_code,
        duration_seconds=monotonic_clock() - process_start,
        stdout_text=stdout_text,
    )
    _write_report(report_file, report)
    _print_summary(report, report_file)
    return report.exit_code


def main(all_command_arguments: list[str] | None = None) -> int:
    arguments = build_argument_parser().parse_args(all_command_arguments)
    return run_worker(
        prompt_file=arguments.prompt_file,
        cwd=arguments.cwd,
        report_file=arguments.report_file,
        model=arguments.model,
        permission_mode=arguments.permission_mode,
        timeout_minutes=arguments.timeout_minutes,
    )


if __name__ == "__main__":
    sys.exit(main())
