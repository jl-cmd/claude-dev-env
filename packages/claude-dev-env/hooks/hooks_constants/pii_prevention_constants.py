"""Named constants imported by `pii_prevention_blocker` and `pii_scanner`."""

from __future__ import annotations

import re

from hooks_constants.hardcoded_user_path_constants import HARDCODED_USER_PATH_PATTERN

BASH_TOOL_NAME: str = "Bash"
POWERSHELL_TOOL_NAME: str = "PowerShell"
WRITE_TOOL_NAME: str = "Write"
EDIT_TOOL_NAME: str = "Edit"
MULTI_EDIT_TOOL_NAME: str = "MultiEdit"

ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES: frozenset[str] = frozenset(
    {WRITE_TOOL_NAME, EDIT_TOOL_NAME, MULTI_EDIT_TOOL_NAME}
)

ALL_SHELL_TOOL_NAMES: frozenset[str] = frozenset(
    {BASH_TOOL_NAME, POWERSHELL_TOOL_NAME}
)

ALL_GIT_BINARY_BASENAMES: frozenset[str] = frozenset({"git", "git.exe"})
GIT_COMMIT_SUBCOMMAND: str = "commit"
GIT_WORKING_DIRECTORY_OPTION: str = "-C"
ALL_VALUE_TAKING_GIT_OPTIONS: frozenset[str] = frozenset(
    {GIT_WORKING_DIRECTORY_OPTION, "-c", "--git-dir", "--work-tree", "--namespace"}
)
GIT_OPTION_WITH_VALUE_STEP: int = 2
ALL_SHELL_COMMAND_SEPARATOR_TOKENS: frozenset[str] = frozenset(
    {"&&", "||", ";", "|", "&"}
)
ALL_SHELL_KEYWORD_TOKENS: frozenset[str] = frozenset(
    {"then", "do", "else", "elif"}
)
ALL_COMMAND_WRAPPER_TOKENS: frozenset[str] = frozenset(
    {
        "sudo",
        "doas",
        "env",
        "time",
        "timeout",
        "nice",
        "ionice",
        "chrt",
        "xargs",
        "command",
        "stdbuf",
        "nohup",
        "setsid",
        "flock",
    }
)
ALL_LEADING_SKIPPABLE_COMMAND_TOKENS: frozenset[str] = (
    ALL_SHELL_KEYWORD_TOKENS | ALL_COMMAND_WRAPPER_TOKENS
)
ALL_ONE_OPERAND_WRAPPER_TOKENS: frozenset[str] = frozenset({"timeout", "flock"})
ALL_BASH_FAMILY_INTERPRETER_BASENAMES: frozenset[str] = frozenset(
    {
        "bash",
        "sh",
        "bash.exe",
        "sh.exe",
    }
)
ALL_POWERSHELL_INTERPRETER_BASENAMES: frozenset[str] = frozenset(
    {
        "pwsh",
        "pwsh.exe",
        "powershell",
        "powershell.exe",
    }
)
ALL_SHELL_INTERPRETER_BASENAMES: frozenset[str] = (
    ALL_BASH_FAMILY_INTERPRETER_BASENAMES | ALL_POWERSHELL_INTERPRETER_BASENAMES
)
SUBSHELL_GROUP_OPEN_TOKEN: str = "("
SHELL_INLINE_COMMAND_FLAG: str = "-c"
POWERSHELL_INLINE_COMMAND_FLAG: str = "-command"
INLINE_COMMAND_FLAG_CLUSTER_CHARACTER: str = "c"
INLINE_COMMAND_TOKEN_JOINER: str = " "
SINGLE_DASH_OPTION_PREFIX: str = "-"
DOUBLE_DASH_OPTION_PREFIX: str = "--"
ALL_SHELL_QUOTE_CHARACTERS: frozenset[str] = frozenset({'"', "'"})
ALL_COMMAND_BOUNDARY_NEWLINE_CHARACTERS: frozenset[str] = frozenset({"\n", "\r"})
ENVIRONMENT_ASSIGNMENT_PATTERN: re.Pattern[str] = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*="
)
LINE_CONTINUATION_PATTERN: re.Pattern[str] = re.compile(r"\\\r?\n")
POWERSHELL_LINE_CONTINUATION_PATTERN: re.Pattern[str] = re.compile(r"`\r?\n")

