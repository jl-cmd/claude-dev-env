"""Named constants imported by `pii_prevention_blocker` and `pii_scanner`."""

from __future__ import annotations

import re

from hooks_constants.hardcoded_user_path_constants import HARDCODED_USER_PATH_PATTERN

BASH_TOOL_NAME: str = "Bash"
WRITE_TOOL_NAME: str = "Write"
EDIT_TOOL_NAME: str = "Edit"
MULTI_EDIT_TOOL_NAME: str = "MultiEdit"

ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES: frozenset[str] = frozenset(
    {WRITE_TOOL_NAME, EDIT_TOOL_NAME, MULTI_EDIT_TOOL_NAME}
)

MCP_GITHUB_TOOL_PREFIX: str = "mcp__plugin_github_github__"

HOOK_SCRIPT_BASENAME: str = "pii_prevention_blocker.py"
SCANNER_MODULE_BASENAME: str = "pii_scanner.py"
CONSTANTS_MODULE_BASENAME: str = "pii_prevention_constants.py"

ALL_SELF_MODULE_BASENAMES: frozenset[str] = frozenset(
    {
        HOOK_SCRIPT_BASENAME,
        SCANNER_MODULE_BASENAME,
        CONSTANTS_MODULE_BASENAME,
    }
)

ALL_LICENSE_BASENAME_PREFIXES: tuple[str, ...] = ("LICENSE", "COPYING", "NOTICE")

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
        "me",
        "name",
        "alice",
        "bob",
        "carol",
        "dave",
        "runner",
        "container",
        "ubuntu",
        "admin",
        "default",
        "placeholder",
        "path",
        "someone",
    }
)

ALL_ALLOWLISTED_PRIVATE_IP_ADDRESSES: frozenset[str] = frozenset(
    {
        "192.168.1.100",
    }
)

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
    "for a full sweep. Add intentional LAN hosts to "
    "ALL_ALLOWLISTED_PRIVATE_IP_ADDRESSES in hooks_constants when tooling must "
    "keep a host such as a NAS."
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
