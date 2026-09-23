#!/usr/bin/env python3
"""Name the Codex account a runner job uses, and keep each account's home ready.

Up to four Codex accounts sign in, each under its own Codex home in
``~/.codex-profiles/<name>``. Jobs try them in one fixed order::

    first account with more than 10% left              -> normal, that account
    none over 10%, the roomiest one over 1%            -> luna, stop at 1% left
    ... but an account with a 5-hour window needs 20% of it left for luna
    none over 1%, or no meter reads                    -> wait, name the first reset
    account not signed in, or its meter unread         -> skipped

Three commands::

    python codex_account_choice.py choose
    {"tier": "normal", "account": "codex-1", "codex_home": "C:/Users/me/.codex-profiles/codex-1",
     "percent_left": 62.0, "stop_below_percent": null, "reason": "codex-1 has 62% left",
     "accounts": [...]}

    python codex_account_choice.py check codex-2 --floor 1
    exit 0 while codex-2 has more than 1% left, exit 3 once it has not

    python codex_account_choice.py sync
    links the shared Codex setup (config, rules, skills, plugins) into every
    account's home and leaves each sign-in and history its own
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from claude_account_profile import sync_profile
from codex_account_meters import (
    CodexAccountMeters,
    CodexMeterUnreadError,
    read_codex_meters,
    resolve_codex_path,
)
from dev_env_scripts_constants.codex_account_constants import (
    ALL_CODEX_ACCOUNT_NAMES,
    ALL_SHARED_CODEX_HOME_NAMES,
    CODEX_AUTH_FILE_NAME,
    CODEX_PROFILES_ROOT_DIRECTORY_NAME,
    CODEX_PROFILES_ROOT_ENVIRONMENT_VARIABLE,
    EXIT_CODE_NO_ROOM,
    EXIT_CODE_ROOM,
    LUNA_TIER_SHORT_WINDOW_MINIMUM_PERCENT_LEFT,
    LUNA_TIER_STOP_PERCENT_LEFT,
    MAIN_CODEX_HOME_DIRECTORY_NAME,
    NORMAL_TIER_MINIMUM_PERCENT_LEFT,
    REASON_LUNA_TEMPLATE,
    REASON_NORMAL_TEMPLATE,
    REASON_WAIT_TEMPLATE,
    REASON_WAIT_UNREAD,
    TIER_LUNA,
    TIER_NORMAL,
    TIER_WAIT,
    UNKNOWN_RESET_TEXT,
    UNREAD_NOT_SIGNED_IN,
)

MeterReader = Callable[[Path], CodexAccountMeters]


@dataclass(frozen=True)
class AccountReading:
    """One account's meters, or why they could not be read."""

    name: str
    codex_home: Path
    meters: CodexAccountMeters | None
    unread_reason: str | None = None


@dataclass(frozen=True)
class CodexAccountDecision:
    """The tier and account a job runs on, and the plain-words reason."""

    tier: str
    reading: AccountReading | None
    stop_below_percent: float | None
    reason: str


def default_profiles_root() -> Path:
    """Locate the directory that holds one Codex home per account.

    Returns:
        The root the environment names, else ``~/.codex-profiles``.
    """
    named_root = os.environ.get(CODEX_PROFILES_ROOT_ENVIRONMENT_VARIABLE)
    return (
        Path(named_root)
        if named_root
        else Path.home() / CODEX_PROFILES_ROOT_DIRECTORY_NAME
    )


def is_account_local_codex_entry(entry_name: str) -> bool:
    """Tell whether a Codex home entry belongs to one account only.

    ::

        "auth.json", "sessions", "history.jsonl", "state_5.sqlite" -> True
        "config.toml", "rules", "skills", "plugins"                -> False

    Args:
        entry_name: A top-level entry name in a Codex home.

    Returns:
        True for every entry outside the shared set.
    """
    return entry_name not in ALL_SHARED_CODEX_HOME_NAMES


def read_account(
    name: str, profiles_root: Path, read_meters: MeterReader
) -> AccountReading:
    """Read one account's meters from its Codex home.

    Args:
        name: The account name.
        profiles_root: The directory that holds every account's Codex home.
        read_meters: Reads the meters under one Codex home.

    Returns:
        The meters, or the reason they are unread.
    """
    codex_home = profiles_root / name
    if not (codex_home / CODEX_AUTH_FILE_NAME).is_file():
        return AccountReading(name, codex_home, None, UNREAD_NOT_SIGNED_IN)
    try:
        return AccountReading(name, codex_home, read_meters(codex_home))
    except CodexMeterUnreadError as error:
        return AccountReading(name, codex_home, None, str(error))


