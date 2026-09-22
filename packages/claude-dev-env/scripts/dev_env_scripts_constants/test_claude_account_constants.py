"""The second-account thresholds keep the main account the protected one."""

from __future__ import annotations

from dev_env_scripts_constants.claude_account_constants import (
    JSON_ACCOUNT_KEY,
    JSON_CONFIG_DIRECTORY_KEY,
    JSON_METERS_KEY,
    JSON_REASON_KEY,
    JSON_SESSION_RESETS_AT_KEY,
    JSON_SESSION_USED_PERCENT_KEY,
    JSON_WEEKLY_RESETS_AT_KEY,
    JSON_WEEKLY_USED_PERCENT_KEY,
    LAUNCHER_TEXT_TEMPLATE,
    MAIN_SESSION_USED_CEILING_PERCENT,
    MAIN_WEEKLY_USED_CEILING_PERCENT,
    SECOND_SESSION_USED_CEILING_PERCENT,
    SECOND_WEEKLY_USED_CEILING_PERCENT,
)


def test_main_ceilings_sit_below_the_second_account_ceilings() -> None:
    assert MAIN_WEEKLY_USED_CEILING_PERCENT < SECOND_WEEKLY_USED_CEILING_PERCENT
    assert MAIN_SESSION_USED_CEILING_PERCENT < SECOND_SESSION_USED_CEILING_PERCENT


def test_launcher_names_the_profile_and_passes_every_argument() -> None:
    assert "{profile_home}" in LAUNCHER_TEXT_TEMPLATE
    assert "claude %*" in LAUNCHER_TEXT_TEMPLATE


def test_picker_report_keys_never_collide() -> None:
    all_report_keys = [
        JSON_ACCOUNT_KEY,
        JSON_CONFIG_DIRECTORY_KEY,
        JSON_REASON_KEY,
        JSON_METERS_KEY,
    ]
    all_meter_keys = [
        JSON_SESSION_USED_PERCENT_KEY,
        JSON_SESSION_RESETS_AT_KEY,
        JSON_WEEKLY_USED_PERCENT_KEY,
        JSON_WEEKLY_RESETS_AT_KEY,
    ]
    assert len(set(all_report_keys)) == len(all_report_keys)
    assert len(set(all_meter_keys)) == len(all_meter_keys)
