#!/usr/bin/env python3
"""Choose a Claude account for a runner job while protecting the main account.

The main account takes a job only to spend usage that expires soon. Otherwise,
the picker tries extra profiles in order and waits when every one is full.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from claude_account_profile import default_profile_home
from claude_chain_usage import (
    AccountUsageMeters,
    WeeklyUtilizationProbeError,
    probe_account_meters,
)
from dev_env_scripts_constants.claude_account_constants import (
    CHOICE_MAIN,
    CHOICE_SECOND,
    CHOICE_WAIT,
    CREDENTIALS_FILE_NAME,
    FULL_PERCENT,
    JSON_ACCOUNT_KEY,
    JSON_CONFIG_DIRECTORY_KEY,
    JSON_METERS_KEY,
    JSON_REASON_KEY,
    JSON_SESSION_RESETS_AT_KEY,
    JSON_SESSION_USED_PERCENT_KEY,
    JSON_WEEKLY_RESETS_AT_KEY,
    JSON_WEEKLY_USED_PERCENT_KEY,
    MAIN_CLAUDE_HOME_DIRECTORY_NAME,
    MAIN_SESSION_USED_CEILING_PERCENT,
    MAIN_SPEND_WINDOW,
    MAIN_WEEKLY_USED_CEILING_PERCENT,
    REASON_MAIN_EXPIRING_TEMPLATE,
    REASON_ALL_EXTRAS_WAIT_TEMPLATE,
    REASON_EXTRA_HAS_ROOM_TEMPLATE,
    REASON_EXTRA_UNREAD_TEMPLATE,
    REASON_SECOND_HAS_ROOM_TEMPLATE,
    REASON_SECOND_UNREAD,
    REASON_WAIT_TEMPLATE,
    SECOND_SESSION_USED_CEILING_PERCENT,
    SECOND_WEEKLY_USED_CEILING_PERCENT,
    SECONDS_PER_HOUR,
    UNKNOWN_RESET_TEXT,
)


@dataclass(frozen=True)
class AccountDecision:
    """The account a job runs on, and the plain-words reason for it."""

    account: str
    reason: str


@dataclass(frozen=True)
class ExtraAccount:
    """One ordered extra profile and its usage reading."""

    name: str
    meters: AccountUsageMeters | None
    config_dir: Path | None = None


def _main_spendable_reason(
    main_meters: AccountUsageMeters | None, now: datetime
) -> str | None:
    if main_meters is None:
        return None
    session_used = main_meters.session_utilization
    weekly_used = main_meters.weekly_utilization
    weekly_resets_at = main_meters.weekly_resets_at
    if session_used is None or weekly_used is None or weekly_resets_at is None:
        return None
    time_until_reset = weekly_resets_at - now
    is_expiring_soon = time_until_reset <= MAIN_SPEND_WINDOW
    has_weekly_room = weekly_used < MAIN_WEEKLY_USED_CEILING_PERCENT
    has_session_room = session_used < MAIN_SESSION_USED_CEILING_PERCENT
    if not (is_expiring_soon and has_weekly_room and has_session_room):
        return None
    return REASON_MAIN_EXPIRING_TEMPLATE.format(
        hours_until_reset=int(time_until_reset.total_seconds() // SECONDS_PER_HOUR),
        remaining_percent=FULL_PERCENT - weekly_used,
    )


def _blocking_reset(meters: AccountUsageMeters) -> datetime | None:
    all_blocking_resets: list[datetime] = []
    weekly_used = meters.weekly_utilization
    session_used = meters.session_utilization
    if weekly_used is not None and weekly_used >= SECOND_WEEKLY_USED_CEILING_PERCENT:
        if meters.weekly_resets_at is None:
            return None
        all_blocking_resets.append(meters.weekly_resets_at)
    if session_used is not None and session_used >= SECOND_SESSION_USED_CEILING_PERCENT:
        if meters.session_resets_at is None:
            return None
        all_blocking_resets.append(meters.session_resets_at)
    return max(all_blocking_resets, default=None)


def _wait_decision(second_meters: AccountUsageMeters) -> AccountDecision:
    blocking_reset = _blocking_reset(second_meters)
    return AccountDecision(
        account=CHOICE_WAIT,
        reason=REASON_WAIT_TEMPLATE.format(
            weekly_used_percent=second_meters.weekly_utilization,
            session_used_percent=second_meters.session_utilization,
            next_reset=(
                blocking_reset.isoformat() if blocking_reset else UNKNOWN_RESET_TEXT
            ),
        ),
    )


def _extra_account_decision(extra_account: ExtraAccount) -> AccountDecision | None:
    meters = extra_account.meters
    unread_reason = (
        REASON_SECOND_UNREAD
        if extra_account.name == CHOICE_SECOND
        else REASON_EXTRA_UNREAD_TEMPLATE.format(account=extra_account.name)
    )
    if meters is None:
        return AccountDecision(account=extra_account.name, reason=unread_reason)
    session_used = meters.session_utilization
    weekly_used = meters.weekly_utilization
    if session_used is None or weekly_used is None:
        return AccountDecision(account=extra_account.name, reason=unread_reason)
    is_week_blocked = weekly_used >= SECOND_WEEKLY_USED_CEILING_PERCENT
    is_session_blocked = session_used >= SECOND_SESSION_USED_CEILING_PERCENT
    if is_week_blocked or is_session_blocked:
        return None
    reason_template = (
        REASON_SECOND_HAS_ROOM_TEMPLATE
        if extra_account.name == CHOICE_SECOND
        else REASON_EXTRA_HAS_ROOM_TEMPLATE
    )
    return AccountDecision(
        account=extra_account.name,
        reason=reason_template.format(
            account=extra_account.name,
            weekly_remaining_percent=FULL_PERCENT - weekly_used,
            session_remaining_percent=FULL_PERCENT - session_used,
        ),
    )


def choose_account_from_extras(
    *,
    main_meters: AccountUsageMeters | None,
    extra_accounts: Sequence[ExtraAccount],
    now: datetime,
) -> AccountDecision:
    """Choose main or the first extra profile with room in list order."""
    main_reason = _main_spendable_reason(main_meters, now)
    if main_reason is not None:
        return AccountDecision(account=CHOICE_MAIN, reason=main_reason)
    for extra_account in extra_accounts:
        decision = _extra_account_decision(extra_account)
        if decision is not None:
            return decision
    if len(extra_accounts) == 1 and extra_accounts[0].meters is not None:
        return _wait_decision(extra_accounts[0].meters)
    all_resets = (
        _blocking_reset(extra_account.meters)
        for extra_account in extra_accounts
        if extra_account.meters is not None
    )
    next_reset = min((reset for reset in all_resets if reset is not None), default=None)
    return AccountDecision(
        account=CHOICE_WAIT,
        reason=REASON_ALL_EXTRAS_WAIT_TEMPLATE.format(
            next_reset=next_reset.isoformat() if next_reset else UNKNOWN_RESET_TEXT
        ),
    )


def choose_account(
    *,
    main_meters: AccountUsageMeters | None,
    second_meters: AccountUsageMeters | None,
    now: datetime,
) -> AccountDecision:
    """Pick the account a job runs on from both accounts' meters.

    ::

        main: week resets in 5h, 80% used, 5-hour 10% used   -> main
        main: week resets in 30h                             -> second, if it has room
        main unread, second at 99% of its week               -> wait
        main unread, second unread                           -> second

    Main runs a job only to spend leftover usage that expires soon.

    Args:
        main_meters: The main account's meters, or None when unread.
        second_meters: The second account's meters, or None when unread.
        now: The time the reset windows are measured from.

    Returns:
        The chosen account and the reason.
    """
    return choose_account_from_extras(
        main_meters=main_meters,
        extra_accounts=(ExtraAccount(name=CHOICE_SECOND, meters=second_meters),),
        now=now,
    )


def read_account_meters(credentials_path: Path) -> AccountUsageMeters | None:
    """Read one account's meters, or None when its credential or probe fails.

    Args:
        credentials_path: The account's CLI credential file.

    Returns:
        The meters, or None when they cannot be read.
    """
    try:
        return probe_account_meters(credentials_path)
    except WeeklyUtilizationProbeError:
        return None


def read_extra_accounts(config_directories: Sequence[Path]) -> tuple[ExtraAccount, ...]:
    """Read ordered extra profiles and reject duplicate directories."""
    all_resolved_directories = [
        str(directory.resolve()).casefold() for directory in config_directories
    ]
    if len(set(all_resolved_directories)) != len(config_directories):
        raise ValueError("extra account config directories must be distinct")
    return tuple(
        ExtraAccount(
            name=CHOICE_SECOND if index == 1 else f"extra_{index}",
            meters=read_account_meters(directory / CREDENTIALS_FILE_NAME),
            config_dir=directory,
        )
        for index, directory in enumerate(config_directories, start=1)
    )


def config_directory_for_decision(
    decision: AccountDecision,
    *,
    main_config_dir: Path,
    extra_accounts: Sequence[ExtraAccount],
) -> Path | None:
    """Find the selected account's config directory."""
    if decision.account == CHOICE_MAIN:
        return main_config_dir
    return next(
        (
            extra_account.config_dir
            for extra_account in extra_accounts
            if extra_account.name == decision.account
        ),
        None,
    )


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Name the Claude account a runner job uses."
    )
    parser.add_argument(
        "--main-config-dir",
        type=Path,
        default=Path.home() / MAIN_CLAUDE_HOME_DIRECTORY_NAME,
    )
    parser.add_argument(
        "--second-config-dir",
        type=Path,
        default=default_profile_home(),
    )
    parser.add_argument("--extra-config-dir", type=Path, action="append", default=[])
    return parser


