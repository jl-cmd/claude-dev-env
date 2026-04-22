from __future__ import annotations

import sys
from pathlib import Path


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))
sys.modules.pop("config", None)

import config


def test_pre_push_gate_script_not_found_message_contains_path_placeholder() -> None:
    assert "{path}" in config.PRE_PUSH_GATE_SCRIPT_NOT_FOUND_MESSAGE


def test_no_parseable_stdin_lines_message_exists_and_describes_problem() -> None:
    assert "no parseable stdin lines" in config.NO_PARSEABLE_STDIN_LINES_MESSAGE


def test_no_parseable_stdin_lines_sentinel_is_distinct_sentinel_value() -> None:
    assert config.NO_PARSEABLE_STDIN_LINES_SENTINEL is not None
    assert config.NO_PARSEABLE_STDIN_LINES_SENTINEL != config.DEFAULT_REMOTE_BASE_REFERENCE
