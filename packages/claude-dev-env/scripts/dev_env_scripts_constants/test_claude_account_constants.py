"""The second-account thresholds keep the main account the protected one."""

from __future__ import annotations

from dev_env_scripts_constants.claude_account_constants import (
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
