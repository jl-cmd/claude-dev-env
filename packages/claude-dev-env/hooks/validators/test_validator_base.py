"""Tests for shared validator base types."""

import pytest

from validator_base import Violation


class TestViolation:
    def test_violation_str_format(self) -> None:
        violation = Violation(file="test.py", line=42, message="Test message")
        assert str(violation) == "test.py:42: Test message"

    def test_violation_is_immutable(self) -> None:
        violation = Violation(file="test.py", line=42, message="Test message")
        with pytest.raises(AttributeError):
            violation.file = "other.py"

    def test_violation_equality(self) -> None:
        v1 = Violation(file="test.py", line=42, message="Test message")
        v2 = Violation(file="test.py", line=42, message="Test message")
        assert v1 == v2

    def test_violation_hashable(self) -> None:
        violation = Violation(file="test.py", line=42, message="Test message")
        violation_set = {violation}
        assert violation in violation_set
