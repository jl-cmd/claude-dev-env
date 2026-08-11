"""Health checks for validator availability and status.

Provides:
- Validator file existence checks
- Dependency availability checks
- Version tracking
"""

import hashlib
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Dict, Optional

VALIDATOR_FILES = [
    "python_style_checks.py",
    "test_safety_checks.py",
    "file_structure_checks.py",
    "react_checks.py",
    "git_checks.py",
    "comment_checks.py",
]


class ValidatorStatus(StrEnum):
    """Displayed state for one required validator."""

    READY = "[READY]"
    FILE_REQUIRED = "[FILE REQUIRED]"
    ACCESS_REQUIRED = "[ACCESS REQUIRED]"


@dataclass(frozen=True)
class ValidatorHealth:
    """Health status of a single validator."""

    name: str
    status: ValidatorStatus
    error: Optional[str] = None
    last_modified: Optional[datetime] = None

    @property
    def is_healthy(self) -> bool:
        """Return whether the validator is ready for use."""
        return self.status is ValidatorStatus.READY

    @property
    def healthy(self) -> bool:
        """Return the readiness state for compatibility readers."""
        return self.is_healthy

    @property
    def is_present(self) -> bool:
        """Return whether the validator file is present on disk."""
        return self.status is not ValidatorStatus.FILE_REQUIRED


@dataclass(frozen=True)
class SystemHealth:
    """Overall system health status."""

    all_healthy: bool
    validators: Dict[str, ValidatorHealth]
    python_version: str
    optional_tools: Dict[str, bool]


def check_validator_exists(validator_path: Path) -> ValidatorHealth:
    """Check if a validator file exists and is readable.

    Args:
        validator_path: Path to validator Python file

    Returns:
        ValidatorHealth with status
    """
    name = validator_path.stem

    try:
        validator_stat = validator_path.stat()
        if not stat.S_ISREG(validator_stat.st_mode):
            return ValidatorHealth(
                name=name,
                status=ValidatorStatus.FILE_REQUIRED,
                error=f"Validator file required: {validator_path}",
            )
        validator_path.read_text(encoding="utf-8")
        return ValidatorHealth(
            name=name,
            status=ValidatorStatus.READY,
            last_modified=datetime.fromtimestamp(
                validator_stat.st_mtime, tz=timezone.utc
            ),
        )
    except FileNotFoundError:
        return ValidatorHealth(
            name=name,
            status=ValidatorStatus.FILE_REQUIRED,
            error=f"Validator file required: {validator_path}",
        )
    except (IOError, OSError, PermissionError) as error:
        return ValidatorHealth(
            name=name,
            status=ValidatorStatus.ACCESS_REQUIRED,
            error=f"Validator read access requires attention: {error}",
        )


def check_all_validators(validators_dir: Path) -> Dict[str, ValidatorHealth]:
    """Check health of all required validators.

    Args:
        validators_dir: Directory containing validator files

    Returns:
        Dict mapping validator names to health status
    """
    results: Dict[str, ValidatorHealth] = {}

    for validator_file in VALIDATOR_FILES:
        validator_path = validators_dir / validator_file
        health = check_validator_exists(validator_path)
        results[health.name] = health

    return results


def check_optional_tool(tool_name: str) -> bool:
    """Check if an optional tool is available.

    Args:
        tool_name: Name of tool to check (ruff, mypy, isort)

    Returns:
        True if tool is available
    """
    try:
        result = subprocess.run(
            [tool_name, "--version"],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def get_validator_version(validators_dir: Optional[Path] = None) -> str:
    """Get a version string for the validator suite.

    Args:
        validators_dir: Optional override for validators directory

    Returns:
        Version string based on file hashes
    """
    if validators_dir is None:
        validators_dir = Path(__file__).parent
    hasher = hashlib.md5()

    for validator_file in sorted(VALIDATOR_FILES):
        validator_path = validators_dir / validator_file
        if validator_path.exists():
            try:
                content = validator_path.read_bytes()
            except (FileNotFoundError, OSError):
                continue
            hasher.update(content)

    return hasher.hexdigest()[:8]


def get_system_health(validators_dir: Optional[Path] = None) -> SystemHealth:
    """Get complete system health status.

    Args:
        validators_dir: Optional override for validators directory

    Returns:
        SystemHealth with all status information
    """
    if validators_dir is None:
        validators_dir = Path(__file__).parent

    validators = check_all_validators(validators_dir)
    all_healthy = all(v.is_healthy for v in validators.values())

    optional_tools = {
        "ruff": check_optional_tool("ruff"),
        "mypy": check_optional_tool("mypy"),
        "isort": check_optional_tool("isort"),
    }

    return SystemHealth(
        all_healthy=all_healthy,
        validators=validators,
        python_version=sys.version,
        optional_tools=optional_tools,
    )


def print_health_report(health: SystemHealth) -> None:
    """Print a formatted health report.

    Args:
        health: SystemHealth to report
    """
    print("=" * 60)
    print("VALIDATOR HEALTH CHECK")
    print("=" * 60)
    print()

    print(f"Python: {health.python_version.split()[0]}")
    print(f"Version: {get_validator_version()}")
    print()

    print("Required Validators:")
    for name, validator in sorted(health.validators.items()):
        print(f"  {validator.status.value} {name}")
        if validator.error:
            print(f"         Error: {validator.error}")
    print()

    print("Optional Tools:")
    for tool, available in sorted(health.optional_tools.items()):
        status = ValidatorStatus.READY.value if available else "[OPTIONAL]"
        print(f"  {status} {tool}")
    print()

    overall = "HEALTHY" if health.all_healthy else "DEGRADED"
    print(f"Overall Status: {overall}")
    print("=" * 60)


def main() -> int:
    """Run health check and print report."""
    health = get_system_health()
    print_health_report(health)
    return 0 if health.all_healthy else 1


if __name__ == "__main__":
    sys.exit(main())
