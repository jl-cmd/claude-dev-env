"""Tests for validator health checks."""

from pathlib import Path

import pytest

from .health_check import (
    SystemHealth,
    ValidatorHealth,
    ValidatorStatus,
    check_validator_exists,
    check_all_validators,
    get_validator_version,
    print_health_report,
)


class TestValidatorExists:
    def test_existing_validator_is_ready(self, tmp_path: Path) -> None:
        validator_path = tmp_path / "validator.py"
        validator_path.write_text("print('hello')", encoding="utf-8")

        result = check_validator_exists(validator_path)

        assert result.is_healthy is True
        assert result.healthy is result.is_healthy
        assert result.status is ValidatorStatus.READY
        assert result.error is None
        assert result.is_present is True

    def test_missing_validator_requires_a_file(self) -> None:
        result = check_validator_exists(Path("/nonexistent/validator.py"))
        assert result.is_healthy is False
        assert result.status is ValidatorStatus.FILE_REQUIRED
        assert result.is_present is False
        assert "file required" in result.error.lower()

    def test_unreadable_validator_reports_read_access_state(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        validator_path = tmp_path / "validator.py"
        validator_path.write_text("print('ready')", encoding="utf-8")

        def raise_read_error(*_args: object, **_kwargs: object) -> str:
            raise OSError("permission detail")

        monkeypatch.setattr(Path, "read_text", raise_read_error)

        result = check_validator_exists(validator_path)

        assert result.is_healthy is False
        assert result.status is ValidatorStatus.ACCESS_REQUIRED
        assert result.is_present is True
        assert "read access requires attention" in result.error.lower()

    def test_directory_at_validator_path_requires_a_file(self, tmp_path: Path) -> None:
        validator_path = tmp_path / "validator.py"
        validator_path.mkdir()

        result = check_validator_exists(validator_path)

        assert result.is_healthy is False
        assert result.status is ValidatorStatus.FILE_REQUIRED
        assert result.is_present is False

    def test_validator_disappearance_reports_file_required(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        validator_path = tmp_path / "validator.py"
        validator_path.write_text("print('ready')", encoding="utf-8")

        original_read_text = Path.read_text

        def remove_before_read(
            each_path: Path, **all_keyword_arguments: object
        ) -> str:
            each_path.unlink()
            return original_read_text(each_path, **all_keyword_arguments)

        monkeypatch.setattr(Path, "read_text", remove_before_read)

        result = check_validator_exists(validator_path)

        assert result.status is ValidatorStatus.FILE_REQUIRED
        assert result.is_present is False


class TestCheckAllValidators:
    def test_returns_all_validator_statuses(self) -> None:
        validators_dir = Path(__file__).parent
        results = check_all_validators(validators_dir)
        assert isinstance(results, dict)
        assert "python_style_checks" in results


class TestGetValidatorVersion:
    def test_version_changes_when_content_changes(self, tmp_path: Path) -> None:
        validator_file = tmp_path / "python_style_checks.py"

        validator_file.write_text("# version 1")
        version1 = get_validator_version(tmp_path)

        validator_file.write_text("# version 2 - different content")
        version2 = get_validator_version(tmp_path)

        assert version1 != version2
        assert isinstance(version1, str)
        assert len(version1) > 0


def test_print_health_report_distinguishes_validator_states(
    capsys: pytest.CaptureFixture[str],
) -> None:
    health = SystemHealth(
        all_healthy=False,
        validators={
            "missing_validator": ValidatorHealth(
                name="missing_validator",
                status=ValidatorStatus.FILE_REQUIRED,
                error="Validator file required: missing_validator.py",
            ),
            "unreadable_validator": ValidatorHealth(
                name="unreadable_validator",
                status=ValidatorStatus.ACCESS_REQUIRED,
                error="Validator read access requires attention: permission detail",
            ),
        },
        python_version="3.12.0",
        optional_tools={"mypy": True, "ruff": False},
    )

    print_health_report(health)

    report = capsys.readouterr().out
    assert "[FILE REQUIRED] missing_validator" in report
    assert "[ACCESS REQUIRED] unreadable_validator" in report
    assert "[READY] mypy" in report
    assert "[OPTIONAL] ruff" in report
