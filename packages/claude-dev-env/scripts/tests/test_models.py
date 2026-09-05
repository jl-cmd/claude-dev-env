"""Behavior tests for repository-check report models."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIRECTORY))

from repository_checks.config.constants import (
    FAILED_CHECK_EXIT_CODE,
    FINDINGS_EXIT_CODE,
    SUCCESS_EXIT_CODE,
)
from repository_checks.models import RepositoryCheckReport, RepositoryFinding


def test_should_choose_exit_code_by_report_severity() -> None:
    finding = RepositoryFinding("check", "file.py", "message")
    assert RepositoryCheckReport((), ()).exit_code == SUCCESS_EXIT_CODE
    assert RepositoryCheckReport((finding,), ()).exit_code == FINDINGS_EXIT_CODE
    assert RepositoryCheckReport((finding,), ("check",)).exit_code == (
        FAILED_CHECK_EXIT_CODE
    )
