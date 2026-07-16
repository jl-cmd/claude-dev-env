"""Tests for portable_converge_driver — deterministic phase machine only."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import portable_converge_driver as driver  # noqa: E402
from skills_pr_loop_constants.portable_driver_constants import (  # noqa: E402
    BLOCKER_COPILOT_WAIT_CAP,
    BLOCKER_INLINE_LAG_CAP,
    BLOCKER_NOT_PORTABLE,
    COPILOT_WAIT_HARD_CAP,
    DEFAULT_WAIT_SECONDS,
    EXIT_CONTRACT_ERROR,
    EXIT_SUCCESS,
    INLINE_LAG_STREAK_CAP,
    NEXT_APPLY_FIXES,
    NEXT_CHECK_READY,
    NEXT_MARK_READY,
    NEXT_POLL_WAIT,
    NEXT_RUN_BUGTEAM,
    NEXT_RUN_CODE_REVIEW,
    NEXT_STOP_BLOCKED,
    PHASE_BLOCKED,
    PHASE_BUGTEAM,
    PHASE_BUGBOT,
    PHASE_CODE_REVIEW,
    PHASE_READY,
    RESULT_KEY_BLOCKER,
    RESULT_KEY_NEXT,
    RESULT_KEY_PACER,
    RESULT_KEY_PHASE,
    RESULT_KEY_STATUS,
    RESULT_KEY_WAIT_SECONDS,
    SERVED_COMMAND_IN_SESSION,
    STATUS_ERROR,
    STATUS_OK,
)


@pytest.fixture
def state_file(tmp_path: Path) -> Path:
    path = tmp_path / "pr-converge-state.json"
    state = driver.build_initial_state(
        current_head="abc123",
        entry_skill="autoconverge",
        is_copilot_down=True,
        is_bugbot_down=True,
        owner="owner",
        repo="repo",
        pr_number=220,
    )
    driver.save_state(path, state)
    return path


def test_after_code_review_clean_advances_to_bugteam(state_file: Path) -> None:
    payload, exit_code = driver.run_after_code_review(
        state_file=state_file,
        returncode=0,
        is_dirty_tree=False,
        served_command="claude.exe",
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_STATUS] == STATUS_OK
    assert payload[RESULT_KEY_NEXT] == NEXT_RUN_BUGTEAM
    assert payload[RESULT_KEY_PHASE] == PHASE_BUGTEAM
    reloaded = driver.load_state(state_file)
    assert reloaded["code_review_clean_at"] == "abc123"


def test_after_code_review_dirty_tree_requests_fixes(state_file: Path) -> None:
    payload, exit_code = driver.run_after_code_review(
        state_file=state_file,
        returncode=0,
        is_dirty_tree=True,
        served_command="claude.exe",
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_APPLY_FIXES
    assert payload[RESULT_KEY_PHASE] == PHASE_CODE_REVIEW


def test_after_code_review_failed_serve_stays_code_review(
    state_file: Path,
) -> None:
    payload, exit_code = driver.run_after_code_review(
        state_file=state_file,
        returncode=1,
        is_dirty_tree=False,
        served_command="",
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_RUN_CODE_REVIEW
    assert payload[RESULT_KEY_BLOCKER] == "code_review_failed"


def test_after_bugteam_converged_with_down_gates_checks_ready(
    state_file: Path,
) -> None:
    payload, exit_code = driver.run_after_bugteam(
        state_file=state_file,
        is_pushed=False,
        is_converged=True,
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_CHECK_READY
    assert payload[RESULT_KEY_PHASE] == PHASE_READY
    all_commands = payload["commands"]
    assert isinstance(all_commands, list)
    assert "check_convergence.py" in " ".join(
        str(each_token) for each_token in all_commands
    )


def test_after_bugteam_pushed_resets_to_code_review(state_file: Path) -> None:
    state = driver.load_state(state_file)
    state["code_review_clean_at"] = "old"
    state["bugteam_clean_at"] = "old"
    state["bugbot_down"] = True
    state["copilot_down"] = True
    state["inline_lag_streak"] = 2
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_bugteam(
        state_file=state_file,
        is_pushed=True,
        is_converged=False,
        current_head="def456",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_RUN_CODE_REVIEW
    reloaded = driver.load_state(state_file)
    assert reloaded["code_review_clean_at"] is None
    assert reloaded["current_head"] == "def456"
    assert reloaded["bugbot_down"] is False
    assert reloaded["copilot_down"] is True
    assert reloaded["inline_lag_streak"] == 0


def test_after_bugbot_clean_with_down_gates_checks_ready(
    state_file: Path,
) -> None:
    payload, exit_code = driver.run_after_bugbot(
        state_file=state_file,
        classification="clean",
        current_head="abc123",
        is_inline_lag=False,
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_STATUS] == STATUS_OK
    assert payload[RESULT_KEY_NEXT] == NEXT_CHECK_READY
    assert payload[RESULT_KEY_PHASE] == PHASE_READY
    reloaded = driver.load_state(state_file)
    assert reloaded["bugbot_clean_at"] == "abc123"
    all_commands = payload["commands"]
    assert isinstance(all_commands, list)
    assert "check_convergence.py" in " ".join(
        str(each_token) for each_token in all_commands
    )


def test_after_bugbot_dirty_requests_fixes(state_file: Path) -> None:
    payload, exit_code = driver.run_after_bugbot(
        state_file=state_file,
        classification="dirty",
        current_head="abc123",
        is_inline_lag=False,
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_APPLY_FIXES
    assert payload[RESULT_KEY_PHASE] == PHASE_CODE_REVIEW
    reloaded = driver.load_state(state_file)
    assert reloaded["inline_lag_streak"] == 0


def test_copilot_wait_cap_blocks(state_file: Path) -> None:
    state = driver.load_state(state_file)
    state["copilot_down"] = False
    state["copilot_wait_count"] = COPILOT_WAIT_HARD_CAP - 1
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_copilot_wait(
        state_file=state_file,
        is_review_surfaced=False,
        classification="absent",
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_STOP_BLOCKED
    assert payload[RESULT_KEY_BLOCKER] == BLOCKER_COPILOT_WAIT_CAP
    assert payload[RESULT_KEY_PHASE] == PHASE_BLOCKED


def test_copilot_wait_poll_emits_delay(state_file: Path) -> None:
    state = driver.load_state(state_file)
    state["copilot_down"] = False
    state["copilot_wait_count"] = 0
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_copilot_wait(
        state_file=state_file,
        is_review_surfaced=False,
        classification="absent",
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_POLL_WAIT
    assert payload[RESULT_KEY_WAIT_SECONDS] == DEFAULT_WAIT_SECONDS


def test_after_ready_check_zero_marks_ready(state_file: Path) -> None:
    payload, exit_code = driver.run_after_ready_check(
        state_file=state_file,
        check_exit=0,
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_MARK_READY
    all_commands = payload["commands"]
    assert isinstance(all_commands, list)
    assert all_commands[0] == "gh"


def test_open_run_rejects_non_portable_pacer(tmp_path: Path) -> None:
    payload, exit_code = driver.run_open_run(
        entry_skill="autoconverge",
        has_workflow=True,
        has_schedule_wakeup=False,
        owner="owner",
        repo="repo",
        pr_number=1,
        cwd_path=tmp_path,
        state_dir=tmp_path / "state",
        session_model="third-party",
        is_copilot_down=True,
        is_bugbot_down=True,
    )
    assert exit_code == EXIT_CONTRACT_ERROR
    assert payload[RESULT_KEY_STATUS] == STATUS_ERROR
    assert payload[RESULT_KEY_BLOCKER] == BLOCKER_NOT_PORTABLE
    assert payload[RESULT_KEY_PACER] == "workflow"


def test_main_after_code_review_cli(state_file: Path) -> None:
    exit_code = driver.main(
        [
            "after-code-review",
            "--state-file",
            str(state_file),
            "--returncode",
            "0",
            "--dirty-tree",
            "0",
            "--served-command",
            "claude",
            "--current-head",
            "abc123",
        ]
    )
    assert exit_code == EXIT_SUCCESS


def test_after_code_review_empty_served_command_is_successful(
    state_file: Path,
) -> None:
    payload, exit_code = driver.run_after_code_review(
        state_file=state_file,
        returncode=0,
        is_dirty_tree=False,
        served_command="",
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_STATUS] == STATUS_OK
    assert payload[RESULT_KEY_NEXT] == NEXT_RUN_BUGTEAM
    assert payload[RESULT_KEY_PHASE] == PHASE_BUGTEAM
    reloaded = driver.load_state(state_file)
    assert reloaded["code_review_clean_at"] == "abc123"


def test_after_code_review_in_session_token_is_successful(
    state_file: Path,
) -> None:
    payload, exit_code = driver.run_after_code_review(
        state_file=state_file,
        returncode=0,
        is_dirty_tree=False,
        served_command=SERVED_COMMAND_IN_SESSION,
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_RUN_BUGTEAM


def test_after_bugbot_inline_lag_polls_under_cap(state_file: Path) -> None:
    state = driver.load_state(state_file)
    state["inline_lag_streak"] = 0
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_bugbot(
        state_file=state_file,
        classification="dirty",
        current_head="abc123",
        is_inline_lag=True,
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_POLL_WAIT
    assert payload[RESULT_KEY_PHASE] == PHASE_BUGBOT
    reloaded = driver.load_state(state_file)
    assert reloaded["inline_lag_streak"] == 1


def test_after_bugbot_inline_lag_cap_blocks(state_file: Path) -> None:
    state = driver.load_state(state_file)
    state["inline_lag_streak"] = INLINE_LAG_STREAK_CAP - 1
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_bugbot(
        state_file=state_file,
        classification="dirty",
        current_head="abc123",
        is_inline_lag=True,
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_STOP_BLOCKED
    assert payload[RESULT_KEY_BLOCKER] == BLOCKER_INLINE_LAG_CAP
    assert payload[RESULT_KEY_PHASE] == PHASE_BLOCKED
    reloaded = driver.load_state(state_file)
    assert reloaded["inline_lag_streak"] == INLINE_LAG_STREAK_CAP

