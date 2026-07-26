"""Single source of truth for the shared prose-style enforcement switch.

Holds the master flag ``PROSE_STYLE_ENFORCEMENT_ENABLED`` (default off) that
every prose-style hook reads before it blocks anything, the roster of hook
modules that read it, and the flag name a coverage test greps for.

::

    PROSE_STYLE_ENFORCEMENT_ENABLED = False
    ok:   a hedging word, a heavy word, a prose question, a promise ending,
          and historical wording all pass untouched, with no hook output
    flag: set the constant to True and all five hooks block again

Set the flag to ``True`` in this file to turn every prose-style hook back on.
When the flag is ``False`` each hook returns before it inspects any text, so it
writes nothing at all: it neither blocks nor reports.
"""

from __future__ import annotations

PROSE_STYLE_ENFORCEMENT_ENABLED = False
PROSE_STYLE_ENFORCEMENT_FLAG_NAME = "PROSE_STYLE_ENFORCEMENT_ENABLED"
ALL_PROSE_STYLE_HOOK_MODULE_NAMES = (
    "hedging_language_blocker",
    "question_to_user_enforcer",
    "intent_only_ending_blocker",
    "plain_language_blocker",
    "state_description_blocker",
)
