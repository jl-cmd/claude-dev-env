"""Single source of truth for opinionated prose-style gate opt-in.

::

    CLAUDE_PROSE_STYLE_ENFORCEMENT=1  ->  PROSE_STYLE_ENFORCEMENT_ENABLED True
    (unset)                           ->  PROSE_STYLE_ENFORCEMENT_ENABLED False

Structural AskUserQuestion lean-block validation stays always on. The flag
arms only opinionated prose gates (heavy-word swaps, hedging, historical
state phrasing, intent-only endings, hook prose-detector consistency).
"""

from __future__ import annotations

import os

PROSE_STYLE_ENFORCEMENT_ENV_VAR = "CLAUDE_PROSE_STYLE_ENFORCEMENT"
ALL_ENFORCEMENT_ENABLED_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


def prose_style_enforcement_enabled_in_environment() -> bool:
    """Read whether this machine turns opinionated prose gates on.

    ::

        CLAUDE_PROSE_STYLE_ENFORCEMENT=1      -> True
        CLAUDE_PROSE_STYLE_ENFORCEMENT=" On " -> True
        CLAUDE_PROSE_STYLE_ENFORCEMENT=0      -> False
        (variable unset)                      -> False

    Returns:
        True when the variable holds an enabled value, False otherwise.
    """
    raw_environment_setting = os.environ.get(PROSE_STYLE_ENFORCEMENT_ENV_VAR, "")
    return raw_environment_setting.strip().lower() in ALL_ENFORCEMENT_ENABLED_ENV_VALUES


PROSE_STYLE_ENFORCEMENT_ENABLED = prose_style_enforcement_enabled_in_environment()
