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

CRLF_NEWLINE: str = "\r\n"
"""Windows-style newline sequence normalized away when decoding spool captures."""

CARRIAGE_RETURN: str = "\r"
"""Bare carriage return normalized to LF when decoding spool captures."""

LINE_FEED: str = "\n"
"""Unix-style newline retained after universal-newline normalization."""

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

CLI_ROUTING_MODE_FLAG: str = "--routing-mode"
"""CLI flag that selects usage-ranked or ordered-account chain routing."""

CLI_ARGUMENTS_SEPARATOR: str = "--"
"""CLI token separating runner flags from the passthrough claude arguments."""

ROUTING_MODE_USAGE_RANKED: str = "usage_ranked"
"""Default routing: probe weekly remaining and try highest remaining first."""

ROUTING_MODE_ORDERED_ACCOUNT: str = "ordered_account"
"""Explicit routing: walk chain entries in config order; usage-limit-only fallover."""

DEFAULT_ROUTING_MODE: str = ROUTING_MODE_USAGE_RANKED
"""Routing mode applied when the caller does not name one."""

ALL_ROUTING_MODES: frozenset[str] = frozenset(
    {
        ROUTING_MODE_USAGE_RANKED,
        ROUTING_MODE_ORDERED_ACCOUNT,
    }
)
"""Accepted values for the routing-mode parameter and CLI flag."""

TERMINAL_STATUS_SERVED: str = "served"
"""Outcome status when a binary served the call (zero or non-usage nonzero)."""

TERMINAL_STATUS_ADVISOR_BLOCKED: str = "advisor_blocked"
"""Outcome status when ordered-account mode stops on a non-usage failure."""

TERMINAL_STATUS_CHAIN_EXHAUSTED: str = "chain_exhausted"
"""Outcome status when every chain entry was usage-limited or missing."""

TERMINAL_STATUS_TIMEOUT: str = "timeout"
"""Outcome status when a usage-ranked walk stops on TimeoutExpired mid-walk."""

SESSION_ID_JSON_KEY: str = "session_id"
"""JSON key read from Claude ``--output-format json`` events for resume."""

CHAIN_ADVISOR_BLOCKED_EXIT_CODE: int = 4
"""CLI exit code when ordered-account mode stops with advisor_blocked."""

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

AFFINITY_STATE_SCHEMA_VERSION: int = 1
"""Version field written into the session-to-binary affinity state document."""

AFFINITY_STATE_FILENAME: str = "claude-chain-affinity.json"
"""Default affinity state file name under the Claude home directory."""

AFFINITY_MAXIMUM_ENTRIES: int = 64
"""Hard cap on retained session-to-binary affinity rows (oldest drop first)."""

AFFINITY_KEY_SCHEMA_VERSION: str = "schema_version"
"""JSON key for the affinity document schema version."""

AFFINITY_KEY_ALL_BINDINGS: str = "all_bindings"
"""JSON key for the ordered list of session-to-command bindings."""

AFFINITY_KEY_SESSION_ID: str = "session_id"
"""JSON key for a bound Claude session id."""

AFFINITY_KEY_COMMAND: str = "command"
"""JSON key for the chain binary command bound to a session id."""

AFFINITY_TEMP_SUFFIX: str = ".tmp"
"""Suffix for the temporary file used during atomic affinity replacement."""

AFFINITY_BINDING_NOT_OBJECT_REASON: str = "a binding entry is not an object"
"""Reason when an affinity binding entry is not a JSON object."""

AFFINITY_BINDING_SESSION_ID_MISSING_REASON: str = (
    "binding missing non-empty session_id"
)
"""Reason when an affinity binding lacks a usable session_id."""

AFFINITY_BINDING_COMMAND_MISSING_REASON: str = "binding missing non-empty command"
"""Reason when an affinity binding lacks a usable command."""

AFFINITY_UNSUPPORTED_SCHEMA_VERSION_REASON_TEMPLATE: str = (
    "unsupported schema_version {schema_version!r}"
)
"""Reason when the affinity document schema version is not supported."""

AFFINITY_BINDINGS_MISSING_OR_NOT_LIST_REASON: str = (
    "all_bindings is missing or not a list"
)
"""Reason when all_bindings is absent or the wrong type."""

AFFINITY_TOP_LEVEL_NOT_OBJECT_REASON: str = "top-level value is not a JSON object"
"""Reason when the affinity document root is not an object."""

AFFINITY_SESSION_ID_AND_COMMAND_REQUIRED_MESSAGE: str = (
    "session_id and command must be non-empty"
)
"""ValueError message when record_affinity_binding receives empty ids."""

AFFINITY_MAXIMUM_ENTRIES_MINIMUM_MESSAGE: str = "maximum_entries must be at least 1"
"""ValueError message when maximum_entries is below one."""

AFFINITY_CORRUPT_MESSAGE_TEMPLATE: str = (
    "Affinity state at {state_path} is corrupt or unreadable: {error}. "
    "Delete or repair the file before retrying."
)
"""Actionable diagnostic when affinity state cannot be loaded."""

AFFINITY_WRITE_FAILED_MESSAGE_TEMPLATE: str = (
    "Failed to write affinity state at {state_path}: {error}. "
    "Check directory permissions and free space."
)
"""Actionable diagnostic when atomic affinity replacement fails."""

AFFINITY_JSON_INDENT_SPACES: int = 2
"""Indent width for the written affinity state JSON document."""

RESUME_SESSION_FLAG: str = "--resume"
"""Claude CLI flag that continues a prior session by id."""
