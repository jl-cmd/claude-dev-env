"""Paginated file intake flattens --slurp pages without losing paths."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from split_pr_paginate import fetch_all_pr_changed_files, parse_paginated_files_payload


def test_fetch_all_pr_changed_files_builds_paginated_gh_api_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_captured: list[list[str]] = []

    class _Completed:
        returncode = 0
        stdout = (
            '[[{"filename": "x.py", "additions": 1, "deletions": 0, "sha": "s"}]]'
        )
        stderr = ""

    def _fake_run(all_command: list[str], **_kwargs: object) -> _Completed:
        all_captured.append(list(all_command))
        return _Completed()

    monkeypatch.setattr("split_pr_paginate.subprocess.run", _fake_run)
    all_files = fetch_all_pr_changed_files("jl-cmd", "claude-dev-env", 1)
    assert all_files[0]["path"] == "x.py"
    assert "--paginate" in all_captured[0]
    assert "--slurp" in all_captured[0]


def test_slurp_pages_are_flattened_in_order() -> None:
    raw = json.dumps(
        [
            [{"filename": "a.py", "additions": 1, "deletions": 0, "sha": "1"}],
            [{"filename": "b.py", "additions": 2, "deletions": 1, "sha": "2"}],
        ]
    )
    all_files = parse_paginated_files_payload(raw)
    assert [each["path"] for each in all_files] == ["a.py", "b.py"]
    assert all_files[1]["additions"] == 2


def test_single_page_array_still_parses() -> None:
    raw = json.dumps([{"filename": "only.py", "additions": 3, "deletions": 0}])
    all_files = parse_paginated_files_payload(raw)
    assert len(all_files) == 1
    assert all_files[0]["path"] == "only.py"


def test_rest_filename_preferred_over_internal_path_key() -> None:
    raw = json.dumps(
        [{"filename": "from-api.py", "path": "stale.py", "additions": 1, "deletions": 0}]
    )
    all_files = parse_paginated_files_payload(raw)
    assert all_files[0]["path"] == "from-api.py"
