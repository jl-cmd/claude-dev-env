"""Tests for PR/commit reference detection in comments."""

from pathlib import Path

import pytest

from .pr_reference_checks import (
    check_pr_references,
    validate_file,
)
from .validator_base import Violation


GOOD_NO_REFERENCES = '''
def process():
    result = calculate()
    return result
'''


class TestPrReferences:
    def test_no_references_pass(self) -> None:
        violations = check_pr_references(GOOD_NO_REFERENCES, "test.py")
        assert violations == []

    def test_pr_reference_in_comment_fails(self) -> None:
        code = "# Fixed in PR #99\ndef foo(): pass"
        violations = check_pr_references(code, "test.py")
        assert len(violations) == 1
        assert "PR" in violations[0].message

    def test_commit_reference_fails(self) -> None:
        code = "# See commit abc123\ndef foo(): pass"
        violations = check_pr_references(code, "test.py")
        assert len(violations) == 1
        assert "commit" in violations[0].message.lower()

    def test_issue_hash_reference_fails(self) -> None:
        code = "# Addresses #17\ndef foo(): pass"
        violations = check_pr_references(code, "test.py")
        assert len(violations) == 1
