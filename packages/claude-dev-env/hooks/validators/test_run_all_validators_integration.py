"""Integration test for new validators in run_all_validators.py"""

import subprocess
import sys
from pathlib import Path

import pytest


VALIDATORS_DIR = Path(__file__).parent
HOOKS_DIR = VALIDATORS_DIR.parent
PACKAGE_MODULE = f"{VALIDATORS_DIR.name}.run_all_validators"


def run_validators_help() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", PACKAGE_MODULE, "--help"],
        capture_output=True,
        text=True,
        cwd=str(HOOKS_DIR),
    )


class TestNewValidatorsIntegration:
    def test_help_exits_cleanly(self) -> None:
        """Verify run_all_validators --help exits with code 0."""
        result = run_validators_help()
        assert result.returncode == 0, result.stderr
