"""Fixture-mode tests for check_convergence --fixture replay."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

import _pr_converge_path_setup  # noqa: F401

_SCRIPTS_DIRECTORY = Path(__file__).absolute().parent
_PR_CONVERGE_DIRECTORY = _SCRIPTS_DIRECTORY.parent

CLEAN_LABEL = "Clean \u2014 no findings"
CLEAN_BODY = (
    f"**Bugteam audit completed** \u2014 {CLEAN_LABEL}\n\n"
    "No findings.\n"
)
HEAD_SHA = "ae8005aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def _load_module() -> ModuleType:
    for each_cached_name in [
        each_key
        for each_key in list(sys.modules)
        if each_key == "config" or each_key.startswith("config.")
    ]:
        sys.modules.pop(each_cached_name, None)
    if str(_PR_CONVERGE_DIRECTORY) in sys.path:
        sys.path.remove(str(_PR_CONVERGE_DIRECTORY))
    sys.path.insert(0, str(_PR_CONVERGE_DIRECTORY))
    module_path = _SCRIPTS_DIRECTORY / "check_convergence.py"
    spec = importlib.util.spec_from_file_location(
        "check_convergence_fixture_under_test", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_convergence = _load_module()


def _write_passing_fixture(tmp_path: Path) -> Path:
    fixture_path = tmp_path / "pr-at-merge.json"
    payload = {
        "head_sha": HEAD_SHA,
        "pr_object": {"mergeable": True, "mergeable_state": "clean"},
        "reviews": [
            {
                "id": 1,
                "body": CLEAN_BODY,
                "commit_id": HEAD_SHA,
            }
        ],
        "unresolved_bot_threads_passed": True,
        "unresolved_bot_threads_detail": "0 unresolved",
        "pending_reviews_passed": True,
        "pending_reviews_detail": "none pending",
    }
    fixture_path.write_text(json.dumps(payload), encoding="utf-8")
    return fixture_path


def should_exit_zero_from_fixture_with_bugbot_and_copilot_down(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture_path = _write_passing_fixture(tmp_path)
    exit_code = check_convergence.main(
        [
            "--owner",
            "jl-cmd",
            "--repo",
            "claude-dev-env",
            "--pr-number",
            "53",
            "--fixture",
            str(fixture_path),
            "--bugbot-down",
            "--copilot-down",
        ]
    )
    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "All pre-conditions met" in captured
    assert "bypassed (bugbot_down)" in captured
    assert "bypassed (copilot_down)" in captured
    assert "clean bugteam audit" in captured
    assert "PR is mergeable: PASS" in captured


def should_exit_one_from_fixture_when_bugteam_clean_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture_path = tmp_path / "missing-bugteam.json"
    payload = {
        "head_sha": HEAD_SHA,
        "pr_object": {"mergeable": True, "mergeable_state": "clean"},
        "reviews": [],
        "unresolved_bot_threads_passed": True,
        "unresolved_bot_threads_detail": "0 unresolved",
        "pending_reviews_passed": True,
        "pending_reviews_detail": "none pending",
    }
    fixture_path.write_text(json.dumps(payload), encoding="utf-8")
    exit_code = check_convergence.main(
        [
            "--owner",
            "jl-cmd",
            "--repo",
            "claude-dev-env",
            "--pr-number",
            "80",
            "--fixture",
            str(fixture_path),
            "--bugbot-down",
            "--copilot-down",
        ]
    )
    captured = capsys.readouterr().out
    assert exit_code == 1
    assert "no bugteam review found" in captured
    assert "do not mark ready" in captured


def should_parse_fixture_flag() -> None:
    arguments = check_convergence.parse_arguments(
        [
            "--owner",
            "o",
            "--repo",
            "r",
            "--pr-number",
            "1",
            "--fixture",
            "snap.json",
            "--bugbot-down",
            "--copilot-down",
        ]
    )
    assert arguments.fixture == "snap.json"
    assert arguments.bugbot_down is True
    assert arguments.copilot_down is True


def should_evaluate_bugteam_clean_from_reviews_on_clean_body() -> None:
    head = HEAD_SHA
    passed, detail = check_convergence._evaluate_bugteam_clean_from_reviews(
        [{"id": 9, "body": CLEAN_BODY, "commit_id": head}],
        head,
    )
    assert passed is True
    assert "clean bugteam audit" in detail


def should_load_convergence_fixture_from_disk(tmp_path: Path) -> None:
    fixture_path = _write_passing_fixture(tmp_path)
    fixture = check_convergence._load_convergence_fixture(fixture_path)
    assert fixture.head_sha == HEAD_SHA
    assert fixture.pr_object["mergeable"] is True
    assert len(fixture.reviews) == 1
