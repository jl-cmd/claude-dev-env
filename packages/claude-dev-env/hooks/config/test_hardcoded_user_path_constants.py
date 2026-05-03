"""Behavior tests for hardcoded user-path detection constants."""

from __future__ import annotations

import sys
from pathlib import Path

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from config.hardcoded_user_path_constants import HARDCODED_USER_PATH_PATTERN


def test_pattern_matches_windows_user_home() -> None:
    match = HARDCODED_USER_PATH_PATTERN.search("C:/Users/jon/notes")
    assert match is not None
    assert match.group(0) == "C:/Users/jon"


def test_pattern_matches_macos_user_home() -> None:
    match = HARDCODED_USER_PATH_PATTERN.search("/Users/bob/Documents")
    assert match is not None
    assert match.group(0) == "/Users/bob"


def test_pattern_matches_linux_user_home() -> None:
    match = HARDCODED_USER_PATH_PATTERN.search("/home/alice/data")
    assert match is not None
    assert match.group(0) == "/home/alice"


def test_pattern_excludes_windows_public_shared_folder() -> None:
    assert HARDCODED_USER_PATH_PATTERN.search("C:/Users/Public/Documents") is None


def test_pattern_excludes_windows_shared_folder() -> None:
    assert HARDCODED_USER_PATH_PATTERN.search("C:/Users/Shared/data") is None


def test_pattern_excludes_windows_all_users_folder() -> None:
    assert HARDCODED_USER_PATH_PATTERN.search("C:/Users/All Users/AppData") is None


def test_pattern_excludes_macos_shared_folder() -> None:
    assert HARDCODED_USER_PATH_PATTERN.search("/Users/Shared/data") is None


def test_pattern_excludes_macos_public_shared_folder() -> None:
    assert HARDCODED_USER_PATH_PATTERN.search("/Users/Public/Documents") is None


def test_pattern_excludes_windows_lowercase_public_shared_folder() -> None:
    assert HARDCODED_USER_PATH_PATTERN.search("c:/users/public/Documents") is None


def test_pattern_excludes_windows_lowercase_shared_folder() -> None:
    assert HARDCODED_USER_PATH_PATTERN.search("c:/users/shared/data") is None


def test_pattern_excludes_windows_lowercase_all_users_folder() -> None:
    assert HARDCODED_USER_PATH_PATTERN.search("c:/users/all users/AppData") is None


def test_pattern_excludes_windows_mixed_case_public_shared_folder() -> None:
    assert HARDCODED_USER_PATH_PATTERN.search("C:/Users/PuBlIc/Documents") is None


def test_pattern_excludes_windows_uppercase_public_shared_folder() -> None:
    assert HARDCODED_USER_PATH_PATTERN.search("C:/Users/PUBLIC/Documents") is None


def test_pattern_excludes_macos_lowercase_shared_folder() -> None:
    assert HARDCODED_USER_PATH_PATTERN.search("/Users/shared/data") is None


def test_pattern_excludes_macos_lowercase_public_shared_folder() -> None:
    assert HARDCODED_USER_PATH_PATTERN.search("/Users/public/Documents") is None
