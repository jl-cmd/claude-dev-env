"""Tests for validator health checks."""

import tempfile
from pathlib import Path

import pytest

from health_check import (
    ValidatorHealth,
    check_validator_exists,
    check_all_validators,
    get_validator_version,
)


class TestValidatorExists:
    def test_existing_validator_healthy(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as temp_file:
            temp_file.write(b"print('hello')")
            temp_path = Path(temp_file.name)

        try:
            result = check_validator_exists(temp_path)
            assert result.healthy is True
            assert result.error is None
        finally:
            temp_path.unlink()

    def test_missing_validator_unhealthy(self) -> None:
        result = check_validator_exists(Path("/nonexistent/validator.py"))
        assert result.healthy is False
        assert "not found" in result.error.lower()


class TestCheckAllValidators:
    def test_returns_all_validator_statuses(self) -> None:
        validators_dir = Path(__file__).parent
        results = check_all_validators(validators_dir)
        assert isinstance(results, dict)
        assert "python_style_checks" in results


class TestGetValidatorVersion:
    def test_version_changes_when_content_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            validator_file = temp_path / "python_style_checks.py"

            validator_file.write_text("# version 1")
            version1 = get_validator_version(temp_path)

            validator_file.write_text("# version 2 - different content")
            version2 = get_validator_version(temp_path)

            assert version1 != version2
            assert isinstance(version1, str)
            assert len(version1) > 0
