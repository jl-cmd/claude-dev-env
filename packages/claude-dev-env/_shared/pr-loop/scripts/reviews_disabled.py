"""Shared helper for the CLAUDE_REVIEWS_DISABLED opt-out gate.

Both ``skills/bugteam/scripts/bugteam_preflight.py`` and
``_shared/pr-loop/scripts/preflight.py`` consume this helper so the parsing
rules and disabled-token taxonomy live in exactly one place.
"""

from __future__ import annotations

import argparse
import os
import sys

from pr_loop_shared_constants.reviews_disabled_constants import (
    CLAUDE_REVIEWS_DISABLED_BUGBOT_TOKEN,
    CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN,
    CLAUDE_REVIEWS_DISABLED_COPILOT_TOKEN,
    CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME,
    CLAUDE_REVIEWS_DISABLED_TOKEN_SEPARATOR,
    EXIT_CODE_BUGTEAM_DISABLED_VIA_ENV,
)


__all__ = [
    "CLAUDE_REVIEWS_DISABLED_BUGBOT_TOKEN",
    "CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN",
    "CLAUDE_REVIEWS_DISABLED_COPILOT_TOKEN",
    "CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME",
    "CLAUDE_REVIEWS_DISABLED_TOKEN_SEPARATOR",
    "EXIT_CODE_BUGTEAM_DISABLED_VIA_ENV",
    "is_bugbot_disabled_via_env",
    "is_bugteam_disabled_via_env",
    "is_copilot_disabled_via_env",
    "main",
]


def _is_reviewer_disabled_via_env(reviewer_token: str) -> bool:
    """Check whether CLAUDE_REVIEWS_DISABLED lists the given reviewer token.

    Args:
        reviewer_token: The reviewer token to look for, already lowercase
            (for example the bugteam or bugbot token constant).

    Returns:
        True when the env var contains ``reviewer_token`` as one of its
        comma-separated entries (case-insensitive, whitespace-tolerant).
    """
    reviews_disabled_token_separator = CLAUDE_REVIEWS_DISABLED_TOKEN_SEPARATOR
    disabled_reviewers_text = os.environ.get(CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME, "")
    all_disabled_tokens = frozenset(
        each_raw_token.strip().lower()
        for each_raw_token in disabled_reviewers_text.split(
            reviews_disabled_token_separator
        )
        if each_raw_token.strip()
    )
    return reviewer_token in all_disabled_tokens


def is_bugteam_disabled_via_env() -> bool:
    """Check whether CLAUDE_REVIEWS_DISABLED opts the bug-audit family out.

    Returns:
        True when the env var lists the ``bugteam`` token.
    """
    return _is_reviewer_disabled_via_env(CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN)


def is_bugbot_disabled_via_env() -> bool:
    """Check whether CLAUDE_REVIEWS_DISABLED opts Cursor Bugbot out.

    Returns:
        True when the env var lists the ``bugbot`` token.
    """
    return _is_reviewer_disabled_via_env(CLAUDE_REVIEWS_DISABLED_BUGBOT_TOKEN)


def is_copilot_disabled_via_env() -> bool:
    """Check whether CLAUDE_REVIEWS_DISABLED opts GitHub Copilot out.

    Returns:
        True when the env var lists the ``copilot`` token.
    """
    return _is_reviewer_disabled_via_env(CLAUDE_REVIEWS_DISABLED_COPILOT_TOKEN)


def parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments for the reviewer opt-out check.

    Args:
        all_argv: Argument list excluding the program name, typically
            ``sys.argv[1:]``.

    Returns:
        Namespace exposing a ``reviewer`` attribute constrained to the
        known reviewer tokens.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reviewer",
        required=True,
        choices=[
            CLAUDE_REVIEWS_DISABLED_BUGBOT_TOKEN,
            CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN,
        ],
        help="Reviewer token to test against CLAUDE_REVIEWS_DISABLED",
    )
    return parser.parse_args(all_argv)


def main(all_arguments: list[str]) -> int:
    """Exit 0 when the named reviewer is disabled via CLAUDE_REVIEWS_DISABLED.

    Args:
        all_arguments: Argument list excluding the program name.

    Returns:
        0 when the named reviewer is opted out by the env var, 1 otherwise.
    """
    arguments = parse_arguments(all_arguments)
    disabled_checker_by_reviewer = {
        CLAUDE_REVIEWS_DISABLED_BUGBOT_TOKEN: is_bugbot_disabled_via_env,
        CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN: is_bugteam_disabled_via_env,
    }
    return 0 if disabled_checker_by_reviewer[arguments.reviewer]() else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
