"""Name the check behind one finding of a bundling rule.

::

    rule "code-rules", "Line 3: Constant TIMEOUT - move to config/"
      -> code-rules/constant-outside-config
    rule "code-rules", "Line 4: something no entry names"
      -> code-rules/unclassified
    rule "rmtree-safety", any message
      -> rmtree-safety

A consumer partitions findings into blocking and advisory ones by this
identifier. A message no catalog entry names resolves to the unclassified
identifier, which a partition treats as blocking, so a reworded message
reports louder rather than quieter.
"""

from __future__ import annotations

from .config.check_catalog_constants import (
    ALL_BUNDLING_RULE_IDS,
    ALL_CHECK_CATALOG_ENTRIES,
    CHECK_ID_SEPARATOR,
    UNCLASSIFIED_CHECK_NAME,
)


def check_id_for_message(rule_id: str, message: str) -> str:
    """Return the check identifier one rule and message resolve to.

    Args:
        rule_id: The rule that raised the finding.
        message: The finding's message text.

    Returns:
        The rule identifier for a rule that runs one check, or the rule
        identifier joined to the name of the check the message names.
    """
    if rule_id not in ALL_BUNDLING_RULE_IDS:
        return rule_id
    for each_entry in ALL_CHECK_CATALOG_ENTRIES:
        if each_entry.message_marker in message:
            return rule_id + CHECK_ID_SEPARATOR + each_entry.check_name
    return rule_id + CHECK_ID_SEPARATOR + UNCLASSIFIED_CHECK_NAME
