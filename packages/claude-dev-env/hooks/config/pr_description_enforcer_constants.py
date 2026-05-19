"""Configuration constants for the pr_description_enforcer PreToolUse hook."""

import os
import re


_PLUGIN_ROOT: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PR_GUIDE_PATH: str = os.path.join(_PLUGIN_ROOT, "docs", "PR_DESCRIPTION_GUIDE.md")

MINIMUM_SUBSTANTIVE_PROSE_CHARS: int = 40

FENCED_CODE_BLOCK_PATTERN: re.Pattern[str] = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_PATTERN: re.Pattern[str] = re.compile(r"`[^`]*`")
HEADING_LINE_PATTERN: re.Pattern[str] = re.compile(r"^#+[ \t].*$", re.MULTILINE)
BOLD_PAIR_PATTERN: re.Pattern[str] = re.compile(r"\*\*([^*]+?)\*\*")
BULLET_MARKER_PATTERN: re.Pattern[str] = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
BLOCKQUOTE_MARKER_PATTERN: re.Pattern[str] = re.compile(r"^\s*>\s+", re.MULTILINE)
LINK_TEXT_PATTERN: re.Pattern[str] = re.compile(r"\[([^\]]+)\]\([^)]+\)")
WHITESPACE_RUN_PATTERN: re.Pattern[str] = re.compile(r"\s+")
