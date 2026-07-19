"""Shared detection for the agent-model-pin blocker.

Both the blocker and the agent-frontmatter test suite import these helpers, so
the pin question is read one way on both surfaces. The frontmatter block is
isolated by line-anchored fences (a fence is a line that is exactly ``---``), the
model value is read from the last top-level ``model:`` line with ``yaml.safe_load``,
and a model line ``yaml.safe_load`` cannot parse falls back to a raw-text read of
that same line.
"""

from __future__ import annotations

import re

import yaml

from hooks_constants.agent_model_pin_blocker_constants import (
    ALL_NON_AGENT_MARKDOWN_FILENAMES,
    FRONTMATTER_FENCE,
    INHERIT_MODEL_VALUE,
    INSTALLED_AGENTS_PATH_FRAGMENT,
    MARKDOWN_EXTENSION,
    MODEL_FRONTMATTER_KEY,
    MODEL_VALUE_QUOTE_CHARACTERS,
    PACKAGE_AGENTS_PATH_FRAGMENT,
    TOP_LEVEL_MODEL_LINE_PATTERN,
)

__all__ = [
    "extract_frontmatter_block",
    "frontmatter_pins_concrete_model",
    "raw_last_model_line_pins",
    "is_agent_definition_path",
]


def extract_frontmatter_block(file_content: str) -> str | None:
    """Return the frontmatter block a file opens with, or None when it has none.

    A fence is a line that is exactly ``---`` (trailing whitespace allowed), so a
    ``---`` inside a description line neither opens nor closes the block. The file
    opens with a fence line; the block is the text between it and the next fence.
    """
    all_lines = file_content.splitlines()
    if not all_lines or all_lines[0].rstrip() != FRONTMATTER_FENCE:
        return None
    for each_index in range(1, len(all_lines)):
        if all_lines[each_index].rstrip() == FRONTMATTER_FENCE:
            return "\n".join(all_lines[1:each_index])
    return None


def _all_model_lines(frontmatter_block: str) -> list[str]:
    """Return the column-zero ``model:`` lines in a frontmatter block, in order."""
    return re.findall(TOP_LEVEL_MODEL_LINE_PATTERN, frontmatter_block, re.MULTILINE)


def frontmatter_pins_concrete_model(frontmatter_block: str) -> bool:
    """Return whether a frontmatter block pins a concrete model.

    Isolates the top-level ``model:`` lines by a column-zero line scan, so a
    ``description`` carrying colon-laden example prose never confuses the read,
    then parses the last line (last-wins) with ``yaml.safe_load`` for the value::

        ok:   model: inherit   -> False
        ok:   model:           -> False (None, not a pin)
        flag: model: opus      -> True

    The comparison against ``inherit`` strips whitespace and ignores case. A model
    line ``yaml.safe_load`` cannot parse (an unterminated quote) raises
    ``yaml.YAMLError``; ``raw_last_model_line_pins`` is the recovery read.
    """
    all_model_lines = _all_model_lines(frontmatter_block)
    if not all_model_lines:
        return False
    parsed_model_line = yaml.safe_load(all_model_lines[-1])
    declared_model = (
        parsed_model_line.get(MODEL_FRONTMATTER_KEY)
        if isinstance(parsed_model_line, dict)
        else None
    )
    if declared_model is None:
        return False
    return str(declared_model).strip().lower() != INHERIT_MODEL_VALUE


def raw_last_model_line_pins(frontmatter_block: str) -> bool:
    """Return whether the last ``model:`` line pins a concrete model, read as raw text.

    The recovery read for a model line ``yaml.safe_load`` cannot parse: take the
    text after the colon on the last top-level ``model:`` line, strip whitespace
    and surrounding quotes, and treat any value other than inherit (or empty) as a
    pin::

        model: 'opus     -> opus    -> pin
        model: 'inherit  -> inherit -> not a pin
    """
    all_model_lines = _all_model_lines(frontmatter_block)
    if not all_model_lines:
        return False
    raw_value = all_model_lines[-1].split(":", 1)[1]
    stripped_value = raw_value.strip().strip(MODEL_VALUE_QUOTE_CHARACTERS).strip().lower()
    if not stripped_value:
        return False
    return stripped_value != INHERIT_MODEL_VALUE


def is_agent_definition_path(file_path: str) -> bool:
    """Return whether a path is an agent-definition `.md` under an agents directory.

    Matches the package shape ``packages/claude-dev-env/agents/<name>.md`` and the
    installed shape ``~/.claude/agents/<name>.md``, across both slash directions
    and any letter case. A per-directory doc file (``CLAUDE.md``, ``README.md``)
    is documentation rather than an agent definition, so it is excluded.
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
