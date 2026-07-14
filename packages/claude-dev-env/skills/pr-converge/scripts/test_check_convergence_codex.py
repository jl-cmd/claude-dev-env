"""Fixture-driven tests for the conditional Codex convergence gate.

Covers: required-and-clean, required-and-dirty, skipped-by-threshold,
skipped-by-token, skipped-by-down. Threshold comes from the probe constant
via ``is_codex_review_required`` — this module never inlines the percent.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

import _pr_converge_path_setup  # noqa: F401
from codex_review_scripts_constants.codex_usage_probe_constants import (
    WEEKLY_USAGE_GATE_THRESHOLD_PERCENT,
)
from pr_converge_scripts_constants.convergence_gate_constants import (
    MINIMUM_ABBREVIATED_SHA_LENGTH,
)

_SCRIPTS_DIRECTORY = Path(__file__).absolute().parent
_PR_CONVERGE_DIRECTORY = _SCRIPTS_DIRECTORY.parent

CLEAN_LABEL = "Clean \u2014 no findings"
CLEAN_BODY = (
    f"**Bugteam audit completed** \u2014 {CLEAN_LABEL}\n\n"
    "No findings.\n"
)
HEAD_SHA = "ae8005aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
OTHER_SHA = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
PERCENT_ABOVE_THRESHOLD = float(WEEKLY_USAGE_GATE_THRESHOLD_PERCENT) + 1.0
PERCENT_AT_THRESHOLD = float(WEEKLY_USAGE_GATE_THRESHOLD_PERCENT)


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
        "check_convergence_codex_under_test", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_convergence = _load_module()


def _write_fixture(
    tmp_path: Path,
    *,
    codex_percent_left: float | None,
    codex_clean_at: str | None,
    filename: str = "codex-gate.json",
) -> Path:
    fixture_path = tmp_path / filename
    payload: dict[str, object] = {
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
        "codex_percent_left": codex_percent_left,
        "codex_clean_at": codex_clean_at,
    }
    fixture_path.write_text(json.dumps(payload), encoding="utf-8")
    return fixture_path


def should_pass_when_codex_required_and_clean(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture_path = _write_fixture(
        tmp_path,
        codex_percent_left=PERCENT_ABOVE_THRESHOLD,
        codex_clean_at=HEAD_SHA,
        filename="required-clean.json",
    )
    exit_code = check_convergence.main(
        [
            "--owner",
            "jl-cmd",
            "--repo",
            "claude-dev-env",
            "--pr-number",
            "111",
            "--fixture",
            str(fixture_path),
            "--bugbot-down",
            "--copilot-down",
        ]
    )
    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "codex_clean_at == current_head: PASS" in captured
    assert "clean at" in captured
    assert "All pre-conditions met" in captured


def should_fail_when_codex_clean_stamp_is_shorter_than_an_abbreviated_sha(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture_path = _write_fixture(
        tmp_path,
        codex_percent_left=PERCENT_ABOVE_THRESHOLD,
        codex_clean_at=HEAD_SHA[:1],
        filename="required-short-stamp.json",
    )
    exit_code = check_convergence.main(
        [
            "--owner",
            "jl-cmd",
            "--repo",
            "claude-dev-env",
            "--pr-number",
            "111",
            "--fixture",
            str(fixture_path),
            "--bugbot-down",
            "--copilot-down",
        ]
    )
    captured = capsys.readouterr().out
    assert exit_code == 1
    assert "codex_clean_at == current_head: FAIL" in captured


def should_pass_when_codex_clean_stamp_is_an_abbreviated_head_sha(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture_path = _write_fixture(
        tmp_path,
        codex_percent_left=PERCENT_ABOVE_THRESHOLD,
        codex_clean_at=HEAD_SHA[:MINIMUM_ABBREVIATED_SHA_LENGTH],
        filename="required-abbreviated-stamp.json",
    )
    exit_code = check_convergence.main(
        [
            "--owner",
            "jl-cmd",
            "--repo",
            "claude-dev-env",
            "--pr-number",
            "111",
            "--fixture",
            str(fixture_path),
            "--bugbot-down",
            "--copilot-down",
        ]
    )
    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "codex_clean_at == current_head: PASS" in captured


def should_fail_when_codex_required_and_dirty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture_path = _write_fixture(
        tmp_path,
        codex_percent_left=PERCENT_ABOVE_THRESHOLD,
        codex_clean_at=OTHER_SHA,
        filename="required-dirty.json",
    )
    exit_code = check_convergence.main(
        [
            "--owner",
            "jl-cmd",
            "--repo",
            "claude-dev-env",
            "--pr-number",
            "111",
            "--fixture",
            str(fixture_path),
            "--bugbot-down",
            "--copilot-down",
        ]
    )
    captured = capsys.readouterr().out
    assert exit_code == 1
    assert "codex_clean_at == current_head: FAIL" in captured
    assert "no codex clean on" in captured
    assert "do not mark ready" in captured


def should_skip_when_usage_at_or_below_threshold(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture_path = _write_fixture(
        tmp_path,
        codex_percent_left=PERCENT_AT_THRESHOLD,
        codex_clean_at=None,
        filename="skipped-threshold.json",
    )
    exit_code = check_convergence.main(
        [
            "--owner",
            "jl-cmd",
            "--repo",
            "claude-dev-env",
            "--pr-number",
            "111",
            "--fixture",
            str(fixture_path),
            "--bugbot-down",
            "--copilot-down",
        ]
    )
    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "codex_clean_at == current_head: PASS" in captured
    assert "skipped (codex review not required)" in captured


def should_skip_when_codex_percent_left_is_null(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture_path = _write_fixture(
        tmp_path,
        codex_percent_left=None,
        codex_clean_at=None,
        filename="skipped-null.json",
    )
    exit_code = check_convergence.main(
        [
            "--owner",
            "jl-cmd",
            "--repo",
            "claude-dev-env",
            "--pr-number",
            "111",
            "--fixture",
            str(fixture_path),
            "--bugbot-down",
            "--copilot-down",
        ]
    )
    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "skipped (codex review not required)" in captured


def should_bypass_when_codex_token_disables_reviewer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "codex")
    fixture_path = _write_fixture(
        tmp_path,
        codex_percent_left=PERCENT_ABOVE_THRESHOLD,
        codex_clean_at=None,
        filename="skipped-token.json",
    )
    exit_code = check_convergence.main(
        [
            "--owner",
            "jl-cmd",
            "--repo",
            "claude-dev-env",
            "--pr-number",
            "111",
            "--fixture",
            str(fixture_path),
            "--bugbot-down",
            "--copilot-down",
        ]
    )
    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "bypassed (codex_down)" in captured
    assert "no codex clean on" not in captured


def should_bypass_when_codex_down_flag_set(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture_path = _write_fixture(
        tmp_path,
        codex_percent_left=PERCENT_ABOVE_THRESHOLD,
        codex_clean_at=None,
        filename="skipped-down.json",
    )
    exit_code = check_convergence.main(
        [
            "--owner",
            "jl-cmd",
            "--repo",
            "claude-dev-env",
            "--pr-number",
            "111",
            "--fixture",
            str(fixture_path),
            "--bugbot-down",
            "--copilot-down",
            "--codex-down",
        ]
    )
    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "bypassed (codex_down)" in captured


def should_resolve_codex_down_true_when_flag_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    monkeypatch.delenv("CLAUDE_JOB_DIR", raising=False)
    assert check_convergence._resolve_codex_down(True) is True


def should_resolve_codex_down_true_when_env_disables_codex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLAUDE_JOB_DIR", raising=False)
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "codex")
    assert check_convergence._resolve_codex_down(False) is True


def should_resolve_codex_down_false_when_flag_unset_and_env_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    monkeypatch.delenv("CLAUDE_JOB_DIR", raising=False)
    assert check_convergence._resolve_codex_down(False) is False


def should_resolve_codex_down_true_when_job_state_sticky_down(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(tmp_path))
    (tmp_path / "pr-converge-state.json").write_text(
        json.dumps({"codex_down": True}),
        encoding="utf-8",
    )
    assert check_convergence._resolve_codex_down(False) is True


def should_resolve_codex_down_false_when_job_state_codex_down_is_false(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(tmp_path))
    (tmp_path / "pr-converge-state.json").write_text(
        json.dumps({"codex_down": False}),
        encoding="utf-8",
    )
    assert check_convergence._resolve_codex_down(False) is False


def should_bypass_when_job_state_codex_down_is_true(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(tmp_path))
    (tmp_path / "pr-converge-state.json").write_text(
        json.dumps({"codex_down": True}),
        encoding="utf-8",
    )
    fixture_path = _write_fixture(
        tmp_path,
        codex_percent_left=PERCENT_ABOVE_THRESHOLD,
        codex_clean_at=None,
        filename="job-state-codex-down.json",
    )
    exit_code = check_convergence.main(
        [
            "--owner",
            "jl-cmd",
            "--repo",
            "claude-dev-env",
            "--pr-number",
            "111",
            "--fixture",
            str(fixture_path),
            "--bugbot-down",
            "--copilot-down",
        ]
    )
    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "bypassed (codex_down)" in captured
    assert "no codex clean on" not in captured


def should_fail_when_job_state_lacks_codex_down_and_clean_stamp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    monkeypatch.setenv("CLAUDE_JOB_DIR", str(tmp_path))
    (tmp_path / "pr-converge-state.json").write_text(
        json.dumps({}),
        encoding="utf-8",
    )
    fixture_path = _write_fixture(
        tmp_path,
        codex_percent_left=PERCENT_ABOVE_THRESHOLD,
        codex_clean_at=None,
        filename="job-state-no-down.json",
    )
    exit_code = check_convergence.main(
        [
            "--owner",
            "jl-cmd",
            "--repo",
            "claude-dev-env",
            "--pr-number",
            "111",
            "--fixture",
            str(fixture_path),
            "--bugbot-down",
            "--copilot-down",
        ]
    )
    captured = capsys.readouterr().out
    assert exit_code == 1
    assert "codex_clean_at == current_head: FAIL" in captured
    assert "no codex clean on" in captured


def should_accept_codex_down_flag_in_parsed_arguments() -> None:
    arguments = check_convergence.parse_arguments(
        ["--owner", "o", "--repo", "r", "--pr-number", "1", "--codex-down"]
    )
    assert arguments.codex_down is True


def should_accept_codex_clean_at_flag_in_parsed_arguments() -> None:
    arguments = check_convergence.parse_arguments(
        [
            "--owner",
            "o",
            "--repo",
            "r",
            "--pr-number",
            "1",
            "--codex-clean-at",
            HEAD_SHA,
        ]
    )
    assert arguments.codex_clean_at == HEAD_SHA
