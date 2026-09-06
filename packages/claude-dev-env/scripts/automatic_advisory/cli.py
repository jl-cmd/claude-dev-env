from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import TextIO

scripts_directory = Path(__file__).resolve().parents[1]
if str(scripts_directory) not in sys.path:
    sys.path.insert(0, str(scripts_directory))

from pr_verification.config.constants import INCOMPLETE_EXIT_CODE, SUCCESS_EXIT_CODE
from pr_verification.github import GitHubAppAuthenticator
from pr_verification.lock import SupervisorLock, SupervisorLockError
from pr_verification.model import RepositorySettings

from automatic_advisory.config.constants import (
    CREATE_NEW_PROCESS_GROUP_ATTRIBUTE,
    CREATE_NO_WINDOW_ATTRIBUTE,
    DETACHED_PROCESS_ATTRIBUTE,
    REPORT_NEWLINE,
    STATE_STATUS_KEY,
    STATE_STATUS_NEVER_RUN,
)
from automatic_advisory.configuration import (
    AdvisoryConfigurationError,
    load_advisory_settings,
)
from automatic_advisory.model import AdvisorySettings, AdvisoryState
from automatic_advisory.runner import (
    AdvisoryGitHub,
    AutomaticAdvisoryRunner,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the automatic advisory command parser.

    Returns:
        Parser for status, one-shot, and polling modes.
    """
    parser = argparse.ArgumentParser(prog="cde automatic-advisory")
    parser.add_argument("--settings", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--poll", action="store_true")
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--start", action="store_true")
    parser.add_argument("--rerun", action="store_true")
    return parser


def main(
    all_arguments: Sequence[str],
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    sleeper: Callable[[float], None] = time.sleep,
) -> int:
    """Run the selected automatic advisory command.
    Args:
        all_arguments: Command arguments after the executable name.
        stdout: Stream for state output.
        stderr: Stream for configuration and runtime errors.
        runner_builder: Optional runner factory used by focused callers.
        sleeper: Delay function used by polling mode.

    Returns:
        Zero for a completed command or three for an incomplete run.
    """
    return _run_main_command(all_arguments, stdout, stderr, sleeper)


def _run_main_command(
    all_arguments: Sequence[str],
    stdout: TextIO,
    stderr: TextIO,
    sleeper: Callable[[float], None],
) -> int:
    try:
        parsed_arguments, settings = _load_command_inputs(all_arguments)
        return _run_selected_mode(parsed_arguments, settings, stdout, sleeper)
    except (AdvisoryConfigurationError, OSError, SupervisorLockError) as error:
        stderr.write(f"{error}{REPORT_NEWLINE}")
        return INCOMPLETE_EXIT_CODE


def _load_command_inputs(
    all_arguments: Sequence[str],
) -> tuple[argparse.Namespace, AdvisorySettings]:
    parsed_arguments = build_parser().parse_args(list(all_arguments))
    return parsed_arguments, load_advisory_settings(parsed_arguments.settings)


def _run_selected_mode(
    parsed_arguments: argparse.Namespace,
    settings: AdvisorySettings,
    stdout: TextIO,
    sleeper: Callable[[float], None],
) -> int:
    if parsed_arguments.status:
        write_status(settings, stdout)
        return SUCCESS_EXIT_CODE
    if parsed_arguments.start:
        return start_polling(parsed_arguments.settings)
    advisory_runner = _build_runner(settings)
    if parsed_arguments.once:
        write_states(advisory_runner.run_once(parsed_arguments.rerun), stdout)
        return SUCCESS_EXIT_CODE
    with SupervisorLock(settings.poll_lock_root):
        return run_polling(advisory_runner, settings.poll_seconds, stdout, sleeper)


def start_polling(settings_path: Path) -> int:
    """Start one detached polling process and return without waiting.

    Args:
        settings_path: JSON settings passed to the detached process.

    Returns:
        Zero after the child process starts.
    """
    process_flags = _detached_process_flags()
    resolved_settings_path = settings_path.resolve()
    subprocess.Popen(
        (
            sys.executable,
            str(Path(__file__).resolve()),
            "--settings",
            str(resolved_settings_path),
            "--poll",
        ),
        cwd=Path(__file__).resolve().parents[1],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=process_flags,
        start_new_session=True,
    )
    return SUCCESS_EXIT_CODE


def _detached_process_flags() -> int:
    all_flag_names = (
        DETACHED_PROCESS_ATTRIBUTE,
        CREATE_NEW_PROCESS_GROUP_ATTRIBUTE,
        CREATE_NO_WINDOW_ATTRIBUTE,
    )
    return (
        0
        if sys.platform != "win32"
        else sum(
            getattr(subprocess, each_flag_name, 0) for each_flag_name in all_flag_names
        )
    )


def _build_runner(
    settings: AdvisorySettings,
) -> AutomaticAdvisoryRunner:
    authenticator = GitHubAppAuthenticator(
        settings.api_url,
        settings.app_id,
        settings.installation_id,
        settings.private_key_path,
    )
    return AutomaticAdvisoryRunner(
        settings,
        None,
        github_factory=lambda repository: _issue_repository_api(
            authenticator, repository
        ),
    )


def _issue_repository_api(
    authenticator: GitHubAppAuthenticator,
    repository: RepositorySettings,
) -> AdvisoryGitHub:
    return authenticator.issue_repository_api(
        repository,
        should_write_issue_labels=True,
    )


def run_polling(
    advisory_runner: AutomaticAdvisoryRunner,
    poll_seconds: float,
    stdout: TextIO,
    sleeper: Callable[[float], None],
) -> int:
    """Run advisory checks until the caller interrupts polling.

    Args:
        advisory_runner: Runner for explicit checkout and pull request pairs.
        poll_seconds: Delay between completed cycles.
        stdout: Stream for each persisted state.
        sleeper: Delay function used between cycles.

    Returns:
        Zero after a user interrupt.
    """
    try:
        while True:
            write_states(advisory_runner.run_once(), stdout)
            sleeper(poll_seconds)
    except KeyboardInterrupt:
        return SUCCESS_EXIT_CODE


def write_states(
    all_states: tuple[AdvisoryState, ...],
    stdout: TextIO,
) -> None:
    """Write one JSON state line for each registration.

    Args:
        all_states: Persisted registration states.
        stdout: Stream receiving each JSON state line.
    """
    stdout.writelines(
        json.dumps(asdict(each_state), sort_keys=True) + REPORT_NEWLINE
        for each_state in all_states
    )
    stdout.flush()


def write_status(settings: AdvisorySettings, stdout: TextIO) -> None:
    """Write the latest state or never-run marker for each registration.

    Args:
        settings: Explicit advisory registrations to inspect.
        stdout: Stream receiving one JSON record per registration.
    """
    for each_registration in settings.registrations:
        state_path = each_registration.state_path
        if not state_path.is_file():
            stdout.write(
                json.dumps(
                    {
                        "repository": each_registration.repository.slug,
                        "pull_request": each_registration.pull_request_number,
                        STATE_STATUS_KEY: STATE_STATUS_NEVER_RUN,
                    },
                    sort_keys=True,
                )
                + REPORT_NEWLINE
            )
            continue
        stdout.write(state_path.read_text(encoding="utf-8"))
    stdout.flush()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