def _first_reset(
    all_read: Sequence[AccountReading],
) -> tuple[datetime, AccountReading] | None:
    all_resets = [
        (each_reset, each_reading)
        for each_reading in all_read
        if each_reading.meters is not None
        and (
            each_reset := each_reading.meters.resets_before_room(
                NORMAL_TIER_MINIMUM_PERCENT_LEFT
            )
        )
        is not None
    ]
    if not all_resets:
        return None
    return min(all_resets, key=lambda each_pair: each_pair[0])


def _wait_decision(all_read: Sequence[AccountReading]) -> CodexAccountDecision:
    if not all_read:
        return CodexAccountDecision(TIER_WAIT, None, None, REASON_WAIT_UNREAD)
    first_reset = _first_reset(all_read)
    if first_reset is None:
        reset_text, first_reading = UNKNOWN_RESET_TEXT, all_read[0]
    else:
        reset_text, first_reading = first_reset[0].isoformat(), first_reset[1]
    return CodexAccountDecision(
        TIER_WAIT,
        first_reading,
        None,
        REASON_WAIT_TEMPLATE.format(account=first_reading.name, reset=reset_text),
    )


def _percent_left(reading: AccountReading) -> float:
    return reading.meters.percent_left if reading.meters is not None else 0.0


def _normal_decision(all_read: Sequence[AccountReading]) -> CodexAccountDecision | None:
    for each_reading in all_read:
        percent_left = _percent_left(each_reading)
        if percent_left > NORMAL_TIER_MINIMUM_PERCENT_LEFT:
            return CodexAccountDecision(
                TIER_NORMAL,
                each_reading,
                None,
                REASON_NORMAL_TEMPLATE.format(
                    account=each_reading.name, percent_left=percent_left
                ),
            )
    return None


def _can_run_luna(reading: AccountReading) -> bool:
    if reading.meters is None or reading.meters.percent_left <= LUNA_TIER_STOP_PERCENT_LEFT:
        return False
    short_window_left = reading.meters.short_window_percent_left
    return (
        short_window_left is None
        or short_window_left >= LUNA_TIER_SHORT_WINDOW_MINIMUM_PERCENT_LEFT
    )


def _luna_decision(all_read: Sequence[AccountReading]) -> CodexAccountDecision | None:
    all_candidates = [each_reading for each_reading in all_read if _can_run_luna(each_reading)]
    if not all_candidates:
        return None
    roomiest = max(all_candidates, key=_percent_left)
    return CodexAccountDecision(
        TIER_LUNA,
        roomiest,
        LUNA_TIER_STOP_PERCENT_LEFT,
        REASON_LUNA_TEMPLATE.format(
            bar=NORMAL_TIER_MINIMUM_PERCENT_LEFT,
            account=roomiest.name,
            percent_left=_percent_left(roomiest),
            stop=LUNA_TIER_STOP_PERCENT_LEFT,
        ),
    )


def choose_codex_account(all_readings: Sequence[AccountReading]) -> CodexAccountDecision:
    """Pick the tier and account a job runs on.

    ::

        codex-1 8%, codex-2 40%          -> normal on codex-2
        codex-1 8%, codex-2 3%, others 0 -> luna on codex-1, stop at 1%
        codex-1 week 8%, 5-hour 15% left -> no luna on codex-1, 5-hour under 20%
        every account 1% or less         -> wait, naming the account that resets first
        codex-1 unread, codex-2 40%      -> normal on codex-2

    Args:
        all_readings: Every account's reading, in try order.

    Returns:
        The tier, the account, where a Luna run stops, and the reason.
    """
    all_read = [
        each_reading for each_reading in all_readings if each_reading.meters is not None
    ]
    return (
        _normal_decision(all_read)
        or _luna_decision(all_read)
        or _wait_decision(all_read)
    )


