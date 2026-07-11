"""Health checks for validator availability and status.

Provides:
- Validator file existence checks
- Dependency availability checks
- Version tracking
"""

import hashlib
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
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


@dataclass(frozen=True)
class ValidatorHealth:
    """Health status of a single validator."""

    name: str
    healthy: bool
    error: Optional[str] = None
    last_modified: Optional[datetime] = None


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

    if not validator_path.exists():
        return ValidatorHealth(
            name=name,
            healthy=False,
            error=f"Validator not found: {validator_path}",
        )

    try:
        validator_path.read_text(encoding="utf-8")
        mtime = datetime.fromtimestamp(validator_path.stat().st_mtime)
        return ValidatorHealth(
            name=name,
            healthy=True,
            last_modified=mtime,
        )
    except (IOError, OSError, PermissionError) as error:
        return ValidatorHealth(
            name=name,
            healthy=False,
            error=f"Cannot read validator: {error}",
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
            content = validator_path.read_bytes()
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
    all_healthy = all(v.healthy for v in validators.values())

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
        status = "[OK]" if validator.healthy else "[MISSING]"
        print(f"  {status} {name}")
        if validator.error:
            print(f"         Error: {validator.error}")
    print()

    print("Optional Tools:")
    for tool, available in sorted(health.optional_tools.items()):
        status = "[OK]" if available else "[NOT INSTALLED]"
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
