"""Shared helper for the CLAUDE_REVIEWS_DISABLED opt-out gate.

Both ``skills/bugteam/scripts/bugteam_preflight.py`` and
``_shared/pr-loop/scripts/preflight.py`` consume this helper so the parsing
rules and disabled-token taxonomy live in exactly one place.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

for each_cached_module_name in [
    each_module_key
    for each_module_key in list(sys.modules)
    if each_module_key == "config" or each_module_key.startswith("config.")
]:
    sys.modules.pop(each_cached_module_name, None)
_shared_pr_loop_scripts_directory = str(Path(__file__).absolute().parent)
while _shared_pr_loop_scripts_directory in sys.path:
    sys.path.remove(_shared_pr_loop_scripts_directory)
if _shared_pr_loop_scripts_directory not in sys.path:
    sys.path.insert(0, _shared_pr_loop_scripts_directory)

from config.reviews_disabled_constants import (
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
