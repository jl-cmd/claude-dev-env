"""Constants for the agent-model-pin PreToolUse blocker.

Holds the frontmatter fence, the accepted non-pinning model value, the gated tool
names, the top-level model-line pattern, the agent-file path fragments the blocker
gates, and the deny-message text. The blocker and its tests import these by name.
"""

from __future__ import annotations

__all__ = [
    "FRONTMATTER_FENCE",
    "FRONTMATTER_SEGMENT_COUNT",
    "MODEL_FRONTMATTER_KEY",
    "INHERIT_MODEL_VALUE",
    "MARKDOWN_EXTENSION",
    "ALL_PIN_GATED_TOOL_NAMES",
    "TOP_LEVEL_MODEL_LINE_PATTERN",
    "EDIT_TEXT_JOIN_SEPARATOR",
    "PACKAGE_AGENTS_PATH_FRAGMENT",
    "INSTALLED_AGENTS_PATH_FRAGMENT",
    "CALLING_HOOK_NAME",
    "DENY_SYSTEM_MESSAGE",
    "DENY_ADDITIONAL_CONTEXT",
]

FRONTMATTER_FENCE = "---"
FRONTMATTER_SEGMENT_COUNT = 3
MODEL_FRONTMATTER_KEY = "model"
INHERIT_MODEL_VALUE = "inherit"
MARKDOWN_EXTENSION = ".md"

ALL_PIN_GATED_TOOL_NAMES = ("Write", "Edit", "MultiEdit")
TOP_LEVEL_MODEL_LINE_PATTERN = r"^model:.*$"
EDIT_TEXT_JOIN_SEPARATOR = "\n"

PACKAGE_AGENTS_PATH_FRAGMENT = "claude-dev-env/agents/"
INSTALLED_AGENTS_PATH_FRAGMENT = ".claude/agents/"

CALLING_HOOK_NAME = "agent_model_pin_blocker.py"

DENY_SYSTEM_MESSAGE = (
    "Agent definition pins a concrete model - the caller supplies the model per spawn"
)

DENY_ADDITIONAL_CONTEXT = (
    "An agent definition either omits the model key or sets model: inherit, so "
    "the caller picks the model on each spawn.\n"
    "  BAD:  model: opus  ->  GOOD: model: inherit\n"
    "  BAD:  model: sonnet  ->  GOOD: <no model line>\n"
    "See agents/CLAUDE.md for the accepted frontmatter keys."
)
