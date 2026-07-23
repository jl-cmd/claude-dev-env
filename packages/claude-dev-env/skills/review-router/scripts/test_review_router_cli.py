"""CLI production-path acceptance tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import pytest

from review_router_cli import arm, close

CLI = Path(__file__).with_name("review_router_cli.py")


def test_public_arm_and_close_reject_missing_signed_state(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        arm(str(tmp_path), "missing", "slot")
    with pytest.raises(OSError):
        close(str(tmp_path), "missing")


def test_cli_rejects_requested_dispatch(tmp_path: Path) -> None:
    command_result = subprocess.run(
        [sys.executable, str(CLI), "next", "--cwd", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert command_result.returncode != 0
    assert "invalid choice" in command_result.stderr


@pytest.mark.parametrize("arguments", ["--tier 4", "--tier", "--tier x", "--tier 1 --tier 2"])
def test_malformed_tier_override_writes_no_artifacts(tmp_path: Path, arguments: str) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    environment = {**os.environ, "CLAUDE_PLUGIN_DATA": str(tmp_path / "data")}
    command_result = subprocess.run([sys.executable, str(CLI), "resolve", "--cwd", str(repository), "--arguments", arguments], capture_output=True, text=True, env=environment)
    assert command_result.returncode != 0
    assert not (tmp_path / "data").exists()
