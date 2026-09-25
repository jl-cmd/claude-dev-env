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

from claude_account_choice import (
    choose_account_from_extras,
    config_directory_for_decision,
    decision_payload,
    read_account_meters,
    read_extra_accounts,
)
from claude_account_profile import default_profile_home
from claude_account_worker_process import WorkerProcess, invoke_worker
from claude_account_worker_report import (
    WorkerReport,
    finalize_report,
    make_report,
    pre_launch_failure_report,
    wait_report,
)
from dev_env_scripts_constants.claude_account_worker_constants import (
    CHOICE_MAIN,
    CHOICE_WAIT,
    CLAUDE_BINARY_NAME,
    CLAUDE_CONFIG_DIR_ENV_VAR,
    CLI_DESCRIPTION,
    CREDENTIALS_FILE_NAME,
    CWD_FLAG,
    DEFAULT_PERMISSION_MODE,
    DEFAULT_TIMEOUT_MINUTES,
    EXTRA_PROFILES_FILE_NAME,
    INVALID_TIMEOUT_MESSAGE,
    JSON_ACCOUNT_KEY,
    JSON_CONFIG_DIRECTORY_KEY,
    JSON_REASON_KEY,
    LAUNCH_FAILURE_EXIT_CODE,
    MAIN_CLAUDE_HOME_DIRECTORY_NAME,
    MISSING_BINARY_EXIT_CODE,
    MINIMUM_TIMEOUT_MINUTES,
    MODEL_FLAG,
    OUTPUT_FORMAT_FLAG,
    OUTPUT_FORMAT_JSON,
    PERMISSION_MODE_FLAG,
    PROMPT_FILE_FLAG,
    REPORT_FILE_FLAG,
    SINGLE_PROMPT_FLAG,
    TIMEOUT_MINUTES_FLAG,
    UTF8_ENCODING,
)
from shared_tree_paths import resolve_shared_process_tree_scripts_directory

_process_tree_scripts_directory = resolve_shared_process_tree_scripts_directory(
    __file__, all_environment=os.environ
)
if str(_process_tree_scripts_directory) not in sys.path:
    sys.path.insert(0, str(_process_tree_scripts_directory))

_process_tree_kill = importlib.import_module("process_tree_kill")
_terminate_process_tree = _process_tree_kill.terminate_process_tree


@dataclass(frozen=True)
class AccountSelection:
    account: str
    config_dir: Path | None
    reason: str


@dataclass(frozen=True)
class WorkerDependencies:
    process_factory: Callable[..., WorkerProcess]
    all_parent_environment_variables: Mapping[str, str]
    binary_resolver: Callable[[str], str | None]
    process_terminator: Callable[[WorkerProcess], None]
    monotonic_clock: Callable[[], float]


def _default_dependencies() -> WorkerDependencies:
    return WorkerDependencies(
        process_factory=subprocess.Popen,
        all_parent_environment_variables=os.environ,
        binary_resolver=shutil.which,
        process_terminator=_terminate_process_tree,
        monotonic_clock=time.monotonic,
    )


def _selection_from_payload(all_selection_payload: Mapping[str, str | None]) -> AccountSelection:
    account = all_selection_payload[JSON_ACCOUNT_KEY]
    reason = all_selection_payload[JSON_REASON_KEY]
    config_dir_text = all_selection_payload[JSON_CONFIG_DIRECTORY_KEY]
    if account is None or reason is None:
        raise ValueError("account picker returned an incomplete decision")
    return AccountSelection(
        account=account,
        config_dir=Path(config_dir_text) if config_dir_text is not None else None,
        reason=reason,
    )


def extra_config_directories(main_config_dir: Path) -> tuple[Path, ...]:
    """Read the ordered local profile list or use the legacy default.

    Args:
        main_config_dir: The main Claude home that may hold the list file.

    Returns:
        The extra profile homes in the order they are tried.

    Raises:
        ValueError: When the list is empty, holds a non-name, or repeats a name.
    """
    profiles_file = main_config_dir / EXTRA_PROFILES_FILE_NAME
    if not profiles_file.exists():
        return (default_profile_home(),)
    profile_names = json.loads(profiles_file.read_text(encoding=UTF8_ENCODING))
    if (
        not isinstance(profile_names, list)
        or not profile_names
        or any(not isinstance(name, str) for name in profile_names)
    ):
        raise ValueError("extra profile list must be a nonempty JSON list of names")
    if len({name.casefold() for name in profile_names}) != len(profile_names):
        raise ValueError("extra profile names must be distinct")
    return tuple(default_profile_home(name) for name in profile_names)


def select_account() -> AccountSelection:
    """Pick the account this worker runs on and its Claude home directory.

    Returns:
        The chosen account, its Claude config directory, and the reason.

    Raises:
        ValueError: When the profile list or account decision is invalid.
    """
    main_config_dir = Path.home() / MAIN_CLAUDE_HOME_DIRECTORY_NAME
    extra_accounts = read_extra_accounts(extra_config_directories(main_config_dir))
    main_meters = read_account_meters(main_config_dir / CREDENTIALS_FILE_NAME)
    decision = choose_account_from_extras(
        main_meters=main_meters,
        all_extra_accounts=extra_accounts,
        now=datetime.now().astimezone(),
    )
    selected_config_dir = config_directory_for_decision(
        decision, main_config_dir=main_config_dir, all_extra_accounts=extra_accounts
    )
    payload = decision_payload(decision, config_directory=selected_config_dir)
    return _selection_from_payload(payload)