MCP_GITHUB_TOOL_PREFIX: str = "mcp__plugin_github_github__"

HOOK_SCRIPT_BASENAME: str = "pii_prevention_blocker.py"

ALL_EXACT_LEGAL_NOTICE_BASENAMES: frozenset[str] = frozenset(
    {
        "license",
        "license.md",
        "license.txt",
        "copying",
        "copying.md",
        "copying.txt",
        "notice",
        "notice.md",
        "notice.txt",
    }
)

ALL_SELF_MODULE_PATH_SUFFIXES: tuple[str, ...] = (
    "/hooks/blocking/pii_prevention_blocker.py",
    "/hooks/blocking/pii_scanner.py",
    "/hooks/hooks_constants/pii_prevention_constants.py",
)

PYTHON_SOURCE_FILE_SUFFIX: str = ".py"
CONFTEST_BASENAME: str = "conftest.py"
TEST_MODULE_BASENAME_PREFIX: str = "test_"
TEST_MODULE_BASENAME_SUFFIX: str = "_test.py"
TESTS_PATH_SEGMENT: str = "/tests/"
TESTS_PATH_PREFIX: str = "tests/"
SPEC_BASENAME_MARKER: str = ".spec."
TEST_BASENAME_MARKER: str = ".test."
ALL_SOURCE_TEST_FILE_SUFFIXES: tuple[str, ...] = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
)
ALL_SAFE_EMAIL_DOMAINS: frozenset[str] = frozenset(
    {
        "anthropic.com",
        "example.com",
        "example.org",
        "example.net",
        "example.edu",
        "localhost",
        "invalid",
        "test",
        "local",
        "test.local",
    }
)

ALL_PLACEHOLDER_HOME_USERNAMES: frozenset[str] = frozenset(
    {
        "example",
        "user",
        "username",
        "your-user",
        "your_user",
        "you",
        "name",
        "alice",
        "bob",
        "carol",
        "dave",
        "placeholder",
        "path",
        "me",
        "someone",
        "default",
        "admin",
        "runner",
        "container",
        "ubuntu",
    }
)

ALL_ALLOWLISTED_PRIVATE_IP_ADDRESSES: frozenset[str] = frozenset()

MAXIMUM_FINDINGS_PER_SCAN: int = 12
MAXIMUM_STAGED_FILE_BYTES: int = 1_000_000
MAXIMUM_OFFENDING_PREVIEW_LENGTH: int = 80
GIT_COMMAND_TIMEOUT_SECONDS: int = 10

ALL_STAGED_FILES_COMMAND: tuple[str, ...] = (
    "git",
    "diff",
    "--cached",
    "--name-only",
    "--diff-filter=ACMR",
)

ALL_STAGED_BLOB_SHOW_COMMAND_PREFIX: tuple[str, ...] = ("git", "show")
STAGED_BLOB_PREFIX: str = ":"

ALL_GIT_ORIGIN_URL_COMMAND: tuple[str, ...] = (
    "git",
    "config",
    "--get",
    "remote.origin.url",
)
GIT_URL_SUFFIX: str = ".git"
GITHUB_COM_HOST: str = "github.com"
ALL_NETWORK_GIT_URL_SCHEMES: frozenset[str] = frozenset({"http", "https", "ssh"})
SCP_STYLE_PATH_SEPARATOR: str = ":"
USERINFO_HOST_SEPARATOR: str = "@"
URL_SCHEME_SEPARATOR: str = "://"
WINDOWS_PATH_SEPARATOR: str = "\\"
POSIX_PATH_SEPARATOR: str = "/"
MINIMUM_OWNER_REPO_SEGMENT_COUNT: int = 2

BODY_FILE_ENCODING: str = "utf-8"
NULL_BYTE_MARKER: bytes = b"\x00"
MESSAGE_LINE_SEPARATOR: str = "\n"
MINIMUM_ENV_STYLE_USERNAME_LENGTH: int = 3
IPV4_VERSION_NUMBER: int = 4

ALL_RFC1918_NETWORK_CIDRS: tuple[str, ...] = (
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
)

CATEGORY_EMAIL: str = "email"
CATEGORY_HOME_PATH: str = "home-path"
CATEGORY_PRIVATE_IP: str = "private-ip"
CATEGORY_SECRET: str = "secret"

