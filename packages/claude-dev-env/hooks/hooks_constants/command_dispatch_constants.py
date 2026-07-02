"""Constants for the unanchored command-dispatch meta-gate."""

import re

COMMAND_DISPATCH_PATH_MARKER: str = "hooks/blocking"

COMMAND_DISPATCH_LITERAL_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:gh|git|npm|npx|node|python3?|pwsh|powershell|docker|kubectl|pip|cargo"
    r"|yarn|pnpm)\\s[+*]"
)

COMMAND_KEY_ACCESS_PATTERN: re.Pattern[str] = re.compile(
    r"""(?:\[\s*|\.get\(\s*)["']command["']"""
)

FIRST_TOKEN_TOKENIZATION_PATTERN: re.Pattern[str] = re.compile(
    r"shlex\.split|\.split\("
)

ALL_REGEX_START_ANCHOR_TOKENS: tuple[str, ...] = ("^", "\\A")

COMMAND_DISPATCH_MESSAGE_SUFFIX: str = (
    "matches a multi-word command as a substring - anchor the pattern to the "
    "start of the command (^) or tokenize the first word (shlex.split) so a "
    "command like 'echo gh pr create' is not matched"
)

MAX_COMMAND_DISPATCH_ISSUES: int = 20