def _positive_timeout_minutes(candidate_text: str) -> int:
    timeout_minutes = int(candidate_text)
    if timeout_minutes < MINIMUM_TIMEOUT_MINUTES:
        raise argparse.ArgumentTypeError(INVALID_TIMEOUT_MESSAGE)
    return timeout_minutes


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for one headless worker invocation.

    Returns:
        The configured argument parser.
    """
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
    all_environment_variables: Mapping[str, str],
) -> dict[str, str]:
    all_child_environment_variables = dict(all_environment_variables)
    if selection.account == CHOICE_MAIN:
        all_child_environment_variables.pop(CLAUDE_CONFIG_DIR_ENV_VAR, None)
        return all_child_environment_variables
    if selection.account == CHOICE_WAIT:
        raise ValueError("wait selection cannot launch a worker")
    if selection.config_dir is None:
        raise ValueError("extra account selection needs a config directory")
    all_child_environment_variables[CLAUDE_CONFIG_DIR_ENV_VAR] = str(selection.config_dir)
    return all_child_environment_variables


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


def _prepared_launch(
    selection: AccountSelection,
    prompt_file: Path,
    dependencies: WorkerDependencies,
) -> tuple[dict[str, str], str, str] | WorkerReport:
    try:
        all_child_environment_variables = _child_environment(
            selection, dependencies.all_parent_environment_variables
        )
        prompt_text = prompt_file.read_text(encoding=UTF8_ENCODING)
    except (OSError, ValueError):
        return pre_launch_failure_report(
            selection.account, selection.reason, LAUNCH_FAILURE_EXIT_CODE
        )
    claude_binary = dependencies.binary_resolver(CLAUDE_BINARY_NAME)
    if claude_binary is None:
        return pre_launch_failure_report(
            selection.account, selection.reason, MISSING_BINARY_EXIT_CODE
        )
    return all_child_environment_variables, prompt_text, claude_binary


def _invoked_report(
    selection: AccountSelection,
    *,
    all_arguments: list[str],
    cwd: Path,
    all_child_environment_variables: dict[str, str],
    prompt_text: str,
    timeout_minutes: int,
    dependencies: WorkerDependencies,
) -> WorkerReport:
    exit_code, duration_seconds, stdout_text = invoke_worker(
        all_arguments=all_arguments,
        cwd=cwd,
        all_child_environment_variables=all_child_environment_variables,
        prompt_text=prompt_text,
        timeout_minutes=timeout_minutes,
        controls=dependencies,
    )
    return make_report(
        selection.account,
        selection.reason,
        exit_code=exit_code,
        duration_seconds=duration_seconds,
        stdout_text=stdout_text,
    )


def _worker_report(
    selection: AccountSelection,
    *,
    prompt_file: Path,
    cwd: Path,
    model: str | None,
    permission_mode: str,
    timeout_minutes: int,
    dependencies: WorkerDependencies,
) -> WorkerReport:
    prepared = _prepared_launch(selection, prompt_file, dependencies)
    if isinstance(prepared, WorkerReport):
        return prepared
    all_child_environment_variables, prompt_text, claude_binary = prepared
    all_arguments = _invocation(claude_binary, model=model, permission_mode=permission_mode)
    return _invoked_report(
        selection,
        all_arguments=all_arguments,
        cwd=cwd,
        all_child_environment_variables=all_child_environment_variables,
        prompt_text=prompt_text,
        timeout_minutes=timeout_minutes,
        dependencies=dependencies,
    )


def _report_for_selection(
    selection: AccountSelection,
    *,
    prompt_file: Path,
    cwd: Path,
    model: str | None,
    permission_mode: str,
    timeout_minutes: int,
    dependencies: WorkerDependencies,
) -> WorkerReport:
    if selection.account == CHOICE_WAIT:
        return wait_report(selection.account, selection.reason)
    return _worker_report(
        selection,
        prompt_file=prompt_file,
        cwd=cwd,
        model=model,
        permission_mode=permission_mode,
        timeout_minutes=timeout_minutes,
        dependencies=dependencies,
    )


def run_worker(
    *,
    prompt_file: Path,
    cwd: Path,
    report_file: Path,
    model: str | None,
    permission_mode: str,
    timeout_minutes: int,
    decision_selector: Callable[[], AccountSelection],
    dependencies: WorkerDependencies,
) -> int:
    """Pick an account and run one headless Claude worker on it.

    Args:
        prompt_file, report_file: The prompt and report file paths.
        decision_selector, dependencies: The picker and process controls.
    Returns:
        The exit code: 3 on wait, 124 on timeout, 127 on a missing binary,
        or the child's own exit code.
    """
    report = _report_for_selection(
        decision_selector(),
        prompt_file=prompt_file,
        cwd=cwd,
        model=model,
        permission_mode=permission_mode,
        timeout_minutes=timeout_minutes,
        dependencies=dependencies,
    )
    return finalize_report(report_file, report)


def main() -> int:
    """Parse CLI arguments and run one headless worker.

    Returns:
        The worker's exit code.
    """
    arguments = build_argument_parser().parse_args()
    return run_worker(
        prompt_file=arguments.prompt_file,
        cwd=arguments.cwd,
        report_file=arguments.report_file,
        model=arguments.model,
        permission_mode=arguments.permission_mode,
        timeout_minutes=arguments.timeout_minutes,
        decision_selector=select_account,
        dependencies=_default_dependencies(),
    )


if __name__ == "__main__":
    sys.exit(main())