ALL_REDACTED_PREVIEW_CATEGORIES: frozenset[str] = frozenset(
    {CATEGORY_EMAIL, CATEGORY_SECRET}
)
REDACTED_PREVIEW_PREFIX_LENGTH: int = 4
REDACTED_PREVIEW_SUFFIX_LENGTH: int = 4
REDACTED_PREVIEW_REVEALED_LENGTH: int = (
    REDACTED_PREVIEW_PREFIX_LENGTH + REDACTED_PREVIEW_SUFFIX_LENGTH
)
REDACTED_PREVIEW_MINIMUM_HIDDEN_LENGTH: int = REDACTED_PREVIEW_REVEALED_LENGTH
REDACTED_PREVIEW_ELLIPSIS: str = "…"
REDACTED_SHORT_PREVIEW: str = "[redacted]"
MINIMUM_LENGTH_FOR_PARTIAL_REDACTION: int = (
    REDACTED_PREVIEW_REVEALED_LENGTH + REDACTED_PREVIEW_MINIMUM_HIDDEN_LENGTH
)

EMAIL_PATTERN: re.Pattern[str] = re.compile(
    r"(?i)\b([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})\b"
)

IPV4_PATTERN: re.Pattern[str] = re.compile(
    r"\b((?:25[0-5]|2[0-4]\d|1?\d?\d)\."
    r"(?:25[0-5]|2[0-4]\d|1?\d?\d)\."
    r"(?:25[0-5]|2[0-4]\d|1?\d?\d)\."
    r"(?:25[0-5]|2[0-4]\d|1?\d?\d))\b"
)

GITHUB_TOKEN_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b"
)

GITHUB_FINE_GRAINED_TOKEN_PATTERN: re.Pattern[str] = re.compile(
    r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"
)

AWS_ACCESS_KEY_PATTERN: re.Pattern[str] = re.compile(r"\bAKIA[0-9A-Z]{16}\b")

PEM_PRIVATE_KEY_HEADER_PATTERN: re.Pattern[str] = re.compile(
    r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |ENCRYPTED )?PRIVATE KEY-----"
)

HOME_PATH_PATTERN: re.Pattern[str] = HARDCODED_USER_PATH_PATTERN

ALL_HOME_DIRECTORY_PATH_MARKERS: tuple[str, ...] = ("/users/", "/home/")

ALL_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    GITHUB_TOKEN_PATTERN,
    GITHUB_FINE_GRAINED_TOKEN_PATTERN,
    AWS_ACCESS_KEY_PATTERN,
    PEM_PRIVATE_KEY_HEADER_PATTERN,
)

ANGLE_BRACKET_PLACEHOLDER_PATTERN: re.Pattern[str] = re.compile(r"^<[^>]+>$")

CORRECTIVE_MESSAGE_HEADER: str = (
    "BLOCKED [pii_prevention_blocker]: high-confidence personal data or secret "
    "material must not land in the repository or on a durable GitHub post."
)

CORRECTIVE_MESSAGE_FOOTER: str = (
    "Remediate: replace with placeholders (user@example.com, C:/Users/example/), "
    "move secrets to an env or secret store, and run the privacy-hygiene skill "
    "for a full sweep. Your own NAS host is allowlisted at scan time from "
    "CLAUDE_NAS_HOST or ~/.claude/local-identity.json, so set it there rather "
    "than committing the address."
)

FINDING_LINE_TEMPLATE: str = "  [{category}] {preview}"

STAGED_LIST_FAILURE_REASON: str = (
    "BLOCKED [pii_prevention_blocker]: could not list staged files for PII scan "
    "(git diff --cached failed). Refuse commit until the index is readable."
)

STAGED_BLOB_UNSCANNABLE_REASON_TEMPLATE: str = (
    "BLOCKED [pii_prevention_blocker]: staged file '{relative_path}' could not be "
    "scanned for PII ({reason}). Refuse commit, shrink the blob, or keep binary "
    "assets free of embedded secrets."
)

STAGED_BLOB_REASON_GIT_SHOW_FAILED: str = "git show of staged blob failed"
STAGED_BLOB_REASON_OVERSIZED: str = "blob exceeds MAXIMUM_STAGED_FILE_BYTES"
STAGED_BLOB_REASON_NULL_BYTES: str = "blob contains null bytes (binary/unscannable)"
STAGED_BLOB_REASON_DECODE_FAILED: str = "blob is not valid UTF-8 text"
