"""Test fixtures for _shared/pr-loop/scripts/tests/."""

import pytest
from pr_loop_shared_constants.reviews_disabled_constants import (
    CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN,
    CLAUDE_REVIEWS_ENABLED_ENV_VAR_NAME,
)


@pytest.fixture(autouse=True)
def opt_bugteam_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """Opt bugteam in so each case exercises its own check, not the default off.

    Bugteam is off by default, so a preflight case that never mentions the
    reviewer lists halts on the opt-in check before reaching the behavior it
    was written for. A case that tests those lists overrides this from its own
    body, where monkeypatch runs after the fixture.
    """
    monkeypatch.setenv(
        CLAUDE_REVIEWS_ENABLED_ENV_VAR_NAME, CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN
    )
