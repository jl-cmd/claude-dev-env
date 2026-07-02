"""Unified reviewer-availability pre-check for GitHub Copilot and Cursor Bugbot.

Run this before either reviewer step spawns. It answers one question: is the
named reviewer available to run right now. It reuses two existing checks
instead of re-implementing their rules. The ``CLAUDE_REVIEWS_DISABLED``
opt-out gate lives in ``reviews_disabled.py``. The Copilot premium-interaction
quota pre-check lives in ``copilot_quota.py``.

Copilot counts as down in two cases: it is opted out via
``CLAUDE_REVIEWS_DISABLED``, or its quota pre-check returns anything other
than quota available (out of quota, the quota API or account down, or no
account configured).

Bugbot carries no quota or availability API. It counts as down only when it
is opted out via ``CLAUDE_REVIEWS_DISABLED``. A genuine runtime outage shows
up later as a poll timeout, not here.

The exit code tells the caller what to do. Exit 0 means the reviewer is
available and may be spawned. The documented down code (3) means skip it. Any
other non-zero exit is a broken check — an interpreter crash or a usage
error — not a down report, so a gating caller fails open on it. Every path
prints one line: available lines go to stdout, down lines go to stderr.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from copilot_quota import (
    COPILOT_QUOTA_DEFAULT_ENV_FILE_PATH,
    EXIT_CODE_QUOTA_AVAILABLE,
    evaluate_copilot_quota,
)
from pr_loop_shared_constants.reviewer_availability_constants import (
    EXIT_CODE_REVIEWER_AVAILABLE,
    EXIT_CODE_REVIEWER_DOWN,
)
from pr_loop_shared_constants.reviews_disabled_constants import (
    CLAUDE_REVIEWS_DISABLED_BUGBOT_TOKEN,
    CLAUDE_REVIEWS_DISABLED_COPILOT_TOKEN,
    CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME,
)
from reviews_disabled import is_bugbot_disabled_via_env, is_copilot_disabled_via_env


@dataclass(frozen=True)
class ReviewerAvailability:
    """One reviewer-availability outcome: the exit code and the single log line.

    The exit code tells the caller what to do, where 0 means the reviewer may
    be spawned and the documented down code (3) means skip it. The CLI prints
    the message on one line, to stdout when available and to stderr when down.
    """

    exit_code: int
    message: str


def _evaluate_copilot_availability(env_file_path: Path) -> ReviewerAvailability:
    """Decide whether GitHub Copilot is available to spawn.

    Args:
        env_file_path: The ``.env`` file the quota pre-check consults for the
            configured account when neither the flag nor the environment
            variable names one.

    Returns:
        A ReviewerAvailability that is down when Copilot is opted out via
        ``CLAUDE_REVIEWS_DISABLED`` or the quota pre-check reports anything
        other than quota available, and available otherwise.
    """
    if is_copilot_disabled_via_env():
        return ReviewerAvailability(
            EXIT_CODE_REVIEWER_DOWN,
            f"reviewer-availability: copilot is disabled via "
            f"{CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME} — skipping.",
        )
    quota_decision = evaluate_copilot_quota(cli_account=None, env_file_path=env_file_path)
    if quota_decision.exit_code != EXIT_CODE_QUOTA_AVAILABLE:
        return ReviewerAvailability(EXIT_CODE_REVIEWER_DOWN, quota_decision.message)
    return ReviewerAvailability(EXIT_CODE_REVIEWER_AVAILABLE, quota_decision.message)


def _evaluate_bugbot_availability() -> ReviewerAvailability:
    """Decide whether Cursor Bugbot is available to spawn.

    Bugbot carries no quota or availability API, so this checks only the
    deterministic ``CLAUDE_REVIEWS_DISABLED`` opt-out.

    Returns:
        A ReviewerAvailability that is down when Bugbot is opted out via
        ``CLAUDE_REVIEWS_DISABLED``, and available otherwise.
    """
    if is_bugbot_disabled_via_env():
        return ReviewerAvailability(
            EXIT_CODE_REVIEWER_DOWN,
            f"reviewer-availability: bugbot is disabled via "
            f"{CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME} — skipping.",
        )
    return ReviewerAvailability(
        EXIT_CODE_REVIEWER_AVAILABLE,
        "reviewer-availability: bugbot is available.",
    )


def evaluate_reviewer_availability(
    reviewer_token: str, env_file_path: Path
) -> ReviewerAvailability:
    """Decide whether the named reviewer is available to spawn.

    Args:
        reviewer_token: Either the Copilot or the Bugbot reviewer token.
        env_file_path: The ``.env`` file the Copilot quota pre-check consults
            for the configured account.

    Returns:
        The ReviewerAvailability for the named reviewer.

    Raises:
        ValueError: When reviewer_token names neither the Copilot nor the
            Bugbot reviewer token.
    """
    if reviewer_token == CLAUDE_REVIEWS_DISABLED_COPILOT_TOKEN:
        return _evaluate_copilot_availability(env_file_path)
    if reviewer_token == CLAUDE_REVIEWS_DISABLED_BUGBOT_TOKEN:
        return _evaluate_bugbot_availability()
    raise ValueError(f"unknown reviewer token: {reviewer_token}")


def _parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments for the reviewer-availability check.

    Args:
        all_argv: Argument list excluding the program name, typically
            ``sys.argv[1:]``.

    Returns:
        Namespace exposing a ``reviewer`` attribute constrained to the
        Copilot and Bugbot reviewer tokens.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reviewer",
        required=True,
        choices=[
            CLAUDE_REVIEWS_DISABLED_COPILOT_TOKEN,
            CLAUDE_REVIEWS_DISABLED_BUGBOT_TOKEN,
        ],
        help="Reviewer to check availability for",
    )
    return parser.parse_args(all_argv)


def main(all_arguments: list[str]) -> int:
    """Run the reviewer-availability check end-to-end and print its decision.

    Args:
        all_arguments: Argument list excluding the program name.

    Returns:
        0 when the named reviewer is available to spawn, the documented
        reviewer-down exit code when it is down.
    """
    arguments = _parse_arguments(all_arguments)
    availability = evaluate_reviewer_availability(
        reviewer_token=arguments.reviewer,
        env_file_path=COPILOT_QUOTA_DEFAULT_ENV_FILE_PATH,
    )
    message_stream = (
        sys.stdout
        if availability.exit_code == EXIT_CODE_REVIEWER_AVAILABLE
        else sys.stderr
    )
    print(availability.message, file=message_stream)
    return availability.exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
