"""Tests for Codex Astra usage preflight."""

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_ROOT / "config"))
sys.path.insert(0, str(SCRIPTS_ROOT))

from codex_astra_preflight import run_astra_preflight


def test_run_astra_preflight_rejects_probe_failure(tmp_path: Path) -> None:
    probe_path = tmp_path / "codex_usage_probe.py"

    def process_runner(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 1, json.dumps({}), "")

    preflight = run_astra_preflight(probe_path, process_runner)

    assert not preflight.eligible
    assert preflight.fallback_kind == "broken"
