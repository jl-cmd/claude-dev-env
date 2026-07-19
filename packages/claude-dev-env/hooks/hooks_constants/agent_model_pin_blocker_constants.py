"""Constants for the agent-model-pin PreToolUse blocker.

Holds the frontmatter fence, the accepted non-pinning model value, the model-value
quote characters, the markdown extension, the doc filenames excluded from the gate,
the gated tool names, the top-level model-line pattern, the agent-file path
fragments, the hook's dispatcher module name, and the deny-message text. The
blocker, its detection helpers, and its tests import these by name.
"""

from __future__ import annotations

__all__ = [
    "FRONTMATTER_FENCE",
    "MODEL_FRONTMATTER_KEY",
    "INHERIT_MODEL_VALUE",
    "MODEL_VALUE_QUOTE_CHARACTERS",
    "MARKDOWN_EXTENSION",
    "ALL_NON_AGENT_MARKDOWN_FILENAMES",
    "ALL_PIN_GATED_TOOL_NAMES",
    "TOP_LEVEL_MODEL_LINE_PATTERN",
    "PACKAGE_AGENTS_PATH_FRAGMENT",
    "INSTALLED_AGENTS_PATH_FRAGMENT",
    "CALLING_HOOK_NAME",
    "DENY_SYSTEM_MESSAGE",
    "DENY_ADDITIONAL_CONTEXT",
]

FRONTMATTER_FENCE = "---"
MODEL_FRONTMATTER_KEY = "model"
INHERIT_MODEL_VALUE = "inherit"
MODEL_VALUE_QUOTE_CHARACTERS = "'\""
MARKDOWN_EXTENSION = ".md"

ALL_NON_AGENT_MARKDOWN_FILENAMES = ("claude.md", "readme.md")
ALL_PIN_GATED_TOOL_NAMES = ("Write", "Edit", "MultiEdit")
TOP_LEVEL_MODEL_LINE_PATTERN = r"^model:.*$"

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