def decision_payload(
    decision: AccountDecision, *, config_directory: Path | None
) -> dict[str, str | None]:
    """Shape a decision as the JSON object the runner job reads.

    ::

        AccountDecision("second", "...") with the profile directory
        -> {"account": "second", "config_dir": "<profile>", "reason": "..."}

    Args:
        decision: The chosen account and reason.
        config_directory: The Claude home the account runs under, or None on wait.

    Returns:
        The account, its Claude home, and the reason.
    """
    return {
        JSON_ACCOUNT_KEY: decision.account,
        JSON_CONFIG_DIRECTORY_KEY: str(config_directory) if config_directory else None,
        JSON_REASON_KEY: decision.reason,
    }


def _iso_or_none(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment else None


def meters_payload(
    account_meters: AccountUsageMeters | None,
) -> dict[str, float | str | None] | None:
    """Shape one account's meters as the JSON object a usage report reads.

    ::

        AccountUsageMeters(12.0, <reset>, 34.0, <reset>)
        -> {"session_used_percent": 12.0, "session_resets_at": "2026-09-22T22:00:00+00:00",
            "weekly_used_percent": 34.0, "weekly_resets_at": "2026-09-25T21:00:00+00:00"}

    Args:
        account_meters: The account's meters, or None when unread.

    Returns:
        Each used percent and reset time, or None for an unread account.
    """
    if account_meters is None:
        return None
    return {
        JSON_SESSION_USED_PERCENT_KEY: account_meters.session_utilization,
        JSON_SESSION_RESETS_AT_KEY: _iso_or_none(account_meters.session_resets_at),
        JSON_WEEKLY_USED_PERCENT_KEY: account_meters.weekly_utilization,
        JSON_WEEKLY_RESETS_AT_KEY: _iso_or_none(account_meters.weekly_resets_at),
    }


def main(all_command_arguments: list[str]) -> int:
    """Print the chosen account and every account's meters as JSON.

    Args:
        all_command_arguments: Command-line arguments after the program name.

    Returns:
        Zero once the choice is printed.
    """
    parser = _build_argument_parser()
    arguments = parser.parse_args(all_command_arguments)
    try:
        extra_accounts = read_extra_accounts(
            (arguments.second_config_dir, *arguments.extra_config_dir)
        )
    except ValueError as error:
        parser.error(str(error))
    main_meters = read_account_meters(arguments.main_config_dir / CREDENTIALS_FILE_NAME)
    decision = choose_account_from_extras(
        main_meters=main_meters,
        extra_accounts=extra_accounts,
        now=datetime.now().astimezone(),
    )
    config_directory = config_directory_for_decision(
        decision,
        main_config_dir=arguments.main_config_dir,
        extra_accounts=extra_accounts,
    )
    report = {
        **decision_payload(decision, config_directory=config_directory),
        JSON_METERS_KEY: {
            CHOICE_MAIN: meters_payload(main_meters),
            **{
                extra_account.name: meters_payload(extra_account.meters)
                for extra_account in extra_accounts
            },
        },
    }
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
