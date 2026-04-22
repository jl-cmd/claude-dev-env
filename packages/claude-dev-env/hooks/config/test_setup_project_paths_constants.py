"""Regression-guard tests for setup_project_paths_constants module."""

from __future__ import annotations

import sys
from pathlib import Path

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

import config.setup_project_paths_constants as constants_module
from config.setup_project_paths_constants import (
    ABORTED_NOTHING_WRITTEN_MESSAGE,
    CONFIRMATION_PROMPT_TEXT,
    ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS,
    STDERR_TRUNCATION_LENGTH,
    WROTE_ENTRIES_STATUS_TEMPLATE,
)


def test_es_exe_arguments_is_immutable_tuple() -> None:
    """Pin PR #230 round 6: constant must be a tuple, not a mutable list.

    Tuples unpack identically into subprocess.run([...]) args and prevent
    accidental mutation of the shared constant at call sites.
    """
    assert isinstance(ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS, tuple)


def test_es_exe_arguments_contains_folders_only_flag() -> None:
    assert "/ad" in ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS


def test_es_exe_arguments_contains_git_folder_query() -> None:
    assert "folder:.git" in ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS


def test_es_exe_arguments_do_not_include_name_flag() -> None:
    assert "-name" not in ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS


def test_user_config_file_relative_parts_is_removed() -> None:
    """Pin PR #230 round 7: dead constant USER_CONFIG_FILE_RELATIVE_PARTS removed.

    This constant had zero references after round 6 moved the canonical
    source to registry_file_path() in project_paths_reader.py.
    """
    assert not hasattr(constants_module, "USER_CONFIG_FILE_RELATIVE_PARTS")


def test_confirmation_prompt_text_constant_exists() -> None:
    """Pin PR #230 round 7: prompt string extracted from prompt_and_write magic values."""
    assert isinstance(CONFIRMATION_PROMPT_TEXT, str)
    assert len(CONFIRMATION_PROMPT_TEXT) > 0


def test_aborted_nothing_written_message_constant_exists() -> None:
    """Pin PR #230 round 7: abort message extracted from prompt_and_write magic values."""
    assert isinstance(ABORTED_NOTHING_WRITTEN_MESSAGE, str)
    assert len(ABORTED_NOTHING_WRITTEN_MESSAGE) > 0


def test_wrote_entries_status_template_constant_exists() -> None:
    """Pin PR #230 round 7: success message template extracted from prompt_and_write magic values."""
    assert isinstance(WROTE_ENTRIES_STATUS_TEMPLATE, str)
    assert "{entry_count}" in WROTE_ENTRIES_STATUS_TEMPLATE
    assert "{save_path}" in WROTE_ENTRIES_STATUS_TEMPLATE


def test_stderr_truncation_length_constant_exists() -> None:
    """Pin PR #230 round 9: STDERR_TRUNCATION_LENGTH required for EverythingScanError messages."""
    assert isinstance(STDERR_TRUNCATION_LENGTH, int)
    assert STDERR_TRUNCATION_LENGTH > 0
