"""Put the pr-converge scripts directory on sys.path for the test suite."""

import sys
from pathlib import Path

import pytest

_scripts_directory = Path(__file__).resolve().parent
if str(_scripts_directory) not in sys.path:
    sys.path.insert(0, str(_scripts_directory))

import check_convergence_availability  # noqa: E402
from pr_loop_shared_constants.reviews_disabled_constants import (  # noqa: E402
    CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN,
    CLAUDE_REVIEWS_DISABLED_CODEX_TOKEN,
    CLAUDE_REVIEWS_DISABLED_TOKEN_SEPARATOR,
    CLAUDE_REVIEWS_ENABLED_ENV_VAR_NAME,
)

_MISSING_SETTINGS_FILENAME = "settings-absent-in-tests.json"


@pytest.fixture(autouse=True)
def opt_gated_reviewers_in(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point settings at an absent file and opt bugteam and codex in.

    Bugteam and codex are off by default, and the resolver reads the real
    ``~/.claude/settings.json`` first. Both together would decide these cases
    from whatever the host machine has on disk. Aiming the resolver at an
    absent path restores the env fallback, and the opt-in lets each case reach
    the gate it was written for. A case that tests the lists themselves
    overrides this from its own body.
    """
    monkeypatch.setattr(
        check_convergence_availability,
        "get_claude_user_settings_path",
        lambda: tmp_path / _MISSING_SETTINGS_FILENAME,
    )
    all_opted_in_tokens = CLAUDE_REVIEWS_DISABLED_TOKEN_SEPARATOR.join(
        (CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN, CLAUDE_REVIEWS_DISABLED_CODEX_TOKEN)
    )
    monkeypatch.setenv(CLAUDE_REVIEWS_ENABLED_ENV_VAR_NAME, all_opted_in_tokens)
