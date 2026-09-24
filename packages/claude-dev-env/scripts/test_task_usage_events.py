"""Check vendor rate parsing through the task report command."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).with_name("task_usage_report.py")


def test_rejects_rates_missing_a_token_category() -> None:
    all_events = [
        {"type": "thread.started", "thread_id": "thread-1"},
        {"type": "turn.completed", "model": "gpt-x", "usage": {"input_tokens": 1}},
    ]
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "run",
            "--task-id",
            "task-1",
            "--run-id",
            "run-1",
            "--repository",
            "team/project",
            "--outcome",
            "pass",
            "--source-format",
            "codex-json",
            "--rate",
            "gpt-x=1,2,3",
            "--rate-source",
            "vendor-price-card",
            "--rate-effective-date",
            "2026-09-24",
        ],
        input="\n".join(map(json.dumps, all_events)),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "rate needs four prices per million tokens" in completed.stderr
