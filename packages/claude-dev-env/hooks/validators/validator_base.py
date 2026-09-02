"""Base classes for validators.

Provides shared dataclasses used across all validator modules.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Violation:
    """Represents a validation violation."""

    file: str
    line: int
    message: str

    def __str__(self) -> str:
        """Format as file:line: message."""
        return f"{self.file}:{self.line}: {self.message}"


@dataclass(frozen=True)
class ValidatorResult:
    """Result from running a validator."""

    name: str
    checks: str
    passed: bool
    output: str
    skipped: bool = False
