"""Shared detection for the agent-model-pin blocker.

Both the blocker and the agent-frontmatter test suite import these helpers, so
the pin question is read one way on both surfaces. The frontmatter block is
isolated by line-anchored fences (a fence is a line that is exactly ``---``,
reached past any byte-order mark and leading blank lines). The last top-level
``model:`` line is read by a single deterministic stdlib scan — no YAML runtime
dependency and no fallback pass — so the dispatcher that hosts this hook loads on
a stdlib-only Python. The scan classifies the line as unset, a concrete pin, or
malformed. ``test_agent_model_pin_detection`` pins the concrete/unset verdicts to
``yaml.safe_load`` as an oracle over the well-formed matrix, and holds the
malformed and intentional over-catch cases to their own contract.

The scan strips ASCII whitespace only, matching YAML: a non-breaking space is a
value character, so ``model: \\xa0`` reads as a concrete pin rather than unset.
"""

from __future__ import annotations

import re

from hooks_constants.agent_model_pin_blocker_constants import (
    ALL_NON_AGENT_MARKDOWN_FILENAMES,
    ALL_NULL_MODEL_VALUES,
    ASCII_WHITESPACE,
    BLOCK_SCALAR_INDICATOR_CHARACTERS,
    BYTE_ORDER_MARK,
    FRONTMATTER_FENCE,
    INHERIT_MODEL_VALUE,
    INLINE_COMMENT_PATTERN,
    INSTALLED_AGENTS_PATH_FRAGMENT,
    MARKDOWN_EXTENSION,
    MODEL_VALUE_QUOTE_CHARACTERS,
    PACKAGE_AGENTS_PATH_FRAGMENT,
    TOP_LEVEL_MODEL_LINE_PATTERN,
)

__all__ = [
    "extract_frontmatter_block",
    "pinned_or_malformed",
    "pinned_model_value",
    "frontmatter_pins_concrete_model",
    "is_agent_definition_path",
]


def _opening_fence_index(all_lines: list[str]) -> int | None:
    """Return the index of the opening frontmatter fence, or None.

    Leading blank lines are skipped, and the first non-blank line opens the
    frontmatter only when it is a fence line.
    """
    for each_index, each_line in enumerate(all_lines):
        if not each_line.strip():
            continue
        return each_index if each_line.rstrip() == FRONTMATTER_FENCE else None
    return None


def extract_frontmatter_block(file_content: str) -> str | None:
    """Return the frontmatter block a file opens with, or None when it has none.

    A byte-order mark and any leading blank lines are skipped before the opening
    fence. A fence is a line that is exactly ``---`` (trailing whitespace
    allowed), so a ``---`` inside a description line neither opens nor closes the
    block. The block is the text between the opening fence and the next fence.
    """
    all_lines = file_content.lstrip(BYTE_ORDER_MARK).splitlines()
    opening_index = _opening_fence_index(all_lines)
    if opening_index is None:
        return None
    for each_index in range(opening_index + 1, len(all_lines)):
        if all_lines[each_index].rstrip() == FRONTMATTER_FENCE:
            return "\n".join(all_lines[opening_index + 1 : each_index])
    return None


def _trailing_is_blank_or_comment(trailing_text: str) -> bool:
    """Return whether text after a closing quote is only whitespace and a comment."""
    remainder = trailing_text.strip(ASCII_WHITESPACE)
    return remainder == "" or remainder.startswith("#")


def _scan_quoted_value(after_colon: str, quote_character: str) -> tuple[str | None, bool]:
    """Read a quoted model value: valid only when the close quote ends the line.

    A trailing whitespace-and-comment run after the close quote is allowed. Any
    other content after it, or a quote that never closes, is malformed::

        "opus"          -> ("opus", False)
        "opus"  # note  -> ("opus", False)
        "opus"x         -> (None, True)
        'opus           -> (None, True)
    """
    closing_index = after_colon.find(quote_character, 1)
    if closing_index == -1:
        return None, True
    if _trailing_is_blank_or_comment(after_colon[closing_index + 1 :]):
        return after_colon[1:closing_index], False
    return None, True


