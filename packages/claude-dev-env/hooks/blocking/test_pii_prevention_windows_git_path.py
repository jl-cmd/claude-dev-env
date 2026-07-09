"""Windows path detection tests for the PII prevention commit gate.

Guards the unquoted absolute Windows git path shape on the PowerShell surface::

    is_git_commit_shell_command(r"C:\\tools\\git.exe commit")
    ok:   True   -- the git.exe basename survives tokenization
    flag: False  -- backslash escaping mangles the basename token

An unquoted absolute path to the git binary must still be recognized as a
commit so a staged blob carrying PII cannot slip past the gate.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_BLOCKING_DIRECTORY = Path(__file__).resolve().parent
if str(_BLOCKING_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_BLOCKING_DIRECTORY))

_blocker_module = importlib.import_module("pii_prevention_blocker")


def test_unquoted_windows_git_exe_path_is_detected_as_commit() -> None:
    assert _blocker_module.is_git_commit_shell_command(r"C:\tools\git.exe commit -m x")


def test_unquoted_windows_git_path_without_extension_is_detected() -> None:
    assert _blocker_module.is_git_commit_shell_command(r"D:\bin\git commit -m note")


def test_quoted_windows_git_path_stays_detected_as_commit() -> None:
    assert _blocker_module.is_git_commit_shell_command(
        r'& "C:\Program Files\Git\cmd\git.exe" commit -m x'
    )


def test_unquoted_windows_git_status_is_not_a_commit() -> None:
    assert not _blocker_module.is_git_commit_shell_command(r"C:\tools\git.exe status")
