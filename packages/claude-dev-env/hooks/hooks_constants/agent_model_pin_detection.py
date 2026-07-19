"""Shared detection for the agent-model-pin blocker.

Both the blocker and the agent-frontmatter test suite import these helpers, so
the pin question is read one way on both surfaces. The frontmatter block is
isolated by line-anchored fences (a fence is a line that is exactly ``---``,
reached past any byte-order mark and leading blank lines). The model value is
read from the last top-level ``model:`` line by a deterministic scan that follows
the YAML scalar rules for that one line, so the detector carries no YAML runtime
dependency — the dispatcher that hosts this hook loads on a stdlib-only Python.
``test_agent_model_pin_detection`` pins the scan to ``yaml.safe_load`` as an
oracle over the well-formed matrix.
"""

from __future__ import annotations

import re

from hooks_constants.agent_model_pin_blocker_constants import (
    ALL_NON_AGENT_MARKDOWN_FILENAMES,
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


def _model_value_from_line(model_line: str) -> str | None:
    """Return the scalar value a single top-level ``model:`` line declares.

    Follows the YAML scalar rules for one line: a quoted value keeps its inner
    text and ignores a trailing comment, an unterminated quote keeps the rest of
    the line, a plain value ends at an ``' #'`` inline comment, and a bare
    ``model:`` yields None. The key and the first colon are dropped first, so a
    space before or after the colon reads the same::

        model: opus       -> opus
        model : opus      -> opus
        model:opus        -> opus
        model: "a # b"    -> a # b
        model: 'opus      -> opus
        model:            -> None
    """
    after_colon = model_line.split(":", 1)[1].strip()
    if not after_colon:
        return None
    opening_quote = after_colon[0]
    if opening_quote in MODEL_VALUE_QUOTE_CHARACTERS:
        closing_index = after_colon.find(opening_quote, 1)
        if closing_index != -1:
            return after_colon[1:closing_index]
        return after_colon[1:]
    comment_match = re.search(INLINE_COMMENT_PATTERN, after_colon)
    if comment_match:
        return after_colon[: comment_match.start()].rstrip()
    return after_colon


def pinned_model_value(frontmatter_block: str) -> str | None:
    """Return the concrete model a frontmatter block pins, or None.

    Scans the top-level ``model:`` lines by column-zero match (so colon-laden
    description prose never reads as one), takes the last (YAML last-wins), and
    returns its value when that value is a concrete model — anything other than
    an empty value or ``inherit`` (case-insensitive). Returns the value as read,
    so a caller can name it in a message.
    """
    all_model_lines = re.findall(
        TOP_LEVEL_MODEL_LINE_PATTERN, frontmatter_block, re.MULTILINE
    )
    if not all_model_lines:
        return None
    declared_value = _model_value_from_line(all_model_lines[-1])
    if declared_value is None or declared_value.strip().lower() == INHERIT_MODEL_VALUE:
        return None
    return declared_value.strip()


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