def _scan_plain_value(after_colon: str) -> tuple[str | None, bool]:
    """Read a plain (unquoted) model value, dropping a trailing ``' #'`` comment.

    A block-scalar indicator (``|`` or ``>``) as the value is malformed; a YAML
    null (``null`` / ``~``, case-insensitive) is unset::

        opus          -> ("opus", False)
        null          -> (None, False)
        |             -> (None, True)
    """
    comment_match = re.search(INLINE_COMMENT_PATTERN, after_colon)
    value = after_colon[: comment_match.start()] if comment_match else after_colon
    value = value.rstrip(ASCII_WHITESPACE)
    if not value:
        return None, False
    if value[0] in BLOCK_SCALAR_INDICATOR_CHARACTERS:
        return None, True
    if value.lower() in ALL_NULL_MODEL_VALUES:
        return None, False
    return value, False


def _scan_model_line(model_line: str) -> tuple[str | None, bool]:
    """Read one top-level ``model:`` line into (scalar-or-None, is-malformed).

    The key and first colon are dropped, so a space before or after the colon
    reads the same. ASCII whitespace only is stripped, so a non-breaking space
    survives as a value character.
    """
    after_colon = model_line.split(":", 1)[1].strip(ASCII_WHITESPACE)
    if not after_colon:
        return None, False
    if after_colon[0] in MODEL_VALUE_QUOTE_CHARACTERS:
        return _scan_quoted_value(after_colon, after_colon[0])
    return _scan_plain_value(after_colon)


def pinned_or_malformed(frontmatter_block: str) -> tuple[str | None, bool]:
    """Return (pinned concrete model, is-malformed) for a frontmatter block.

    Scans the top-level ``model:`` lines by column-zero match, takes the last
    (YAML last-wins), and classifies it::

        no model line / model: / model: null / model: inherit -> (None, False)
        model: opus                                           -> ("opus", False)
        model: "x"y / model: | / model: 'unclosed             -> (None, True)
    """
    all_model_lines = re.findall(
        TOP_LEVEL_MODEL_LINE_PATTERN, frontmatter_block, re.MULTILINE
    )
    if not all_model_lines:
        return None, False
    scalar_value, is_malformed = _scan_model_line(all_model_lines[-1])
    if is_malformed:
        return None, True
    if scalar_value is None:
        return None, False
    if scalar_value.strip(ASCII_WHITESPACE).lower() == INHERIT_MODEL_VALUE:
        return None, False
    return scalar_value.strip(ASCII_WHITESPACE), False


def pinned_model_value(frontmatter_block: str) -> str | None:
    """Return the concrete model a block pins, or None when unset, inherit, or malformed."""
    return pinned_or_malformed(frontmatter_block)[0]


def frontmatter_pins_concrete_model(frontmatter_block: str) -> bool:
    """Return whether a frontmatter block pins a concrete model::

        ok:   model: inherit   -> False
        ok:   model:           -> False (bare, not a pin)
        flag: model: opus      -> True
    """
    return pinned_model_value(frontmatter_block) is not None


def is_agent_definition_path(file_path: str) -> bool:
    """Return whether a path is an agent-definition `.md` under an agents directory.

    Matches the package shape ``packages/claude-dev-env/agents/<name>.md`` and the
    installed shape ``~/.claude/agents/<name>.md``, across both slash directions
    and any letter case. The `agents/` directory contract is: agent definitions
    plus exactly the known per-directory doc files (``CLAUDE.md``, ``README.md``),
    which are documentation rather than definitions and are excluded by name — so
    a future non-agent `.md` landing there would need adding to that exclusion.
    """
    normalized_path = file_path.replace("\\", "/").lower()
    if not normalized_path.endswith(MARKDOWN_EXTENSION):
        return False
    file_name = normalized_path.rsplit("/", 1)[-1]
    if file_name in ALL_NON_AGENT_MARKDOWN_FILENAMES:
        return False
    return (
        PACKAGE_AGENTS_PATH_FRAGMENT in normalized_path
        or INSTALLED_AGENTS_PATH_FRAGMENT in normalized_path
    )
