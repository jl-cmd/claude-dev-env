"""Configuration for the pr-converge skill Markdown reflow script."""

import re
from pathlib import Path

MAXIMUM_LINE_WIDTH: int = 80
BASH_CONTINUATION_MARKER_WIDTH: int = 2
TARGET_SKILL_PATH: Path = Path(__file__).resolve().parent.parent.parent / "SKILL.md"

ORDERED_LIST_ITEM_PATTERN: re.Pattern[str] = re.compile(r"^(\s*)(\d+\.\s)(.*)$")
BULLET_LIST_ITEM_PATTERN: re.Pattern[str] = re.compile(r"^(\s*)([-*]\s)(.*)$")
UNFINISHED_MARKDOWN_LINK_TARGET_PATTERN: re.Pattern[str] = re.compile(r"\]\([^)]*$")
MARKDOWN_REFERENCE_DEFINITION_PATTERN: re.Pattern[str] = re.compile(r"^\s*\[[^\]]+\]:\s*\S")
