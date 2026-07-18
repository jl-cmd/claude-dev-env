"""Named constants for the claude fallback-chain runner, and the helper that
picks which text-codec kwargs a chain subprocess wrapper forwards.

Per the project's configuration conventions, every scalar and structural
constant the runner needs lives here rather than inline in the module.
"""

from __future__ import annotations

from collections.abc import Mapping

UTF8_ENCODING: str = "utf-8"
"""Encoding used to read the chain configuration file."""

CODEC_ERROR_STRATEGY: str = "replace"
"""Codec error handler that maps any unencodable or undecodable value to a marker."""

SUBPROCESS_ENCODING_KEYWORD: str = "encoding"
"""Keyword name for text encoding when forwarding chain subprocess runner kwargs."""

SUBPROCESS_ERRORS_KEYWORD: str = "errors"
"""Keyword name for text decode error policy when forwarding chain subprocess runner kwargs."""

ALL_SUBPROCESS_TEXT_CODEC_KEYWORDS: tuple[str, ...] = (
    SUBPROCESS_ENCODING_KEYWORD,
    SUBPROCESS_ERRORS_KEYWORD,
)
"""Keyword names to forward from the chain runner for text-mode subprocess capture."""


def collect_forwarded_text_codec(
    all_keywords: Mapping[str, object],
) -> dict[str, object]:
    """Return only the text-codec kwargs present in ``all_keywords``.

    ::

        collect_forwarded_text_codec({"encoding": "utf-8", "timeout": 30})
        # -> {"encoding": "utf-8"}

        collect_forwarded_text_codec({"timeout": 30})
        # -> {}

    Args:
        all_keywords: Keyword arguments received by a chain subprocess wrapper.

    Returns:
        Mapping of codec keyword names to their values, limited to keys listed
        in ``ALL_SUBPROCESS_TEXT_CODEC_KEYWORDS`` that are present in the input.
    """
    return {
        each_key: all_keywords[each_key]
        for each_key in ALL_SUBPROCESS_TEXT_CODEC_KEYWORDS
        if each_key in all_keywords
    }


CLAUDE_HOME_SUBDIRECTORY: str = ".claude"
"""Per-user directory under the home directory that holds the chain config."""

CONFIG_FILENAME: str = "claude-chain.json"
"""Real chain-configuration filename read from the user's home directory."""

CHAIN_USAGE_MODULE_NAME: str = "claude_chain_usage"
"""Import name of the weekly-usage report module loaded lazily by the runner."""

EXAMPLE_CONFIG_FILENAME: str = "claude-chain.example.json"
"""Committed template filename referenced in the config-error guidance."""

CONFIG_CHAIN_KEY: str = "chain"
"""Top-level key whose value is the ordered list of chain entries."""

CONFIG_COMMAND_KEY: str = "command"
"""Chain-entry key naming the binary to spawn."""

CONFIG_EXTRA_ARGS_KEY: str = "extra_args"
"""Chain-entry key holding per-account arguments appended to each invocation."""

CONFIG_CREDENTIALS_PATH_KEY: str = "credentials_path"
"""Optional chain-entry key naming that account's OAuth credentials file path."""

ALL_USAGE_LIMIT_SIGNATURES: tuple[str, ...] = (
    "hit your session limit",
    "usage limit reached",
    "out of usage",
    "usage quota exceeded",
)
"""Case-insensitive substrings that mark a non-zero exit as a usage-limit refusal."""

ATTEMPT_STATUS_SERVED: str = "served"
"""Status recorded when a binary exits zero and serves the call."""

ATTEMPT_STATUS_USAGE_LIMITED: str = "usage_limited"
"""Status recorded when a binary fails with a usage-limit signature."""

ATTEMPT_STATUS_EXECUTABLE_NOT_FOUND: str = "executable_not_found"
"""Status recorded when a binary is not installed."""

