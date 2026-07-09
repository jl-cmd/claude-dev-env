#!/usr/bin/env python3
"""Resolve the account's 5-hour usage window and plan the pause stage chain.

::

    python resolve_usage_window.py --override 74m
    {"source": "override", "reset_at": "2026-07-08T10:14:00-07:00",
     "seconds_until_reset": 4440, "stages_seconds": [3480, 960, 120], ...}

With no ``--override``, the script reads the Claude Code OAuth access token
from the CLI credential file and asks the OAuth usage endpoint for the
``five_hour`` and ``seven_day`` windows. Exit code 2 means the probe cannot
resolve; the caller then asks the user for a manual reset time.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from usage_pause_constants.resolve_usage_window_constants import (
    ALL_CREDENTIALS_RELATIVE_PATH_PARTS,
    ALL_RESETS_AT_KEYS,
    AUTHORIZATION_BEARER_PREFIX,
    AUTHORIZATION_HEADER_NAME,
    BARE_MINUTES_PATTERN,
    CLOCK_HOUR_MAXIMUM,
    CLOCK_PATTERN,
    CONTENT_TYPE_HEADER_NAME,
    CONTENT_TYPE_JSON,
    CREDENTIALS_ACCESS_TOKEN_KEY,
    CREDENTIALS_EXPIRES_AT_KEY,
    CREDENTIALS_OAUTH_SECTION_KEY,
    DURATION_PATTERN,
    EPOCH_MILLISECONDS_THRESHOLD,
    EXIT_CODE_PROBE_UNAVAILABLE,
    EXIT_CODE_RESOLVED,
    FIVE_HOUR_BUCKET_KEY,
    ISO_UTC_OFFSET,
    ISO_UTC_SUFFIX,
    LOGGING_FORMAT,
    MAXIMUM_STAGE_SECONDS,
    MERIDIEM_AM,
    MERIDIEM_PM,
    MILLISECONDS_PER_SECOND,
    MINIMUM_STAGE_SECONDS,
    MINUTES_PER_HOUR,
    NOON_HOUR,
    OAUTH_BETA_HEADER_NAME,
    OAUTH_BETA_HEADER_VALUE,
    OAUTH_USAGE_ENDPOINT_URL,
    PROBE_TIMEOUT_SECONDS,
    RESULT_KEY_ERROR,
    RESULT_KEY_RESET_AT,
    RESULT_KEY_SECONDS_UNTIL_RESET,
    RESULT_KEY_SESSION_UTILIZATION,
    RESULT_KEY_SOURCE,
    RESULT_KEY_STAGES_SECONDS,
    RESULT_KEY_WEEKLY_NEAR_CAP,
    RESULT_KEY_WEEKLY_RESETS_AT,
    RESULT_KEY_WEEKLY_UTILIZATION,
    SEVEN_DAY_BUCKET_KEY,
    SOURCE_OVERRIDE,
    SOURCE_PROBE,
    TAIL_STAGE_SECONDS,
    UTILIZATION_KEY,
    WEEKLY_UTILIZATION_WARN_THRESHOLD,
)

logger = logging.getLogger("resolve_usage_window")


@dataclass(frozen=True)
class UsageWindows:
    """The usage meters read from one OAuth usage response.

    ::

        {"five_hour": {"utilization": 42, "resets_at": ...}}  -> session meters
        {"seven_day": {"utilization": 63, "resets_at": ...}}  -> weekly meters

    Attributes:
        session_utilization: Percent of the 5-hour window spent, or None
            when the five_hour bucket is missing or unreadable.
        session_resets_at: When the 5-hour window resets, or None when the
            five_hour reset time is missing or unreadable.
        weekly_utilization: Percent of the weekly window spent, or None
            when the seven_day bucket is missing or unreadable.
        weekly_resets_at: When the weekly window resets, or None when the
            seven_day reset time is missing or unreadable.
    """

    session_utilization: float | None
    session_resets_at: datetime | None
    weekly_utilization: float | None
    weekly_resets_at: datetime | None


def parse_manual_override(override_text: str, now: datetime) -> datetime:
    """Turn a user-given reset override into the reset datetime.

    ::

        "74m"     -> now + 74 minutes
        "1h30m"   -> now + 90 minutes
        "45"      -> now + 45 minutes
        "10:20pm" -> today 22:20, or tomorrow 22:20 when already past
        "22:15"   -> today 22:15, or tomorrow when already past

    Args:
        override_text: The reset time or duration the user typed.
        now: The current local time the override is anchored to.

    Returns:
        The reset time the pause chain should land past.

    Raises:
        ValueError: The text parses as neither a duration nor a clock time.
    """
    normalized = override_text.strip().lower()
    if re.fullmatch(BARE_MINUTES_PATTERN, normalized):
        return now + timedelta(minutes=int(normalized))
    duration_match = re.fullmatch(DURATION_PATTERN, normalized)
    if duration_match and (
        duration_match.group("hours") or duration_match.group("minutes")
    ):
        duration_hours = int(duration_match.group("hours") or 0)
        duration_minutes = int(duration_match.group("minutes") or 0)
        return now + timedelta(hours=duration_hours, minutes=duration_minutes)
    clock_match = re.fullmatch(CLOCK_PATTERN, normalized)
    if clock_match and (clock_match.group("meridiem") or clock_match.group("minute")):
        return _clock_match_to_datetime(clock_match, now)
    raise ValueError(
        f"cannot read '{override_text}' as a reset time; give a clock time like 10:20pm or a duration like 74m"
    )


def _clock_match_to_datetime(clock_match: re.Match[str], now: datetime) -> datetime:
    hour = int(clock_match.group("hour"))
    minute = int(clock_match.group("minute") or 0)
    meridiem = clock_match.group("meridiem")
    if minute >= MINUTES_PER_HOUR:
        raise ValueError(f"minute {minute} is out of range")
    if meridiem is not None:
        if hour < 1 or hour > NOON_HOUR:
            raise ValueError(f"hour {hour} needs to be 1-12 with am/pm")
        if meridiem == MERIDIEM_PM and hour != NOON_HOUR:
            hour += NOON_HOUR
        if meridiem == MERIDIEM_AM and hour == NOON_HOUR:
            hour = 0
    elif hour > CLOCK_HOUR_MAXIMUM:
        raise ValueError(f"hour {hour} is out of range")
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def plan_wakeup_stages(seconds_until_reset: int) -> list[int]:
    """Split the wait until the reset into ScheduleWakeup stage durations.

    ::

        4440 (74m to reset) -> [3480, 960, 120]

    Every stage stays within the stage cap, the chain sums to the wait plus
    the tail buffer so the last firing lands past the reset, and a leftover
    too short to stand alone folds into the tail.

    Args:
        seconds_until_reset: Seconds from now until the window resets.

    Returns:
        The stage durations in firing order, each one a ScheduleWakeup delay.
    """
    tail_seconds = TAIL_STAGE_SECONDS
    total_seconds = max(seconds_until_reset + tail_seconds, MINIMUM_STAGE_SECONDS)
    if total_seconds <= tail_seconds + MINIMUM_STAGE_SECONDS:
        return [total_seconds]
    head_seconds = total_seconds - tail_seconds
    full_stage_count, leftover_seconds = divmod(head_seconds, MAXIMUM_STAGE_SECONDS)
    stages = [MAXIMUM_STAGE_SECONDS] * full_stage_count
    if leftover_seconds >= MINIMUM_STAGE_SECONDS:
        stages.append(leftover_seconds)
    else:
        tail_seconds += leftover_seconds
    stages.append(tail_seconds)
    return stages


def read_oauth_access_token(credentials_path: Path, now: datetime) -> str | None:
    """Read the CLI's OAuth access token when it is still valid.

    Returns None on any of: an unreadable or non-JSON credential file, a
    missing or ill-typed token or expiry field, or a token whose stored
    expiry sits at or before ``now``.

    Args:
        credentials_path: The CLI credential file holding the OAuth section.
        now: The current time the stored expiry is compared against.

    Returns:
        The bearer token for the usage endpoint, or None when unavailable.
    """
    try:
        credentials_payload = json.loads(credentials_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("credential file unreadable at %s", credentials_path)
        return None
    oauth_section = credentials_payload.get(CREDENTIALS_OAUTH_SECTION_KEY)
    if not isinstance(oauth_section, dict):
        logger.warning(
            "credential file has no %s section", CREDENTIALS_OAUTH_SECTION_KEY
        )
        return None
    access_token = oauth_section.get(CREDENTIALS_ACCESS_TOKEN_KEY)
    expires_at_milliseconds = oauth_section.get(CREDENTIALS_EXPIRES_AT_KEY)
    if not isinstance(access_token, str) or not isinstance(
        expires_at_milliseconds, (int, float)
    ):
        logger.warning("credential file is missing the token or its expiry")
        return None
    if expires_at_milliseconds <= now.timestamp() * MILLISECONDS_PER_SECOND:
        logger.warning("stored access token is expired; probe unavailable")
        return None
    return access_token


def _parse_resets_at(raw_resets_at: object) -> datetime | None:
    if isinstance(raw_resets_at, bool):
        return None
    if isinstance(raw_resets_at, (int, float)):
        epoch_seconds = float(raw_resets_at)
        if epoch_seconds > EPOCH_MILLISECONDS_THRESHOLD:
            epoch_seconds /= MILLISECONDS_PER_SECOND
        return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).astimezone()
    if isinstance(raw_resets_at, str):
        try:
            parsed = datetime.fromisoformat(
                raw_resets_at.replace(ISO_UTC_SUFFIX, ISO_UTC_OFFSET)
            )
        except ValueError:
            logger.warning("unreadable resets_at %r", raw_resets_at)
            return None
        return parsed.astimezone()
    return None


def _read_bucket(
    all_usage_buckets: dict[str, object], bucket_key: str
) -> tuple[float | None, datetime | None]:
    bucket = all_usage_buckets.get(bucket_key)
    if not isinstance(bucket, dict):
        return None, None
    raw_utilization = bucket.get(UTILIZATION_KEY)
    utilization = (
        float(raw_utilization) if isinstance(raw_utilization, (int, float)) else None
    )
    resets_at = None
    for each_key in ALL_RESETS_AT_KEYS:
        resets_at = _parse_resets_at(bucket.get(each_key))
        if resets_at is not None:
            break
    return utilization, resets_at


def extract_usage_windows(all_usage_buckets: dict[str, object]) -> UsageWindows:
    """Pull the session and weekly meters out of a usage response body.

    ::

        {"five_hour": {"utilization": 42, "resets_at": "2026-07-08T22:00:00Z"},
         "seven_day": {"utilization": 63, "resets_at": 1783900800}}
        -> UsageWindows(42.0, <today 22:00 UTC>, 63.0, <weekly reset>)

    A reset time arrives as an ISO-8601 string or an epoch number (seconds
    or milliseconds); a missing or unreadable bucket yields None fields.

    Args:
        all_usage_buckets: The decoded JSON body of the OAuth usage response.

    Returns:
        The parsed session and weekly meters.
    """
    session_utilization, session_resets_at = _read_bucket(
        all_usage_buckets, FIVE_HOUR_BUCKET_KEY
    )
    weekly_utilization, weekly_resets_at = _read_bucket(
        all_usage_buckets, SEVEN_DAY_BUCKET_KEY
    )
    return UsageWindows(
        session_utilization=session_utilization,
        session_resets_at=session_resets_at,
        weekly_utilization=weekly_utilization,
        weekly_resets_at=weekly_resets_at,
    )


def build_pause_plan(
    source: str,
    reset_at: datetime,
    now: datetime,
    session_utilization: float | None,
    weekly_utilization: float | None,
    weekly_resets_at: datetime | None,
) -> dict[str, object]:
    """Assemble the resolver's JSON-ready output for one resolved reset time.

    Args:
        source: Where the reset time came from, probe or override.
        reset_at: When the 5-hour window resets.
        now: The current local time the wait is measured from.
        session_utilization: Percent of the 5-hour window spent, when known.
        weekly_utilization: Percent of the weekly window spent, when known.
        weekly_resets_at: When the weekly window resets, when known.

    Returns:
        The plan mapping: source, reset time, seconds until reset, the
        stage plan, both utilization meters, the weekly reset time, and the
        weekly near-cap flag.
    """
    seconds_until_reset = max(int((reset_at - now).total_seconds()), 0)
    weekly_near_cap = (
        weekly_utilization is not None
        and weekly_utilization >= WEEKLY_UTILIZATION_WARN_THRESHOLD
    )
    return {
        RESULT_KEY_SOURCE: source,
        RESULT_KEY_RESET_AT: reset_at.isoformat(),
        RESULT_KEY_SECONDS_UNTIL_RESET: seconds_until_reset,
        RESULT_KEY_STAGES_SECONDS: plan_wakeup_stages(seconds_until_reset),
        RESULT_KEY_SESSION_UTILIZATION: session_utilization,
        RESULT_KEY_WEEKLY_UTILIZATION: weekly_utilization,
        RESULT_KEY_WEEKLY_RESETS_AT: weekly_resets_at.isoformat()
        if weekly_resets_at
        else None,
        RESULT_KEY_WEEKLY_NEAR_CAP: weekly_near_cap,
    }


def _fetch_usage_payload(access_token: str) -> dict[str, object]:
    usage_request = urllib.request.Request(
        OAUTH_USAGE_ENDPOINT_URL,
        headers={
            AUTHORIZATION_HEADER_NAME: f"{AUTHORIZATION_BEARER_PREFIX}{access_token}",
            OAUTH_BETA_HEADER_NAME: OAUTH_BETA_HEADER_VALUE,
            CONTENT_TYPE_HEADER_NAME: CONTENT_TYPE_JSON,
        },
    )
    with urllib.request.urlopen(
        usage_request, timeout=PROBE_TIMEOUT_SECONDS
    ) as usage_reply:
        decoded = json.loads(usage_reply.read())
    if not isinstance(decoded, dict):
        raise ValueError("usage response body is not a JSON object")
    return decoded


def _emit_error(message: str) -> int:
    logger.error("%s", message)
    print(json.dumps({RESULT_KEY_ERROR: message}))
    return EXIT_CODE_PROBE_UNAVAILABLE


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve the 5-hour usage window reset and plan the pause stage chain.",
    )
    parser.add_argument(
        "--override",
        default=None,
        help="Manual reset time (10:20pm, 22:15) or duration (74m, 1h30m); skips the probe.",
    )
    parser.add_argument(
        "--now",
        default=None,
        help="ISO-8601 time to anchor the plan to; defaults to the current local time.",
    )
    parser.add_argument(
        "--credentials-path",
        default=None,
        help="Path to the CLI credential file; defaults to the home-directory location.",
    )
    return parser.parse_args()


def main() -> int:
    """Resolve the usage window from the override or the probe and print the plan.

    Returns:
        0 with the plan JSON on stdout, or 2 with an error JSON when the
        override is unreadable or the probe cannot resolve.
    """
    logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT, stream=sys.stderr)
    arguments = _parse_arguments()
    if arguments.now:
        try:
            now = datetime.fromisoformat(arguments.now).astimezone()
        except ValueError as now_error:
            return _emit_error(f"cannot read --now time {arguments.now!r}: {now_error}")
    else:
        now = datetime.now().astimezone()
    if arguments.override:
        try:
            reset_at = parse_manual_override(arguments.override, now)
        except ValueError as parse_error:
            return _emit_error(str(parse_error))
        print(
            json.dumps(
                build_pause_plan(SOURCE_OVERRIDE, reset_at, now, None, None, None)
            )
        )
        return EXIT_CODE_RESOLVED
    credentials_path = (
        Path(arguments.credentials_path)
        if arguments.credentials_path
        else Path.home().joinpath(*ALL_CREDENTIALS_RELATIVE_PATH_PARTS)
    )
    access_token = read_oauth_access_token(credentials_path, now)
    if access_token is None:
        return _emit_error(
            "OAuth access token unavailable or expired; give a manual reset time, "
            "for example /usage-pause 10:20pm or /usage-pause 74m"
        )
    try:
        usage_payload = _fetch_usage_payload(access_token)
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as probe_error:
        return _emit_error(f"usage probe failed: {probe_error}")
    windows = extract_usage_windows(usage_payload)
    if windows.session_resets_at is None:
        return _emit_error("usage response carried no five_hour reset time")
    print(
        json.dumps(
            build_pause_plan(
                SOURCE_PROBE,
                windows.session_resets_at,
                now,
                windows.session_utilization,
                windows.weekly_utilization,
                windows.weekly_resets_at,
            )
        )
    )
    return EXIT_CODE_RESOLVED


if __name__ == "__main__":
    sys.exit(main())
