"""Shared helper for the CLAUDE_REVIEWS_DISABLED opt-out gate.

Both ``skills/bugteam/scripts/bugteam_preflight.py`` and
``_shared/pr-loop/scripts/preflight.py`` consume this helper so the parsing
rules and disabled-token taxonomy live in exactly one place.
"""

from __future__ import annotations

import os

from pr_loop_shared_constants.reviews_disabled_constants import (
    CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN,
    CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME,
    CLAUDE_REVIEWS_DISABLED_TOKEN_SEPARATOR,
    EXIT_CODE_BUGTEAM_DISABLED_VIA_ENV,
)


__all__ = [
    "CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN",
    "CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME",
    "CLAUDE_REVIEWS_DISABLED_TOKEN_SEPARATOR",
    "EXIT_CODE_BUGTEAM_DISABLED_VIA_ENV",
    "is_bugteam_disabled_via_env",
]


def is_bugteam_disabled_via_env() -> bool:
    """Check whether CLAUDE_REVIEWS_DISABLED opts the bug-audit family out of running.

    Returns:
        True when the env var contains the literal ``bugteam`` token
        (comma-separated, case-insensitive, whitespace-tolerant).
    """
    reviews_disabled_env_var_name = CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME
    reviews_disabled_token_separator = CLAUDE_REVIEWS_DISABLED_TOKEN_SEPARATOR
    reviews_disabled_bugteam_token = CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN
    raw_value = os.environ.get(reviews_disabled_env_var_name, "")
    all_disabled_tokens = frozenset(
        each_raw_token.strip().lower()
        for each_raw_token in raw_value.split(reviews_disabled_token_separator)
        if each_raw_token.strip()
    )
    return reviews_disabled_bugteam_token in all_disabled_tokens
