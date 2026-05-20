"""Configuration constants for the gh-pr-author swap hook trio.

The PreToolUse enforcer (``gh_pr_author_enforcer.py``) auto-switches the
active ``gh`` CLI account to ``GITHUB_DEFAULT_ACCOUNT`` before a
``gh pr create`` invocation, the PostToolUse companion
(``gh_pr_author_restore.py``) restores the prior account afterwards, and
the SessionStart cleanup hook (``gh_pr_author_session_cleanup.py``)
sweeps any stale state files left behind when a prior session was
interrupted between the swap and the restore. The state file written
between the hooks is keyed per session so parallel Claude Code sessions
cannot stomp on each other's swap state.
"""

from __future__ import annotations

import re

REQUIRED_ACCOUNT_ENV_VAR: str = "GITHUB_DEFAULT_ACCOUNT"

BASH_TOOL_NAME: str = "Bash"

GH_PR_CREATE_PATTERN: re.Pattern[str] = re.compile(
    r"(?:^|[;&|\n`({]|\$\()[ \t]*"
    r"(?:(?:if|then|else|elif|while|until|do|!)[ \t]+)*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*=\S+[ \t]+)*"
    r"gh(?:[ \t]+(?:--[A-Za-z][\w-]*(?:=\S+)?|-[A-Za-z])(?:[ \t]+(?!-)\S+)?)*"
    r"[ \t]+pr[ \t]+create\b",
    re.IGNORECASE,
)
WEB_FLAG_PATTERN: re.Pattern[str] = re.compile(r"(?<!\S)(?:--web|-w)(?!\S)")
COMMAND_SEPARATOR_PATTERN: re.Pattern[str] = re.compile(
    r"(?:&&|\|\||;|(?<!\|)\|(?!\|)|(?<!&)&(?!&)|[\r\n])"
)
BASH_COMMENT_INTRODUCER_CHARACTER: str = "#"
COMMAND_SUBSTITUTION_OPENER_LENGTH: int = 2

ALL_GH_API_USER_COMMAND: tuple[str, ...] = ("gh", "api", "user", "--jq", ".login")
GH_API_USER_TIMEOUT_SECONDS: int = 5

ALL_GH_AUTH_SWITCH_COMMAND_HEAD: tuple[str, ...] = ("gh", "auth", "switch", "--user")
GH_AUTH_SWITCH_TIMEOUT_SECONDS: int = 10

STATE_FILE_PREFIX: str = "gh_pr_author_swap_"
STATE_FILE_SUFFIX: str = ".json"
STATE_FILE_DEFAULT_SESSION_ID: str = "default"

SESSION_ID_UNSAFE_CHARACTERS_PATTERN: re.Pattern[str] = re.compile(r"[^A-Za-z0-9_-]")

STATE_FILE_ORIGINAL_ACCOUNT_KEY: str = "original_account"
STATE_FILE_PRIMARY_ACCOUNT_KEY: str = "primary_account"

STATE_FILE_PERMISSION_MODE: int = 0o600

STATE_FILE_PAYLOAD_TEXT_ENCODING_NAME: str = "utf-8"

OS_O_NOFOLLOW_ATTRIBUTE_NAME: str = "O_NOFOLLOW"

STATE_FILE_STALE_AGE_SECONDS: int = 1800

ALL_SHELL_QUOTE_CHARACTERS: tuple[str, ...] = ("\"", "'")
SHELL_QUOTE_REPLACEMENT_CHARACTER: str = " "
SHELL_BACKSLASH_ESCAPE_PAIR_LENGTH: int = 2
SHELL_BACKTICK_CHARACTER: str = "`"
SHELL_DOLLAR_CHARACTER: str = "$"
SHELL_PAREN_OPEN_CHARACTER: str = "("
SHELL_PAREN_CLOSE_CHARACTER: str = ")"
SHELL_LESS_THAN_CHARACTER: str = "<"
SHELL_BACKSLASH_CHARACTER: str = "\\"
SHELL_NEWLINE_CHARACTER: str = "\n"

HEREDOC_OPENER_TAG_PATTERN: re.Pattern[str] = re.compile(
    r"[ \t]*(?P<dash>-?)[ \t]*(?:'(?P<sq_tag>[A-Za-z_][A-Za-z0-9_]*)'"
    r"|\"(?P<dq_tag>[A-Za-z_][A-Za-z0-9_]*)\""
    r"|(?P<bare_tag>[A-Za-z_][A-Za-z0-9_]*))"
)
HEREDOC_OPENER_TOKEN_LENGTH: int = 2
