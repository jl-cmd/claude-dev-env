"""Tests for the validator result record and its fail-closed fault mapper."""

from .validator_result import ValidatorResult, run_with_fallback


class TestGracefulDegradation:
    def test_missing_validator_fails_closed_naming_the_check(self) -> None:
        def failing_validator() -> ValidatorResult:
            raise FileNotFoundError("validator.py not found")

        blocking_result = run_with_fallback(
            failing_validator,
            "Missing Validator",
            "99",
        )

        assert blocking_result.passed is False
        assert blocking_result.skipped is False
        assert blocking_result.name == "Missing Validator"
        assert "write blocked" in blocking_result.output.lower()

    def test_validator_exception_fails_closed_naming_the_check(self) -> None:
        def crashing_validator() -> ValidatorResult:
            raise RuntimeError("Unexpected crash")

        blocking_result = run_with_fallback(
            crashing_validator,
            "Crashing Validator",
            "99",
        )

        assert blocking_result.passed is False
        assert blocking_result.skipped is False
        assert blocking_result.name == "Crashing Validator"
        assert "write blocked" in blocking_result.output.lower()

    def test_successful_validator_returns_normal_result(self) -> None:
        def working_validator() -> ValidatorResult:
            return ValidatorResult(
                name="Working",
                checks="1",
                passed=True,
                output="All good",
            )

        result = run_with_fallback(
            working_validator,
            "Working",
            "1",
        )

        assert result.skipped is False
        assert result.passed is True
