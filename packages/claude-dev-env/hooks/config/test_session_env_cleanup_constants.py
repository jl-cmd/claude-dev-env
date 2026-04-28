"""Tests for session_env_cleanup_constants — behavioral checks on SESSION_ID_PATTERN."""

from __future__ import annotations

import sys
from pathlib import Path

_CONFIG_DIRECTORY = Path(__file__).resolve().parent
_HOOKS_ROOT = _CONFIG_DIRECTORY.parent
for each_sys_path_entry in (str(_CONFIG_DIRECTORY), str(_HOOKS_ROOT)):
    if each_sys_path_entry not in sys.path:
        sys.path.insert(0, each_sys_path_entry)

from config.session_env_cleanup_constants import SESSION_ID_PATTERN, SESSION_ID_PAYLOAD_KEY


class TestSessionIdPatternAccepts:
    def test_accepts_uuid_with_hyphens(self) -> None:
        valid_uuid_input = "5fcc01b3-138b-49e1-9976-ff1035013a4f"
        matched = SESSION_ID_PATTERN.fullmatch(valid_uuid_input)
        assert matched.group(0) == valid_uuid_input

    def test_accepts_alphanumeric_only(self) -> None:
        alphanumeric_input = "abc123XYZ"
        matched = SESSION_ID_PATTERN.fullmatch(alphanumeric_input)
        assert matched.group(0) == alphanumeric_input

    def test_accepts_underscore_separated(self) -> None:
        underscore_input = "session_42_alpha"
        matched = SESSION_ID_PATTERN.fullmatch(underscore_input)
        assert matched.group(0) == underscore_input


class TestSessionIdPayloadKey:
    def test_session_id_payload_key_matches_hook_protocol_field(self) -> None:
        assert SESSION_ID_PAYLOAD_KEY == "session_id"


class TestSessionIdPatternRejects:
    def test_rejects_forward_slash(self) -> None:
        assert SESSION_ID_PATTERN.match("etc/passwd") is None

    def test_rejects_back_slash(self) -> None:
        assert SESSION_ID_PATTERN.match("Users\\jon") is None

    def test_rejects_parent_traversal(self) -> None:
        assert SESSION_ID_PATTERN.match("..") is None

    def test_rejects_absolute_windows_path(self) -> None:
        assert SESSION_ID_PATTERN.match("C:\\Windows\\Temp") is None

    def test_rejects_empty_string(self) -> None:
        assert SESSION_ID_PATTERN.match("") is None

    def test_rejects_overlong_input(self) -> None:
        overlong_input = "a" * 65
        assert SESSION_ID_PATTERN.match(overlong_input) is None

    def test_rejects_dot_in_middle(self) -> None:
        assert SESSION_ID_PATTERN.match("session.uuid") is None
