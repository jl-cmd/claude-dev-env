from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


_BLOCKING_DIRECTORY = Path(__file__).resolve().parent
_ENTRYPOINT_PATH = _BLOCKING_DIRECTORY / "content_search_to_zoekt_redirector.py"
_HOOKS_MANIFEST_PATH = _BLOCKING_DIRECTORY.parent / "hooks.json"


def test_retired_entrypoint_allows_valid_search_events_silently() -> None:
    all_search_events = (
        {"tool_name": "Bash", "tool_input": {"command": "rg --files packages"}},
        {
            "tool_name": "Grep",
            "tool_input": {"pattern": "zoekt", "path": "packages"},
        },
        {
            "tool_name": "Search",
            "tool_input": {"pattern": "zoekt", "path": "packages"},
        },
    )

    for each_search_event in all_search_events:
        completed_process = subprocess.run(
            [sys.executable, str(_ENTRYPOINT_PATH)],
            check=False,
            input=json.dumps(each_search_event),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert completed_process.returncode == 0
        assert completed_process.stdout == ""
        assert completed_process.stderr == ""


def test_shipped_hook_manifest_omits_retired_entrypoint() -> None:
    hooks_manifest_text = _HOOKS_MANIFEST_PATH.read_text(encoding="utf-8")

    assert _ENTRYPOINT_PATH.name not in hooks_manifest_text
