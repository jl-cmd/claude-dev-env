#!/usr/bin/env python3
"""Report remaining weekly usage for every account in the Claude chain.

Loads ``~/.claude/claude-chain.json`` (or a path the caller names), probes each
entry's weekly utilization through the usage-pause OAuth endpoint, and prints a
JSON report. Ranking is available as an importable helper; ``run_claude``
consumes that ranking to choose try order.

::

    python claude_chain_usage.py
    {"accounts": [
      {"command": "claude", "weekly_remaining_percent": 58.0},
      {"command": "claude-ev", "weekly_remaining_percent": null, "error": "..."}
    ]}
"""

from __future__ import annotations

import argparse
import http.client
import importlib.util
import json
import sys
import urllib.error
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import ModuleType

from dev_env_scripts_constants.claude_chain_constants import CHAIN_CONFIG_ERROR_EXIT_CODE
from dev_env_scripts_constants.claude_chain_usage_constants import (
    CLI_CONFIG_PATH_FLAG,
    FULL_WEEKLY_PERCENT,
    JSON_ACCOUNTS_KEY,
    JSON_COMMAND_KEY,
    JSON_ERROR_KEY,
    JSON_WEEKLY_REMAINING_PERCENT_KEY,
    NO_ACCESS_TOKEN_ERROR_TEMPLATE,
    RESOLVE_USAGE_WINDOW_FILENAME,
    RESOLVE_USAGE_WINDOW_MISSING_ERROR_TEMPLATE,
    RESOLVE_USAGE_WINDOW_MODULE_NAME,
    USAGE_PAUSE_SCRIPTS_DIRECTORY_NAME,
    USAGE_PAUSE_SKILL_DIRECTORY_NAME,
    USAGE_PAUSE_SKILL_NAME,
    USAGE_PROBE_FAILED_ERROR_TEMPLATE,
    WEEKLY_UTILIZATION_MISSING_ERROR,
)

import claude_chain_runner as chain_runner

WeeklyUtilizationProbe = Callable[[Path], float]


class WeeklyUtilizationProbeError(Exception):
    """Raised when the weekly_utilization_probe cannot measure one account."""


@dataclass(frozen=True)
class AccountUsageReport:
    """One chain account's remaining weekly usage, or the reason it is unknown."""

    command: str
    weekly_remaining_percent: float | None
    error: str | None = None


def _default_credentials_path() -> Path:
    usage_window_resolver = _load_resolve_usage_window_module()
    return Path.home().joinpath(
        *usage_window_resolver.ALL_CREDENTIALS_RELATIVE_PATH_PARTS
    )


def _credentials_path_for_entry(entry: chain_runner.ChainEntry) -> Path:
    if entry.credentials_path is None:
        return _default_credentials_path()
    return Path(entry.credentials_path).expanduser()


def _usage_pause_scripts_directory() -> Path:
    package_root = Path(__file__).resolve().parent.parent
    return (
        package_root
        / USAGE_PAUSE_SKILL_DIRECTORY_NAME
        / USAGE_PAUSE_SKILL_NAME
        / USAGE_PAUSE_SCRIPTS_DIRECTORY_NAME
    )


def _discard_sys_path_entry(path_text: str) -> None:
    if path_text in sys.path:
        sys.path.remove(path_text)


def _load_resolve_usage_window_module() -> ModuleType:
    already_loaded = sys.modules.get(RESOLVE_USAGE_WINDOW_MODULE_NAME)
    if already_loaded is not None:
        return already_loaded
    scripts_directory = _usage_pause_scripts_directory()
    module_path = scripts_directory / RESOLVE_USAGE_WINDOW_FILENAME
    if not module_path.is_file():
        raise WeeklyUtilizationProbeError(
            RESOLVE_USAGE_WINDOW_MISSING_ERROR_TEMPLATE.format(
                module_path=module_path
            )
        )
    scripts_directory_text = str(scripts_directory)
    was_path_inserted = False
    if scripts_directory_text not in sys.path:
        sys.path.insert(0, scripts_directory_text)
        was_path_inserted = True
    is_module_ready = False
    try:
        module_specification = importlib.util.spec_from_file_location(
            RESOLVE_USAGE_WINDOW_MODULE_NAME, module_path
        )
        if module_specification is None or module_specification.loader is None:
            raise WeeklyUtilizationProbeError(
                RESOLVE_USAGE_WINDOW_MISSING_ERROR_TEMPLATE.format(
                    module_path=module_path
                )
            )
        loaded_module = importlib.util.module_from_spec(module_specification)
        sys.modules[RESOLVE_USAGE_WINDOW_MODULE_NAME] = loaded_module
        module_specification.loader.exec_module(loaded_module)
        is_module_ready = True
    finally:
        if not is_module_ready:
            sys.modules.pop(RESOLVE_USAGE_WINDOW_MODULE_NAME, None)
        if was_path_inserted:
            _discard_sys_path_entry(scripts_directory_text)
    return loaded_module


def _probe_weekly_utilization(credentials_path: Path) -> float:
    usage_window_resolver = _load_resolve_usage_window_module()
    now = datetime.now().astimezone()
    try:
        access_token = usage_window_resolver.read_oauth_access_token(
            credentials_path, now
        )
        if access_token is None:
            raise WeeklyUtilizationProbeError(
                NO_ACCESS_TOKEN_ERROR_TEMPLATE.format(credentials_path=credentials_path)
            )
        usage_payload = usage_window_resolver._fetch_usage_payload(access_token)
    except WeeklyUtilizationProbeError:
        raise
    except (
        urllib.error.URLError,
        http.client.HTTPException,
        TimeoutError,
        OSError,
        ValueError,
    ) as probe_error:
        raise WeeklyUtilizationProbeError(
            USAGE_PROBE_FAILED_ERROR_TEMPLATE.format(error=probe_error)
        ) from probe_error
    usage_windows = usage_window_resolver.extract_usage_windows(usage_payload)
    if usage_windows.weekly_utilization is None:
        raise WeeklyUtilizationProbeError(WEEKLY_UTILIZATION_MISSING_ERROR)
    return float(usage_windows.weekly_utilization)


