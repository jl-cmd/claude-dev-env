"""Decide which PR reviewers run from the opt-out and opt-in env token lists.

::

    enabled lists bugbot, disabled empty    -> bugbot   ok:   runs
    no lists set                            -> bugbot   flag: off (default)
    enabled lists bugbot, disabled bugbot   -> bugbot   flag: off (opt-out wins)
    disabled empty                          -> bugteam  ok:   runs
    disabled lists copilot                  -> copilot  flag: off

Bugbot is off by default and runs only when the enabled list names it.
Bugteam and copilot run by default and stop only when the disabled list
names them; both lists parse case-insensitively and tolerate whitespace.
"""

from __future__ import annotations

import argparse
import os
import sys

from pr_loop_shared_constants.reviews_disabled_constants import (
    CLAUDE_REVIEWS_DISABLED_BUGBOT_TOKEN,
    CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN,
    CLAUDE_REVIEWS_DISABLED_CODEX_TOKEN,
    CLAUDE_REVIEWS_DISABLED_COPILOT_TOKEN,
    CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME,
    CLAUDE_REVIEWS_DISABLED_TOKEN_SEPARATOR,
    CLAUDE_REVIEWS_ENABLED_ENV_VAR_NAME,
    EXIT_CODE_BUGTEAM_DISABLED_VIA_ENV,
)


__all__ = [
    "CLAUDE_REVIEWS_DISABLED_BUGBOT_TOKEN",
    "CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN",
    "CLAUDE_REVIEWS_DISABLED_CODEX_TOKEN",
    "CLAUDE_REVIEWS_DISABLED_COPILOT_TOKEN",
    "CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME",
    "CLAUDE_REVIEWS_DISABLED_TOKEN_SEPARATOR",
    "CLAUDE_REVIEWS_ENABLED_ENV_VAR_NAME",
    "EXIT_CODE_BUGTEAM_DISABLED_VIA_ENV",
    "is_bugbot_disabled_via_env",
    "is_bugbot_opted_out_via_env",
    "is_bugteam_disabled_via_env",
    "is_codex_disabled_via_env",
    "is_copilot_disabled_via_env",
    "main",
]


def _is_reviewer_listed_in_env(
    environment_variable_name: str, reviewer_token: str
) -> bool:
    """Check whether an environment variable lists the given reviewer token.

    Args:
        environment_variable_name: The environment variable to read, either
            the reviews-disabled or the reviews-enabled variable name.
        reviewer_token: The reviewer token to look for, already lowercase
            (for example the bugteam or bugbot token constant).

    Returns:
        True when the env var contains ``reviewer_token`` as one of its
        comma-separated entries (case-insensitive, whitespace-tolerant).
    """
    reviews_token_separator = CLAUDE_REVIEWS_DISABLED_TOKEN_SEPARATOR
    listed_reviewers_text = os.environ.get(environment_variable_name, "")
    all_listed_tokens = frozenset(
        each_raw_token.strip().lower()
        for each_raw_token in listed_reviewers_text.split(reviews_token_separator)
        if each_raw_token.strip()
    )
    return reviewer_token in all_listed_tokens


def is_bugteam_disabled_via_env() -> bool:
    """Check whether CLAUDE_REVIEWS_DISABLED opts the bug-audit family out.

    Returns:
        True when the env var lists the ``bugteam`` token.
    """
    return _is_reviewer_listed_in_env(
        CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME, CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN
    )


def is_bugbot_disabled_via_env() -> bool:
    """Check whether Cursor Bugbot is disabled for this run.

    Cursor Bugbot is off by default. It runs only when
    ``CLAUDE_REVIEWS_ENABLED`` lists ``bugbot``, and a ``bugbot`` token in
    ``CLAUDE_REVIEWS_DISABLED`` forces it off even when the opt-in lists it.

    Returns:
        True when ``CLAUDE_REVIEWS_DISABLED`` lists ``bugbot`` or when
        ``CLAUDE_REVIEWS_ENABLED`` does not list ``bugbot``.
    """
    is_opted_out = _is_reviewer_listed_in_env(
        CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME, CLAUDE_REVIEWS_DISABLED_BUGBOT_TOKEN
    )
    is_opted_in = _is_reviewer_listed_in_env(
        CLAUDE_REVIEWS_ENABLED_ENV_VAR_NAME, CLAUDE_REVIEWS_DISABLED_BUGBOT_TOKEN
    )
    return is_opted_out or not is_opted_in


def is_bugbot_opted_out_via_env() -> bool:
    """Check whether CLAUDE_REVIEWS_DISABLED opts Cursor Bugbot out.

    The opt-out forces Bugbot off even when ``CLAUDE_REVIEWS_ENABLED`` lists
    ``bugbot``. This reports only the opt-out signal, where
    ``is_bugbot_disabled_via_env`` also reports off for the default case in
    which neither env var names ``bugbot``.

    Returns:
        True when ``CLAUDE_REVIEWS_DISABLED`` lists the ``bugbot`` token.
    """
    return _is_reviewer_listed_in_env(
        CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME, CLAUDE_REVIEWS_DISABLED_BUGBOT_TOKEN
    )


def is_copilot_disabled_via_env() -> bool:
    """Check whether CLAUDE_REVIEWS_DISABLED opts GitHub Copilot out.

    Returns:
        True when the env var lists the ``copilot`` token.
    """
    return _is_reviewer_listed_in_env(
        CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME, CLAUDE_REVIEWS_DISABLED_COPILOT_TOKEN
    )


def is_codex_disabled_via_env() -> bool:
    """Check whether CLAUDE_REVIEWS_DISABLED opts the Codex reviewer out.

    Returns:
        True when the env var lists the ``codex`` token.
    """
    return _is_reviewer_listed_in_env(
        CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME, CLAUDE_REVIEWS_DISABLED_CODEX_TOKEN
    )


def parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments for the reviewer opt-out and opt-in gate check.

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
            CLAUDE_REVIEWS_DISABLED_COPILOT_TOKEN,
            CLAUDE_REVIEWS_DISABLED_CODEX_TOKEN,
        ],
        help="Reviewer token to test against the CLAUDE_REVIEWS_DISABLED / CLAUDE_REVIEWS_ENABLED gates",
    )
    return parser.parse_args(all_argv)


def main(all_arguments: list[str]) -> int:
    """Exit 0 when the named reviewer is disabled for this run.

    Args:
        all_arguments: Argument list excluding the program name.

    Returns:
        0 when the named reviewer is disabled for this run, 1 otherwise.
    """
    arguments = parse_arguments(all_arguments)
    disabled_checker_by_reviewer = {
        CLAUDE_REVIEWS_DISABLED_BUGBOT_TOKEN: is_bugbot_disabled_via_env,
        CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN: is_bugteam_disabled_via_env,
        CLAUDE_REVIEWS_DISABLED_COPILOT_TOKEN: is_copilot_disabled_via_env,
        CLAUDE_REVIEWS_DISABLED_CODEX_TOKEN: is_codex_disabled_via_env,
    }
    return 0 if disabled_checker_by_reviewer[arguments.reviewer]() else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