def _iso_or_none(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment else None


def reading_payload(reading: AccountReading) -> dict[str, object]:
    """Shape one account's reading as the JSON object a report prints.

    Args:
        reading: One account's reading.

    Returns:
        The name, percent left, each window, and any unread reason.
    """
    if reading.meters is None:
        return {
            "name": reading.name,
            "percent_left": None,
            "unread": reading.unread_reason,
        }
    return {
        "name": reading.name,
        "percent_left": reading.meters.percent_left,
        "windows": [
            {
                "minutes": each_window.duration_minutes,
                "used_percent": each_window.used_percent,
                "resets_at": _iso_or_none(each_window.resets_at),
            }
            for each_window in reading.meters.all_windows
        ],
    }


def decision_payload(
    decision: CodexAccountDecision, all_readings: Sequence[AccountReading]
) -> dict[str, object]:
    """Shape a decision as the JSON object the runner job reads.

    Args:
        decision: The chosen tier and account.
        all_readings: Every account's reading, for the report.

    Returns:
        The tier, account, Codex home, room, stop point, reason, and all readings.
    """
    is_runnable = decision.tier != TIER_WAIT and decision.reading is not None
    chosen = decision.reading if is_runnable else None
    return {
        "tier": decision.tier,
        "account": chosen.name if chosen else None,
        "codex_home": str(chosen.codex_home) if chosen else None,
        "percent_left": chosen.meters.percent_left
        if chosen and chosen.meters
        else None,
        "stop_below_percent": decision.stop_below_percent,
        "reason": decision.reason,
        "accounts": [reading_payload(each_reading) for each_reading in all_readings],
    }


def _meter_reader(codex_path_argument: Path | None) -> MeterReader:
    codex_path = resolve_codex_path(codex_path_argument)
    return lambda codex_home: read_codex_meters(codex_path, codex_home)


def _run_choose(arguments: argparse.Namespace) -> int:
    read_meters = _meter_reader(arguments.codex_path)
    all_readings = [
        read_account(each_name, arguments.profiles_root, read_meters)
        for each_name in ALL_CODEX_ACCOUNT_NAMES
    ]
    print(
        json.dumps(decision_payload(choose_codex_account(all_readings), all_readings))
    )
    return 0


def _run_check(arguments: argparse.Namespace) -> int:
    reading = read_account(
        arguments.account, arguments.profiles_root, _meter_reader(arguments.codex_path)
    )
    print(json.dumps(reading_payload(reading)))
    if reading.meters is not None and reading.meters.percent_left > arguments.floor:
        return EXIT_CODE_ROOM
    return EXIT_CODE_NO_ROOM


def _run_sync(arguments: argparse.Namespace) -> int:
    now = datetime.now(timezone.utc)
    all_reports = {}
    for each_name in ALL_CODEX_ACCOUNT_NAMES:
        report = sync_profile(
            main_home=arguments.main_home,
            profile_home=arguments.profiles_root / each_name,
            now=now,
            is_local=is_account_local_codex_entry,
        )
        all_reports[each_name] = {
            "linked": list(report.all_linked),
            "moved_aside": list(report.all_moved_aside),
            "unlinked": list(report.all_unlinked),
        }
    print(json.dumps(all_reports))
    return 0


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Name the Codex account a runner job uses."
    )
    parser.add_argument("--profiles-root", type=Path, default=default_profiles_root())
    parser.add_argument("--codex-path", type=Path, default=None)
    all_commands = parser.add_subparsers(dest="command", required=True)
    all_commands.add_parser("choose").set_defaults(run=_run_choose)
    check_parser = all_commands.add_parser("check")
    check_parser.add_argument("account", choices=ALL_CODEX_ACCOUNT_NAMES)
    check_parser.add_argument(
        "--floor", type=float, default=LUNA_TIER_STOP_PERCENT_LEFT
    )
    check_parser.set_defaults(run=_run_check)
    sync_parser = all_commands.add_parser("sync")
    sync_parser.add_argument(
        "--main-home", type=Path, default=Path.home() / MAIN_CODEX_HOME_DIRECTORY_NAME
    )
    sync_parser.set_defaults(run=_run_sync)
    return parser


def main(all_command_arguments: list[str]) -> int:
    """Run one command and print its JSON report.

    Args:
        all_command_arguments: Command-line arguments after the program name.

    Returns:
        Zero for choose and sync; for check, zero with room and three without.
    """
    arguments = _build_argument_parser().parse_args(all_command_arguments)
    return arguments.run(arguments)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
