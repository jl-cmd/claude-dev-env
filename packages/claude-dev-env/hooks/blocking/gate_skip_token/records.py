"""Per-session skip tokens that escalate a gate deny to a human permission prompt.

::

    write foo.py (proposed content)  -> gate deny, real findings
    user picks "refactor to pass"    -> agent may record a token for (foo, sha256)
    retry write foo.py               -> gate reads the token; under default mode,
                                        with a subset of the on-disk findings, it
                                        emits "ask" and consumes the token

A token binds a session, a file path, and the sha256 of the proposed content,
and carries a record time. A token past the freshness window is ignored, and a
consumed token is removed so it opens the gate once. Each session keeps one JSON
file under the temp directory, and a missing or corrupt file reads as no tokens.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

from gate_skip_token.config.gate_skip_token_constants import (
    ALL_SKIP_TOKENS_KEY,
    DEFAULT_PERMISSION_MODE,
    GATE_SKIP_TOKEN_FILE_PREFIX,
    GATE_SKIP_TOKEN_FILE_SUFFIX,
    GATE_SKIP_TOKEN_FRESHNESS_WINDOW_SECONDS,
    SKIP_TOKEN_CONTENT_SHA256_FIELD,
    SKIP_TOKEN_FILE_PATH_FIELD,
    SKIP_TOKEN_RECORDED_AT_FIELD,
    SKIP_TOKEN_SESSION_FIELD,
)

from hooks_constants.session_edit_stage_gate_constants import (
    SESSION_ID_UNSAFE_CHARACTERS_PATTERN,
    STATE_FILE_ATOMIC_WRITE_SUFFIX,
    STATE_FILE_DEFAULT_SESSION_ID,
    STATE_FILE_JSON_INDENT_SPACES,
)


def content_sha256(text: str) -> str:
    """Return the lowercase hex sha256 of the text's utf-8 bytes.

    The gate and the agent hash the same proposed file content, so the token
    binds to exactly the bytes the retry write carries.

    Args:
        text: The full proposed file content the token binds to.

    Returns:
        The 64-character lowercase hex sha256 digest of the encoded text.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _skip_token_file_path(session_id: str) -> Path:
    """Return this session's skip-token file in the temp directory.

    Args:
        session_id: Raw session id; unsafe characters are stripped and an empty
            result falls back to the default id.

    Returns:
        The absolute path of this session's skip-token file.
    """
    sanitized_session_id = SESSION_ID_UNSAFE_CHARACTERS_PATTERN.sub("", session_id)
    effective_session_id = sanitized_session_id or STATE_FILE_DEFAULT_SESSION_ID
    file_name = f"{GATE_SKIP_TOKEN_FILE_PREFIX}{effective_session_id}{GATE_SKIP_TOKEN_FILE_SUFFIX}"
    return Path(tempfile.gettempdir()) / file_name


def _empty_records() -> dict[str, list[dict[str, object]]]:
    """Return an empty single-list token structure."""
    return {ALL_SKIP_TOKENS_KEY: []}


def _skip_token_list(all_records: dict[str, object]) -> list[dict[str, object]]:
    """Return the well-formed token dictionaries stored under the list key.

    Args:
        all_records: A parsed records payload.

    Returns:
        Each dictionary entry under the key; a malformed value yields an empty list.
    """
    stored_value = all_records.get(ALL_SKIP_TOKENS_KEY, [])
    if not isinstance(stored_value, list):
        return []
    return [each_entry for each_entry in stored_value if isinstance(each_entry, dict)]


def _read_records(session_id: str) -> dict[str, list[dict[str, object]]]:
    """Return this session's tokens, or an empty structure when unreadable.

    Args:
        session_id: Raw session id keying the shared token file.

    Returns:
        The single-list token structure; a missing, malformed, or wrong-shape
        file reads as an empty structure so a storage fault falls back to no tokens.
    """
    token_file = _skip_token_file_path(session_id)
    try:
        raw_text = token_file.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return _empty_records()
    try:
        parsed_payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return _empty_records()
    if not isinstance(parsed_payload, dict):
        return _empty_records()
    return {ALL_SKIP_TOKENS_KEY: _skip_token_list(parsed_payload)}


def _write_records(session_id: str, all_records: dict[str, list[dict[str, object]]]) -> None:
    """Write the token structure atomically, failing open on an OS error.

    Args:
        session_id: Raw session id keying the shared token file.
        all_records: The full token structure to persist.
    """
    token_file = _skip_token_file_path(session_id)
    temporary_file = token_file.with_name(token_file.name + STATE_FILE_ATOMIC_WRITE_SUFFIX)
    encoded_text = json.dumps(all_records, indent=STATE_FILE_JSON_INDENT_SPACES)
    try:
        temporary_file.write_text(encoded_text, encoding="utf-8")
        os.replace(str(temporary_file), str(token_file))
    except OSError:
        return


