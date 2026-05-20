"""Configuration constants for the es_exe_path_rewriter PreToolUse hook."""

import re

BASH_TOOL_NAME = "Bash"

HOOK_EVENT_NAME = "PreToolUse"

PERMISSION_ALLOW = "allow"

PLACEHOLDER_TOKEN_PATTERN = re.compile(
    r"""(?:(?<=\s)|^)['"]?(?<!\$)\{([^}]+)\}['"]?(?=\s|$)""",
)
