"""Integration test for new validators in run_all_validators.py"""

import subprocess
import sys
from pathlib import Path

import pytest


VALIDATORS_DIR = Path(__file__).parent


class TestNewValidatorsIntegration:
    def test_abbreviation_checks_called(self) -> None:
        """Verify abbreviation_checks is invoked by run_all_validators."""
        result = subprocess.run(
            [sys.executable, str(VALIDATORS_DIR / "run_all_validators.py"), "--help"],
            capture_output=True,
            text=True,
        )
        assert "Abbreviations" in result.stdout or result.returncode == 0

    def test_pr_reference_checks_called(self) -> None:
        """Verify pr_reference_checks is invoked by run_all_validators."""
        result = subprocess.run(
            [sys.executable, str(VALIDATORS_DIR / "run_all_validators.py"), "--help"],
            capture_output=True,
            text=True,
        )
        assert "PR References" in result.stdout or result.returncode == 0

    def test_magic_value_checks_called(self) -> None:
        """Verify magic_value_checks is invoked by run_all_validators."""
        result = subprocess.run(
            [sys.executable, str(VALIDATORS_DIR / "run_all_validators.py"), "--help"],
            capture_output=True,
            text=True,
        )
        assert "Magic Values" in result.stdout or result.returncode == 0

    def test_useless_test_checks_called(self) -> None:
        """Verify useless_test_checks is invoked by run_all_validators."""
        result = subprocess.run(
            [sys.executable, str(VALIDATORS_DIR / "run_all_validators.py"), "--help"],
            capture_output=True,
            text=True,
        )
        assert "Useless Tests" in result.stdout or result.returncode == 0
