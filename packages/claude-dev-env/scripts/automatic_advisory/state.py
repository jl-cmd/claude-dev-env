from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from .config.constants import (
    JSON_INDENT_SPACES,
    REPORT_NEWLINE,
    STATE_BASE_SHA_KEY,
    STATE_FILE_SUFFIX,
    STATE_HEAD_SHA_KEY,
    STATE_LAST_POLL_KEY,
    STATE_LAST_RUN_KEY,
    STATE_PULL_REQUEST_KEY,
    STATE_REASON_KEY,
    STATE_REPORT_KEY,
    STATE_REPOSITORY_KEY,
    STATE_STATUS_KEY,
    STATE_VERSION,
    STATE_VERSION_KEY,
    UTF8_ENCODING,
)
from .model import AdvisoryState


def read_state(state_path: Path) -> AdvisoryState | None:
    """Read one persisted advisory state when its shape is valid.

    Args:
        state_path: JSON state file to read.

    Returns:
        Parsed advisory state, or None when the file is absent or invalid.
    """
    try:
        parsed_state = json.loads(state_path.read_text(encoding=UTF8_ENCODING))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(parsed_state, Mapping):
        return None
    return _state_from_mapping(parsed_state)


def _state_from_mapping(
    all_state_fields: Mapping[str, object],
) -> AdvisoryState | None:
    if all_state_fields.get(STATE_VERSION_KEY) != STATE_VERSION:
        return None
    try:
        repository = _require_state_text(all_state_fields.get(STATE_REPOSITORY_KEY))
        status = _require_state_text(all_state_fields.get(STATE_STATUS_KEY))
        reason = _require_state_text(all_state_fields.get(STATE_REASON_KEY))
        last_poll = _require_state_text(all_state_fields.get(STATE_LAST_POLL_KEY))
        report_path = _require_state_text(all_state_fields.get(STATE_REPORT_KEY))
    except TypeError:
        return None
    pull_request_number = all_state_fields.get(STATE_PULL_REQUEST_KEY)
    if not isinstance(pull_request_number, int):
        return None
    return AdvisoryState(
        repository,
        pull_request_number,
        status,
        reason,
        _optional_text(all_state_fields.get(STATE_HEAD_SHA_KEY)),
        _optional_text(all_state_fields.get(STATE_BASE_SHA_KEY)),
        last_poll,
        _optional_text(all_state_fields.get(STATE_LAST_RUN_KEY)),
        report_path,
    )


def _require_state_text(state_field: object) -> str:
    if not isinstance(state_field, str):
        raise TypeError("state field must be text")
    return state_field


def _optional_text(state_field: object) -> str | None:
    return state_field if isinstance(state_field, str) else None


def write_state(state_path: Path, state: AdvisoryState) -> None:
    """Atomically persist one advisory state.

    Args:
        state_path: Destination JSON state file.
        state: State record to persist.
    """
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_mapping = {
        STATE_VERSION_KEY: STATE_VERSION,
        STATE_REPOSITORY_KEY: state.repository,
        STATE_PULL_REQUEST_KEY: state.pull_request_number,
        STATE_STATUS_KEY: state.status,
        STATE_REASON_KEY: state.reason,
        STATE_HEAD_SHA_KEY: state.head_sha,
        STATE_BASE_SHA_KEY: state.base_sha,
        STATE_LAST_POLL_KEY: state.last_poll,
        STATE_LAST_RUN_KEY: state.last_run,
        STATE_REPORT_KEY: state.report_path,
    }
    temporary_state_path = state_path.with_name(state_path.name + STATE_FILE_SUFFIX)
    temporary_state_path.write_text(
        json.dumps(state_mapping, indent=JSON_INDENT_SPACES, sort_keys=True)
        + REPORT_NEWLINE,
        encoding=UTF8_ENCODING,
    )
    os.replace(temporary_state_path, state_path)


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()
