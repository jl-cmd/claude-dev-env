"""Constants for the agent-model-pin PreToolUse blocker.

Holds the frontmatter fence, the accepted non-pinning model value, the model-value
quote characters, the inline-comment pattern, the ASCII-whitespace set, the YAML
null model values, the block-scalar indicator characters, the markdown extension,
the doc filenames excluded from the gate, the gated tool names, the top-level
model-line pattern, the agent-file path fragments, the hook's dispatcher module
name, and the deny-message text. The blocker, its detection helpers, and its tests
import these by name.

``AGENT_MODEL_PIN_BLOCKER_MODULE_NAME`` lives here, with the hook's own constants,
for cohesion; the dispatcher roster imports it for this hook's native entry, so
each hook's module name sits beside that hook's constants.
"""

from __future__ import annotations

__all__ = [
    "FRONTMATTER_FENCE",
    "BYTE_ORDER_MARK",
    "INHERIT_MODEL_VALUE",
    "MODEL_VALUE_QUOTE_CHARACTERS",
    "INLINE_COMMENT_PATTERN",
    "ASCII_WHITESPACE",
    "ALL_NULL_MODEL_VALUES",
    "BLOCK_SCALAR_INDICATOR_CHARACTERS",
    "MARKDOWN_EXTENSION",
    "ALL_NON_AGENT_MARKDOWN_FILENAMES",
    "ALL_PIN_GATED_TOOL_NAMES",
    "TOP_LEVEL_MODEL_LINE_PATTERN",
    "PACKAGE_AGENTS_PATH_FRAGMENT",
    "INSTALLED_AGENTS_PATH_FRAGMENT",
    "AGENT_MODEL_PIN_BLOCKER_MODULE_NAME",
    "CALLING_HOOK_NAME",
    "DENY_SYSTEM_MESSAGE",
    "DENY_ADDITIONAL_CONTEXT",
]

FRONTMATTER_FENCE = "---"
BYTE_ORDER_MARK = "\ufeff"
INHERIT_MODEL_VALUE = "inherit"
MODEL_VALUE_QUOTE_CHARACTERS = "'\""
INLINE_COMMENT_PATTERN = r"\s#"
ASCII_WHITESPACE = " \t\n\r\x0b\x0c"
ALL_NULL_MODEL_VALUES = ("null", "~")
BLOCK_SCALAR_INDICATOR_CHARACTERS = "|>"
MARKDOWN_EXTENSION = ".md"

ALL_NON_AGENT_MARKDOWN_FILENAMES = ("claude.md", "readme.md")
ALL_PIN_GATED_TOOL_NAMES = ("Write", "Edit", "MultiEdit")
TOP_LEVEL_MODEL_LINE_PATTERN = r"^model[ \t]*:.*$"

PACKAGE_AGENTS_PATH_FRAGMENT = "claude-dev-env/agents/"
INSTALLED_AGENTS_PATH_FRAGMENT = ".claude/agents/"

AGENT_MODEL_PIN_BLOCKER_MODULE_NAME = "agent_model_pin_blocker"

CALLING_HOOK_NAME = "agent_model_pin_blocker.py"

DENY_SYSTEM_MESSAGE = (
    "Agent definition model line rejected - omit the model key or set model: inherit"
)

DENY_ADDITIONAL_CONTEXT = (
    "An agent definition either omits the model key or sets model: inherit, so "
    "the caller picks the model on each spawn.\n"
    "  BAD:  model: opus  ->  GOOD: model: inherit\n"
    "  BAD:  model: sonnet  ->  GOOD: <no model line>\n"
    "See agents/CLAUDE.md for the accepted frontmatter keys."
)