def _is_fresh(skip_token: dict, current_time: float) -> bool:
    """Return whether one token was recorded within the freshness window.

    Args:
        skip_token: One stored token dictionary.
        current_time: The current epoch time.

    Returns:
        True when the record time is present and within the window.
    """
    recorded_at = skip_token.get(SKIP_TOKEN_RECORDED_AT_FIELD)
    if not isinstance(recorded_at, (int, float)):
        return False
    return current_time - float(recorded_at) <= GATE_SKIP_TOKEN_FRESHNESS_WINDOW_SECONDS


def _matches_target(skip_token: dict, file_path: str, content_hash: str) -> bool:
    """Return whether one token names the given file path and content hash.

    Args:
        skip_token: One stored token dictionary.
        file_path: The write target to match.
        content_hash: The proposed-content sha256 to match.

    Returns:
        True when both the file-path and content-hash fields equal the target.
    """
    return (
        skip_token.get(SKIP_TOKEN_FILE_PATH_FIELD) == file_path
        and skip_token.get(SKIP_TOKEN_CONTENT_SHA256_FIELD) == content_hash
    )


def record_skip_token(session_id: str, file_path: str, content_hash: str) -> None:
    """Record one skip token, dropping stale tokens and any prior same-target token.

    Args:
        session_id: Raw session id keying the shared token file.
        file_path: The write target the token authorizes an escalation for.
        content_hash: The sha256 of the proposed content the token binds to.
    """
    all_records = _read_records(session_id)
    current_time = time.time()
    kept_tokens = [
        each_token
        for each_token in all_records[ALL_SKIP_TOKENS_KEY]
        if _is_fresh(each_token, current_time)
        and not _matches_target(each_token, file_path, content_hash)
    ]
    kept_tokens.append(
        {
            SKIP_TOKEN_SESSION_FIELD: session_id,
            SKIP_TOKEN_FILE_PATH_FIELD: file_path,
            SKIP_TOKEN_CONTENT_SHA256_FIELD: content_hash,
            SKIP_TOKEN_RECORDED_AT_FIELD: current_time,
        }
    )
    all_records[ALL_SKIP_TOKENS_KEY] = kept_tokens
    _write_records(session_id, all_records)


def has_valid_skip_token(session_id: str, file_path: str, content_hash: str) -> bool:
    """Return whether a fresh token names the file path and content hash.

    Args:
        session_id: Raw session id keying the shared token file.
        file_path: The write target to match.
        content_hash: The proposed-content sha256 to match.

    Returns:
        True when a matching fresh token exists.
    """
    all_records = _read_records(session_id)
    current_time = time.time()
    return any(
        _is_fresh(each_token, current_time) and _matches_target(each_token, file_path, content_hash)
        for each_token in all_records[ALL_SKIP_TOKENS_KEY]
    )


def consume_skip_token(session_id: str, file_path: str, content_hash: str) -> None:
    """Remove every token naming the file path and content hash, one-shot.

    Args:
        session_id: Raw session id keying the shared token file.
        file_path: The write target of the consumed token.
        content_hash: The proposed-content sha256 of the consumed token.
    """
    all_records = _read_records(session_id)
    current_time = time.time()
    remaining_tokens = [
        each_token
        for each_token in all_records[ALL_SKIP_TOKENS_KEY]
        if _is_fresh(each_token, current_time)
        and not _matches_target(each_token, file_path, content_hash)
    ]
    all_records[ALL_SKIP_TOKENS_KEY] = remaining_tokens
    _write_records(session_id, all_records)


def should_downgrade_to_ask(
    permission_mode: str, proposed_is_subset_of_current: bool, has_token: bool
) -> bool:
    """Return whether the gate may escalate a deny to a human permission prompt.

    The escalation holds only under the default permission mode, only when the
    proposed findings are a subset of the on-disk findings, and only when a valid
    token backs the retry, so a token never carries a new violation past.

    Args:
        permission_mode: The PreToolUse permission mode of the retry write.
        proposed_is_subset_of_current: Whether every proposed finding is already
            present on disk.
        has_token: Whether a valid token backs the retry write.

    Returns:
        True only when the mode is default and the findings are a subset and a
        token backs the retry.
    """
    return (
        permission_mode == DEFAULT_PERMISSION_MODE and proposed_is_subset_of_current and has_token
    )
