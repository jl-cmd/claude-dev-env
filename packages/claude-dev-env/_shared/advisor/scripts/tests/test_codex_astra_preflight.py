"""Tests for the Codex Astra account preflight."""

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_ROOT / "config"))
sys.path.insert(0, str(SCRIPTS_ROOT))

from codex_astra_preflight import run_astra_preflight


def test_run_astra_preflight_rejects_picker_failure(tmp_path: Path) -> None:
    picker_path = tmp_path / "codex_account_choice.py"

    def process_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 1, json.dumps({}), "")

    preflight = run_astra_preflight(picker_path, process_runner)

    assert not preflight.eligible
    assert preflight.fallback_kind == "broken"
