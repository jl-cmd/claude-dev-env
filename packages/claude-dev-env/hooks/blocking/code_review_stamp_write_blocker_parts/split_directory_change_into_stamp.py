"""Decide whether a split directory change reaches the stamp directory then runs a command.

A change into the Claude home (``cd ~/.claude``) followed by a change into a
relative ``code-review-stamps`` directory (``cd code-review-stamps``) lands in
the stamp directory without ever naming the two segments adjacently, so the
absolute-path matcher and the single-step ``cd ~/.claude/code-review-stamps``
matcher both miss it. The trust contract denies every shell command that
reaches the stamp directory, so any command after the second change — a
redirect, ``cp``, ``mv``, ``tee``, ``install``, or a ``python -c`` write — is a
forge vector. An unrelated second change (``cd hooks``) lands elsewhere and
passes.

The entry hook registers the constant packages before importing this module, so
the ``from config...`` imports below resolve against the sibling ``config/``
package without a bootstrap call here.
"""

from __future__ import annotations

import re

from config.code_review_enforcement_constants import STAMP_DIRECTORY_CHANGE_TARGET_PATTERN
from config.verified_commit_constants import (
    CLAUDE_HOME_DIRECTORY_NAME,
    CLAUDE_HOME_TARGET_BOUNDARY_PATTERN,
    COMMAND_AFTER_DIRECTORY_CHANGE_PATTERN,
    DIRECTORY_CHANGE_OPTION_PREFIX_PATTERN,
    DIRECTORY_CHANGE_OPTION_TERMINATOR,
    DIRECTORY_CHANGE_PATH_OPTIONS,
    DIRECTORY_CHANGE_PATTERN_PREFIX,
    DIRECTORY_CHANGE_PATTERN_SUFFIX,
    DIRECTORY_CHANGE_TARGET_PATTERN,
    DIRECTORY_CHANGE_VERBS,
)
from config.verified_commit_gate_output_constants import REGEX_ALTERNATION_SEPARATOR


def _directory_change_verbs_pattern() -> str:
    """Build the alternation of directory-change verbs for a change matcher.

    Returns:
        The regex alternation of escaped directory-change verbs in sorted order.
    """
    return REGEX_ALTERNATION_SEPARATOR.join(
        re.escape(each_verb) for each_verb in sorted(DIRECTORY_CHANGE_VERBS)
    )


def _directory_change_option_prefix_pattern() -> str:
    """Build the optional path-option prefix that may precede a change target.

    Returns:
        The regex matching zero or more leading path-option or terminator
        tokens, ready to sit between the change suffix and target patterns.
    """
    option_alternation = REGEX_ALTERNATION_SEPARATOR.join(
        re.escape(each_option)
        for each_option in sorted(
            DIRECTORY_CHANGE_PATH_OPTIONS | {DIRECTORY_CHANGE_OPTION_TERMINATOR}
        )
    )
    return DIRECTORY_CHANGE_OPTION_PREFIX_PATTERN % option_alternation


def _directory_change_prefix() -> str:
    """Build the change-verb prefix shared by both directory-change matchers.

    Returns:
        The regex prefix matching a directory-change verb and any leading
        path-option tokens, ready for a target pattern to follow.
    """
    return (
        DIRECTORY_CHANGE_PATTERN_PREFIX
        + _directory_change_verbs_pattern()
        + DIRECTORY_CHANGE_PATTERN_SUFFIX
        + _directory_change_option_prefix_pattern()
    )


def _change_into_claude_pattern() -> re.Pattern[str]:
    """Build the compiled matcher for a directory change into the Claude home.

    Returns:
        The compiled, case-insensitive pattern matching a change verb into any
        path ending in ``.claude``.
    """
    return re.compile(
        _directory_change_prefix()
        + DIRECTORY_CHANGE_TARGET_PATTERN
        + re.escape(CLAUDE_HOME_DIRECTORY_NAME)
        + CLAUDE_HOME_TARGET_BOUNDARY_PATTERN,
        re.IGNORECASE,
    )


def _change_into_stamp_pattern() -> re.Pattern[str]:
    """Build the compiled matcher for a directory change into the stamp directory.

    Returns:
        The compiled, case-insensitive pattern matching a change verb into a
        relative ``code-review-stamps`` directory.
    """
    return re.compile(
        _directory_change_prefix() + STAMP_DIRECTORY_CHANGE_TARGET_PATTERN, re.IGNORECASE
    )


def changes_through_split_directory_into_stamp(command_text: str) -> bool:
    """Decide whether a split change reaches the stamp directory then runs a command.

    ::

        cd ~/.claude && cd code-review-stamps && echo x > f.json  -> True
        cd ~/.claude && cd hooks && echo x > f.json               -> False

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        True when a change into the Claude home precedes a change into a
        relative stamp directory that is itself followed by any further command.
    """
    change_into_claude_match = _change_into_claude_pattern().search(command_text)
    if change_into_claude_match is None:
        return False
    change_into_stamp_match = _change_into_stamp_pattern().search(
        command_text, change_into_claude_match.end()
    )
    if change_into_stamp_match is None:
        return False
    command_after_change_pattern = re.compile(COMMAND_AFTER_DIRECTORY_CHANGE_PATTERN)
    return (
        command_after_change_pattern.search(command_text, change_into_stamp_match.end()) is not None
    )