weekly_utilization_probe: WeeklyUtilizationProbe = _probe_weekly_utilization


def weekly_remaining_from_utilization(weekly_utilization: float) -> float:
    """Convert weekly utilization percent into remaining weekly percent.

    ::

        weekly_remaining_from_utilization(42.0) -> 58.0
        weekly_remaining_from_utilization(9.0)  -> 91.0

    Args:
        weekly_utilization: Used weekly capacity on the 0–100 scale.

    Returns:
        Remaining weekly capacity on the same 0–100 scale.
    """
    return FULL_WEEKLY_PERCENT - weekly_utilization


def _report_for_entry(
    entry: chain_runner.ChainEntry,
    active_probe: WeeklyUtilizationProbe,
) -> AccountUsageReport:
    try:
        credentials_path = _credentials_path_for_entry(entry)
        weekly_utilization = active_probe(credentials_path)
    except (WeeklyUtilizationProbeError, ImportError, AttributeError) as probe_error:
        return AccountUsageReport(
            command=entry.command,
            weekly_remaining_percent=None,
            error=str(probe_error),
        )
    return AccountUsageReport(
        command=entry.command,
        weekly_remaining_percent=weekly_remaining_from_utilization(
            weekly_utilization
        ),
    )


def report_chain_weekly_usage(*, config_path: Path) -> list[AccountUsageReport]:
    """Report remaining weekly usage for every account in the chain config.

    ::

        report_chain_weekly_usage(config_path=Path("chain.json"))
        -> [AccountUsageReport("claude", 58.0), ...]

    Uses the module-level ``weekly_utilization_probe`` (tests rebind it).

    Args:
        config_path: Chain configuration file to load.

    Returns:
        One report per chain entry, in config order.

    Raises:
        ChainConfigurationError: When the chain configuration cannot be loaded.
    """
    all_entries = chain_runner.load_chain(config_path)
    return [
        _report_for_entry(each_entry, weekly_utilization_probe)
        for each_entry in all_entries
    ]


def _nulls_last_remaining_rank(report: AccountUsageReport) -> tuple[int, float]:
    if report.weekly_remaining_percent is None:
        return (1, 0.0)
    return (0, -report.weekly_remaining_percent)


def rank_accounts_by_weekly_remaining(
    all_reports: list[AccountUsageReport],
) -> list[AccountUsageReport]:
    """Order reports by remaining weekly usage, highest first.

    ::

        [40%, 70%, null, 70%] -> [70% (earlier), 70% (later), 40%, null]

    Ties keep config order. Unmeasurable accounts (null remaining) sort last.

    Args:
        all_reports: Reports in chain-config order.

    Returns:
        A new list ordered by remaining weekly percent descending.
    """
    return sorted(all_reports, key=_nulls_last_remaining_rank)


def _account_report_to_json_mapping(
    report: AccountUsageReport,
) -> dict[str, str | float | None]:
    if report.weekly_remaining_percent is None:
        return {
            JSON_COMMAND_KEY: report.command,
            JSON_WEEKLY_REMAINING_PERCENT_KEY: None,
            JSON_ERROR_KEY: report.error,
        }
    return {
        JSON_COMMAND_KEY: report.command,
        JSON_WEEKLY_REMAINING_PERCENT_KEY: report.weekly_remaining_percent,
    }


def reports_to_json_payload(
    all_reports: list[AccountUsageReport],
) -> dict[str, list[dict[str, str | float | None]]]:
    """Build the CLI JSON payload for a list of account reports.

    ::

        reports_to_json_payload([AccountUsageReport("claude", 58.0)])
        -> {"accounts": [{"command": "claude", "weekly_remaining_percent": 58.0}]}

    Args:
        all_reports: Reports in the order they should appear in the payload.

    Returns:
        The ``{"accounts": [...]}`` envelope.
    """
    return {
        JSON_ACCOUNTS_KEY: [
            _account_report_to_json_mapping(each_report)
            for each_report in all_reports
        ]
    }


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Report remaining weekly usage for every account in the Claude chain."
        )
    )
    parser.add_argument(
        CLI_CONFIG_PATH_FLAG,
        dest="config_path",
        default=None,
        help="Path to claude-chain.json; defaults to the per-user chain config.",
    )
    return parser


def main(all_command_arguments: list[str]) -> int:
    """Probe the chain and print the weekly-usage JSON report on stdout.

    ::

        main(["--config-path", "chain.json"]) -> 0  # JSON on stdout
        main(["--config-path", "missing.json"]) -> 3  # error on stderr

    Args:
        all_command_arguments: The argument vector after the program name.

    Returns:
        Zero on success, or the chain-config error exit code when the config
        cannot be loaded.
    """
    parser = _build_argument_parser()
    parsed_arguments = parser.parse_args(all_command_arguments)
    resolved_config_path = (
        Path(parsed_arguments.config_path)
        if parsed_arguments.config_path is not None
        else chain_runner.chain_config_path()
    )
    try:
        all_reports = report_chain_weekly_usage(config_path=resolved_config_path)
    except chain_runner.ChainConfigurationError as configuration_error:
        print(str(configuration_error), file=sys.stderr)
        return CHAIN_CONFIG_ERROR_EXIT_CODE
    print(json.dumps(reports_to_json_payload(all_reports), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