ATTEMPT_STATUS_NONZERO_EXIT: str = "nonzero_exit"
"""Status recorded when a binary fails without a usage-limit signature."""

ATTEMPT_STATUS_TIMEOUT: str = "timeout"
"""Status recorded when a binary exceeds the invocation timeout."""

DEFAULT_TIMEOUT_SECONDS: int = 300
"""Timeout applied to each binary invocation when the caller names none."""

NO_COMPLETED_PROCESS_RETURN_CODE: int = 1
"""Return code carried on the result when no binary produced a completed process."""

CHAIN_EXHAUSTED_EXIT_CODE: int = 2
"""CLI exit code when no binary in the chain served the call."""

CHAIN_CONFIG_ERROR_EXIT_CODE: int = 3
"""CLI exit code when the chain configuration is missing or invalid."""

CLI_TIMEOUT_FLAG: str = "--timeout-seconds"
"""CLI flag that overrides the per-invocation timeout in seconds."""

CLI_ARGUMENTS_SEPARATOR: str = "--"
"""CLI token separating runner flags from the passthrough claude arguments."""

CONFIG_NOT_OBJECT_REASON: str = "the top-level value is not a JSON object"
"""Reason detail when the config root is not an object."""

CONFIG_CHAIN_NOT_LIST_REASON: str = "the 'chain' key is missing or not a list"
"""Reason detail when the chain key is absent or the wrong type."""

CONFIG_CHAIN_EMPTY_REASON: str = "the 'chain' list is empty"
"""Reason detail when the chain contains no entries."""

CONFIG_ENTRY_NOT_OBJECT_REASON: str = "a chain entry is not a JSON object"
"""Reason detail when a chain entry is not an object."""

CONFIG_ENTRY_COMMAND_MISSING_REASON: str = "a chain entry has no string 'command'"
"""Reason detail when a chain entry lacks a usable command."""

CONFIG_ENTRY_EXTRA_ARGS_INVALID_REASON: str = (
    "a chain entry's 'extra_args' is not a list of strings"
)
"""Reason detail when a chain entry's extra_args value is the wrong shape."""

CONFIG_ENTRY_CREDENTIALS_PATH_INVALID_REASON: str = (
    "a chain entry's 'credentials_path' is not a non-empty string"
)
"""Reason detail when a chain entry's credentials_path value is the wrong shape."""

CONFIG_MISSING_MESSAGE_TEMPLATE: str = (
    "Claude chain config not found at {config_path}. Copy {example_filename} to "
    "{config_path} and list your account binaries. Try order comes from weekly "
    "remaining; config order is the tiebreak."
)
"""Guidance shown when the config file is absent."""

CONFIG_UNREADABLE_MESSAGE_TEMPLATE: str = (
    "Cannot read claude chain config at {config_path}: {error}. "
    "See {example_filename} for the expected shape."
)
"""Guidance shown when the config file cannot be read."""

CONFIG_MALFORMED_MESSAGE_TEMPLATE: str = (
    "Malformed JSON in claude chain config at {config_path}: {error}. "
    "See {example_filename} for the expected shape."
)
"""Guidance shown when the config file is not valid JSON."""

CONFIG_INVALID_SHAPE_MESSAGE_TEMPLATE: str = (
    "Invalid claude chain config at {config_path}: {reason}. "
    "See {example_filename} for the expected shape."
)
"""Guidance shown when the config JSON does not match the expected shape."""

CHAIN_EXHAUSTED_MESSAGE_TEMPLATE: str = (
    "No claude binary in the chain served the call. Attempts: {attempt_summary}"
)
"""CLI stderr message when the walk ends without a serving binary."""

ATTEMPT_SUMMARY_ENTRY_TEMPLATE: str = "{command}={status}"
"""Per-attempt fragment used to build the exhausted-chain summary."""

ATTEMPT_SUMMARY_JOIN_SEPARATOR: str = ", "
"""Separator joining per-attempt fragments in the exhausted-chain summary."""
