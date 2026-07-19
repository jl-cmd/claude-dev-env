"""The validator result record and its fail-closed fault mapper."""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ValidatorResult:
    """Result from running a validator."""

    name: str
    checks: str
    passed: bool
    output: str
    skipped: bool = False


def run_with_fallback(
    validator_func: Callable[[], ValidatorResult],
    fallback_name: str,
    fallback_checks: str,
) -> ValidatorResult:
    """Run one validator, mapping any fault to a fail-closed blocking result.

    ::

        healthy validator          -> its own ValidatorResult
        validator raises any error -> flag: failed (not skipped), names the check

    A validator that raises cannot take down the whole batch, and its fault is
    never a pass or a skip. The returned result is a failure that names the
    faulted validator, so the gate blocks the write and the deny reason
    attributes the block to the check that could not run. Mapping a crash to a
    skip would let content crafted to trip one validator bypass that check.

    Args:
        validator_func: The validator call to run.
        fallback_name: The validator's name, carried into a fault result.
        fallback_checks: The validator's check numbers, carried into a fault result.

    Returns:
        The validator's own result on success, or a failed result that names
        the faulted validator on any exception.
    """
    try:
        return validator_func()
    except Exception as error:
        return ValidatorResult(
            name=fallback_name,
            checks=fallback_checks,
            passed=False,
            output=f"check could not run; write blocked (validator error: {error})",
        )
