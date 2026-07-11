"""Integration test for new validators in run_all_validators.py"""

import subprocess

from .run_all_validators import run_validators_entrypoint_subprocess


def run_validators_help() -> subprocess.CompletedProcess[str]:
    return run_validators_entrypoint_subprocess(["--help"])


class TestNewValidatorsIntegration:
    def test_help_exits_cleanly(self) -> None:
        """Verify run_all_validators --help exits with code 0."""
        result = run_validators_help()
        assert result.returncode == 0, result.stderr
