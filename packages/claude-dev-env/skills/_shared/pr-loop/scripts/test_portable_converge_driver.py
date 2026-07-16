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
    BUGBOT_INLINE_LAG_WAIT_SECONDS,
    COPILOT_WAIT_HARD_CAP,
    DEFAULT_WAIT_SECONDS,
    EXIT_CONTRACT_ERROR,
    EXIT_SUCCESS,
    EXIT_USAGE_ERROR,
    INLINE_LAG_STREAK_CAP,
    NEXT_APPLY_FIXES,
    NEXT_CHECK_READY,
    NEXT_MARK_READY,
    NEXT_POLL_WAIT,
    NEXT_RUN_BUGTEAM,
    NEXT_RUN_BUGBOT_GATE,
    NEXT_RUN_CODE_REVIEW,
    NEXT_RUN_CODEX,
    NEXT_STOP_BLOCKED,
    PHASE_BLOCKED,
    PHASE_BUGTEAM,
    PHASE_BUGBOT,
    PHASE_CODE_REVIEW,
    PHASE_COPILOT_WAIT,
    PHASE_READY,
    RESULT_KEY_BLOCKER,
    RESULT_KEY_NEXT,
    RESULT_KEY_PACER,
    RESULT_KEY_PHASE,
    RESULT_KEY_STATUS,
    RESULT_KEY_WAIT_SECONDS,
    SERVED_COMMAND_IN_SESSION,
    STATE_KEY_CODEX_CLEAN_AT,
    STATE_KEY_CODEX_DOWN,
    STATE_KEY_CODEX_REQUIRED,
    STATE_KEY_PENDING_NEXT,
    STATE_KEY_PENDING_WAIT_SECONDS,
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
        is_codex_down=True,
        is_codex_required=False,
        owner="owner",
        repo="repo",
        pr_number=220,
        session_model="third-party",
        cwd_path=str(tmp_path / "worktree"),
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
    joined = " ".join(str(each_token) for each_token in all_commands)
    assert "check_convergence.py" in joined
    assert "--codex-down" in joined


def test_after_bugteam_pushed_resets_to_code_review(state_file: Path) -> None:
    state = driver.load_state(state_file)
    state["code_review_clean_at"] = "old"
    state["bugteam_clean_at"] = "old"
    state["bugbot_down"] = True
    state["copilot_down"] = True
    state[STATE_KEY_CODEX_DOWN] = True
    state[STATE_KEY_CODEX_CLEAN_AT] = "old"
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
    assert reloaded[STATE_KEY_CODEX_DOWN] is False
    assert reloaded[STATE_KEY_CODEX_CLEAN_AT] is None
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


def test_after_copilot_surfaced_clean_checks_ready(state_file: Path) -> None:
    state = driver.load_state(state_file)
    state["copilot_down"] = False
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_copilot_wait(
        state_file=state_file,
        is_review_surfaced=True,
        classification="clean",
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_CHECK_READY
    assert payload[RESULT_KEY_PHASE] == PHASE_READY
    reloaded = driver.load_state(state_file)
    assert reloaded["copilot_clean_at"] == "abc123"


def test_after_copilot_surfaced_absent_keeps_waiting(state_file: Path) -> None:
    state = driver.load_state(state_file)
    state["copilot_down"] = False
    state["copilot_wait_count"] = 0
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_copilot_wait(
        state_file=state_file,
        is_review_surfaced=True,
        classification="absent",
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_POLL_WAIT
    assert payload[RESULT_KEY_PHASE] == PHASE_COPILOT_WAIT
    reloaded = driver.load_state(state_file)
    assert reloaded["copilot_clean_at"] is None
    assert reloaded["copilot_wait_count"] == 1


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
    reloaded = driver.load_state(state_file)
    assert reloaded[STATE_KEY_PENDING_NEXT] == NEXT_MARK_READY


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


def test_open_run_portable_seeds_state_and_code_review_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        driver, "_run_preflight", lambda **_kwargs: (None, EXIT_SUCCESS)
    )
    monkeypatch.setattr(
        driver, "_read_git_head", lambda _cwd: ("deadbeef", None, EXIT_SUCCESS)
    )
    state_dir = tmp_path / "state"
    payload, exit_code = driver.run_open_run(
        entry_skill="autoconverge",
        has_workflow=False,
        has_schedule_wakeup=False,
        owner="owner",
        repo="repo",
        pr_number=220,
        cwd_path=tmp_path / "worktree",
        state_dir=state_dir,
        session_model="third-party",
        is_copilot_down=False,
        is_bugbot_down=False,
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_STATUS] == STATUS_OK
    assert payload[RESULT_KEY_NEXT] == NEXT_RUN_CODE_REVIEW
    assert payload[RESULT_KEY_PHASE] == PHASE_CODE_REVIEW
    all_commands = payload["commands"]
    assert isinstance(all_commands, list)
    assert all_commands[0] == "python"
    assert "tasks" in payload
    reloaded = driver.load_state(state_dir / "pr-converge-state.json")
    assert reloaded[STATE_KEY_PENDING_NEXT] == NEXT_RUN_CODE_REVIEW
    assert reloaded["current_head"] == "deadbeef"


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
    assert payload[RESULT_KEY_WAIT_SECONDS] == BUGBOT_INLINE_LAG_WAIT_SECONDS
    reloaded = driver.load_state(state_file)
    assert reloaded["inline_lag_streak"] == 1
    assert reloaded[STATE_KEY_PENDING_WAIT_SECONDS] == BUGBOT_INLINE_LAG_WAIT_SECONDS


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


def test_after_copilot_clean_stamps_and_checks_ready(state_file: Path) -> None:
    state = driver.load_state(state_file)
    state["copilot_down"] = False
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_copilot_wait(
        state_file=state_file,
        is_review_surfaced=True,
        classification="clean",
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_CHECK_READY
    assert payload[RESULT_KEY_PHASE] == PHASE_READY
    reloaded = driver.load_state(state_file)
    assert reloaded["copilot_clean_at"] == "abc123"


def test_after_copilot_absent_when_surfaced_polls_without_stamp(
    state_file: Path,
) -> None:
    state = driver.load_state(state_file)
    state["copilot_down"] = False
    state["copilot_wait_count"] = 0
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_copilot_wait(
        state_file=state_file,
        is_review_surfaced=True,
        classification="absent",
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_POLL_WAIT
    reloaded = driver.load_state(state_file)
    assert reloaded["copilot_clean_at"] is None
    assert reloaded["copilot_wait_count"] == 1


def test_after_copilot_unknown_classification_rejects(
    state_file: Path,
) -> None:
    state = driver.load_state(state_file)
    state["copilot_down"] = False
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_copilot_wait(
        state_file=state_file,
        is_review_surfaced=True,
        classification="mystery",
        current_head="abc123",
    )
    assert exit_code == EXIT_USAGE_ERROR
    assert payload[RESULT_KEY_STATUS] == STATUS_ERROR
    reloaded = driver.load_state(state_file)
    assert reloaded["copilot_clean_at"] is None


def test_after_copilot_down_advances_without_clean_stamp(
    state_file: Path,
) -> None:
    state = driver.load_state(state_file)
    state["copilot_down"] = False
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_copilot_wait(
        state_file=state_file,
        is_review_surfaced=True,
        classification="down",
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_CHECK_READY
    reloaded = driver.load_state(state_file)
    assert reloaded["copilot_down"] is True
    assert reloaded["copilot_clean_at"] is None


def test_after_bugbot_clean_when_codex_required_runs_codex(
    state_file: Path,
) -> None:
    state = driver.load_state(state_file)
    state[STATE_KEY_CODEX_DOWN] = False
    state[STATE_KEY_CODEX_REQUIRED] = True
    state["copilot_down"] = True
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_bugbot(
        state_file=state_file,
        classification="clean",
        current_head="abc123",
        is_inline_lag=False,
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_RUN_CODEX
    assert payload[RESULT_KEY_PHASE] == PHASE_BUGBOT
    reloaded = driver.load_state(state_file)
    assert reloaded["bugbot_clean_at"] == "abc123"
    assert reloaded[STATE_KEY_CODEX_CLEAN_AT] is None


def test_after_codex_clean_advances_to_check_ready(state_file: Path) -> None:
    state = driver.load_state(state_file)
    state[STATE_KEY_CODEX_DOWN] = False
    state[STATE_KEY_CODEX_REQUIRED] = True
    state["copilot_down"] = True
    state["bugbot_down"] = True
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_codex(
        state_file=state_file,
        classification="clean",
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_CHECK_READY
    assert payload[RESULT_KEY_PHASE] == PHASE_READY
    reloaded = driver.load_state(state_file)
    assert reloaded[STATE_KEY_CODEX_CLEAN_AT] == "abc123"
    all_commands = payload["commands"]
    assert isinstance(all_commands, list)
    joined = " ".join(str(each_token) for each_token in all_commands)
    assert "--codex-clean-at" in joined
    assert "abc123" in joined


def test_after_codex_down_waives_and_checks_ready(state_file: Path) -> None:
    state = driver.load_state(state_file)
    state[STATE_KEY_CODEX_DOWN] = False
    state[STATE_KEY_CODEX_REQUIRED] = True
    state["copilot_down"] = True
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_codex(
        state_file=state_file,
        classification="down",
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_CHECK_READY
    reloaded = driver.load_state(state_file)
    assert reloaded[STATE_KEY_CODEX_DOWN] is True
    assert reloaded[STATE_KEY_CODEX_CLEAN_AT] is None
    all_commands = payload["commands"]
    assert isinstance(all_commands, list)
    assert "--codex-down" in " ".join(
        str(each_token) for each_token in all_commands
    )


def test_after_codex_dirty_requests_fixes(state_file: Path) -> None:
    state = driver.load_state(state_file)
    state[STATE_KEY_CODEX_REQUIRED] = True
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_codex(
        state_file=state_file,
        classification="dirty",
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_APPLY_FIXES
    assert payload[RESULT_KEY_PHASE] == PHASE_CODE_REVIEW


def test_after_bugteam_when_codex_required_runs_codex_before_ready(
    state_file: Path,
) -> None:
    state = driver.load_state(state_file)
    state["bugbot_down"] = True
    state["copilot_down"] = True
    state[STATE_KEY_CODEX_DOWN] = False
    state[STATE_KEY_CODEX_REQUIRED] = True
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_bugteam(
        state_file=state_file,
        is_pushed=False,
        is_converged=True,
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_RUN_CODEX
    assert payload[RESULT_KEY_PHASE] == PHASE_BUGBOT


def test_show_state_ready_with_pending_mark_ready(state_file: Path) -> None:
    driver.run_after_ready_check(
        state_file=state_file,
        check_exit=0,
        current_head="abc123",
    )
    exit_code = driver.main(
        ["show-state", "--state-file", str(state_file)]
    )
    assert exit_code == EXIT_SUCCESS
    reloaded = driver.load_state(state_file)
    assert reloaded["phase"] == PHASE_READY
    assert reloaded[STATE_KEY_PENDING_NEXT] == NEXT_MARK_READY
    payload, show_exit = driver._dispatch_show_state(  # noqa: SLF001
        type(
            "Namespace",
            (),
            {"state_file": str(state_file)},
        )()
    )
    assert show_exit == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_MARK_READY
    all_commands = payload["commands"]
    assert isinstance(all_commands, list)
    assert all_commands[0] == "gh"
    assert "ready" in all_commands


def test_show_state_ready_without_pending_defaults_to_mark_ready(
    state_file: Path,
) -> None:
    state = driver.load_state(state_file)
    state["phase"] = PHASE_READY
    state.pop(STATE_KEY_PENDING_NEXT, None)
    driver.save_state(state_file, state)
    payload, exit_code = driver._dispatch_show_state(  # noqa: SLF001
        type(
            "Namespace",
            (),
            {"state_file": str(state_file)},
        )()
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_MARK_READY


def test_show_state_echoes_pending_check_ready(state_file: Path) -> None:
    driver.run_after_bugteam(
        state_file=state_file,
        is_pushed=False,
        is_converged=True,
        current_head="abc123",
    )
    payload, exit_code = driver._dispatch_show_state(  # noqa: SLF001
        type(
            "Namespace",
            (),
            {"state_file": str(state_file)},
        )()
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_CHECK_READY
    assert payload[RESULT_KEY_PHASE] == PHASE_READY
    joined = _command_joined(payload)
    assert "check_convergence.py" in joined


def _command_joined(payload: dict[str, object]) -> str:
    all_commands = payload["commands"]
    assert isinstance(all_commands, list)
    return " ".join(str(each_token) for each_token in all_commands)


def test_after_code_review_failed_serve_emits_code_review_commands(
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
    joined = _command_joined(payload)
    assert "invoke_code_review.py" in joined
    assert "--session-model" in joined
    assert "third-party" in joined
    all_commands = payload["commands"]
    assert isinstance(all_commands, list)
    assert len(all_commands) > 0


def test_after_bugteam_pushed_emits_code_review_commands(
    state_file: Path,
) -> None:
    payload, exit_code = driver.run_after_bugteam(
        state_file=state_file,
        is_pushed=True,
        is_converged=False,
        current_head="def456",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_RUN_CODE_REVIEW
    joined = _command_joined(payload)
    assert "invoke_code_review.py" in joined
    assert "--session-model" in joined


def test_show_state_rehydrates_code_review_commands(state_file: Path) -> None:
    state = driver.load_state(state_file)
    state[STATE_KEY_PENDING_NEXT] = NEXT_RUN_CODE_REVIEW
    state["phase"] = PHASE_CODE_REVIEW
    driver.save_state(state_file, state)
    payload, exit_code = driver._dispatch_show_state(  # noqa: SLF001
        type(
            "Namespace",
            (),
            {"state_file": str(state_file)},
        )()
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_RUN_CODE_REVIEW
    joined = _command_joined(payload)
    assert "invoke_code_review.py" in joined
    assert "--session-model" in joined
    assert "third-party" in joined


def test_after_code_review_head_change_resets_push_markers(
    state_file: Path,
) -> None:
    state = driver.load_state(state_file)
    state["current_head"] = "abc123"
    state["code_review_clean_at"] = "abc123"
    state["bugbot_clean_at"] = "abc123"
    state["bugteam_clean_at"] = "abc123"
    state["copilot_clean_at"] = "abc123"
    state[STATE_KEY_CODEX_CLEAN_AT] = "abc123"
    state["bugbot_down"] = True
    state[STATE_KEY_CODEX_DOWN] = True
    state["inline_lag_streak"] = 2
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_code_review(
        state_file=state_file,
        returncode=0,
        is_dirty_tree=False,
        served_command="claude.exe",
        current_head="def456",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_RUN_BUGTEAM
    reloaded = driver.load_state(state_file)
    assert reloaded["code_review_clean_at"] == "def456"
    assert reloaded["bugbot_clean_at"] is None
    assert reloaded["bugteam_clean_at"] is None
    assert reloaded["copilot_clean_at"] is None
    assert reloaded[STATE_KEY_CODEX_CLEAN_AT] is None
    assert reloaded["bugbot_down"] is False
    assert reloaded[STATE_KEY_CODEX_DOWN] is False
    assert reloaded["inline_lag_streak"] == 0
    assert reloaded["current_head"] == "def456"


def test_copilot_surfaced_absent_preserves_wait_count_to_cap(
    state_file: Path,
) -> None:
    state = driver.load_state(state_file)
    state["copilot_down"] = False
    state["copilot_wait_count"] = COPILOT_WAIT_HARD_CAP - 1
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_copilot_wait(
        state_file=state_file,
        is_review_surfaced=True,
        classification="absent",
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_STOP_BLOCKED
    assert payload[RESULT_KEY_BLOCKER] == BLOCKER_COPILOT_WAIT_CAP
    reloaded = driver.load_state(state_file)
    assert reloaded["copilot_wait_count"] == COPILOT_WAIT_HARD_CAP


def test_copilot_surfaced_absent_increments_from_two(state_file: Path) -> None:
    state = driver.load_state(state_file)
    state["copilot_down"] = False
    state["copilot_wait_count"] = 2
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_copilot_wait(
        state_file=state_file,
        is_review_surfaced=True,
        classification="absent",
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    reloaded = driver.load_state(state_file)
    assert reloaded["copilot_wait_count"] == 3
    if COPILOT_WAIT_HARD_CAP <= 3:
        assert payload[RESULT_KEY_NEXT] == NEXT_STOP_BLOCKED
    else:
        assert payload[RESULT_KEY_NEXT] == NEXT_POLL_WAIT

def test_show_state_rehydrates_poll_wait_seconds(state_file: Path) -> None:
    state = driver.load_state(state_file)
    state[STATE_KEY_PENDING_NEXT] = NEXT_POLL_WAIT
    state["phase"] = PHASE_COPILOT_WAIT
    driver.save_state(state_file, state)
    payload, exit_code = driver._dispatch_show_state(  # noqa: SLF001
        type(
            "Namespace",
            (),
            {"state_file": str(state_file)},
        )()
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_POLL_WAIT
    assert payload[RESULT_KEY_WAIT_SECONDS] == DEFAULT_WAIT_SECONDS


def test_after_bugbot_inline_lag_show_state_preserves_wait_seconds(
    state_file: Path,
) -> None:
    state = driver.load_state(state_file)
    state["inline_lag_streak"] = 0
    driver.save_state(state_file, state)
    after_payload, after_exit = driver.run_after_bugbot(
        state_file=state_file,
        classification="dirty",
        current_head="abc123",
        is_inline_lag=True,
    )
    assert after_exit == EXIT_SUCCESS
    assert after_payload[RESULT_KEY_WAIT_SECONDS] == BUGBOT_INLINE_LAG_WAIT_SECONDS
    show_payload, show_exit = driver._dispatch_show_state(  # noqa: SLF001
        type(
            "Namespace",
            (),
            {"state_file": str(state_file)},
        )()
    )
    assert show_exit == EXIT_SUCCESS
    assert show_payload[RESULT_KEY_NEXT] == NEXT_POLL_WAIT
    assert show_payload[RESULT_KEY_WAIT_SECONDS] == BUGBOT_INLINE_LAG_WAIT_SECONDS


def test_after_bugteam_head_change_resets_down_flags(state_file: Path) -> None:
    state = driver.load_state(state_file)
    state["current_head"] = "abc123"
    state["code_review_clean_at"] = "abc123"
    state["bugbot_down"] = True
    state[STATE_KEY_CODEX_DOWN] = True
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_bugteam(
        state_file=state_file,
        is_pushed=False,
        is_converged=True,
        current_head="def456",
    )
    assert exit_code == EXIT_SUCCESS
    reloaded = driver.load_state(state_file)
    assert reloaded["bugbot_down"] is False
    assert reloaded[STATE_KEY_CODEX_DOWN] is False
    assert reloaded["code_review_clean_at"] is None
    assert reloaded["current_head"] == "def456"
    assert payload[RESULT_KEY_NEXT] == NEXT_RUN_BUGBOT_GATE


def test_after_ready_check_head_change_resets_markers(state_file: Path) -> None:
    state = driver.load_state(state_file)
    state["current_head"] = "abc123"
    state["code_review_clean_at"] = "abc123"
    state["bugbot_down"] = True
    state[STATE_KEY_CODEX_DOWN] = True
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_ready_check(
        state_file=state_file,
        check_exit=0,
        current_head="def456",
    )
    assert exit_code == EXIT_SUCCESS
    reloaded = driver.load_state(state_file)
    assert reloaded["bugbot_down"] is False
    assert reloaded[STATE_KEY_CODEX_DOWN] is False
    assert reloaded["code_review_clean_at"] is None
    assert reloaded["current_head"] == "def456"
    assert payload[RESULT_KEY_NEXT] == NEXT_MARK_READY


def test_after_codex_dirty_resets_down_flags(state_file: Path) -> None:
    state = driver.load_state(state_file)
    state[STATE_KEY_CODEX_REQUIRED] = True
    state["bugbot_down"] = True
    state[STATE_KEY_CODEX_DOWN] = True
    state["code_review_clean_at"] = "abc123"
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_codex(
        state_file=state_file,
        classification="dirty",
        current_head="abc123",
    )
    assert exit_code == EXIT_SUCCESS
    assert payload[RESULT_KEY_NEXT] == NEXT_APPLY_FIXES
    reloaded = driver.load_state(state_file)
    assert reloaded["bugbot_down"] is False
    assert reloaded[STATE_KEY_CODEX_DOWN] is False
    assert reloaded["code_review_clean_at"] is None


def test_after_bugbot_down_rebuilds_task_list(state_file: Path) -> None:
    state = driver.load_state(state_file)
    state["bugbot_down"] = False
    state["tasks"] = []
    state["runnable_review_ids"] = ["code_review"]
    driver.save_state(state_file, state)
    payload, exit_code = driver.run_after_bugbot(
        state_file=state_file,
        classification="down",
        current_head="abc123",
        is_inline_lag=False,
    )
    assert exit_code == EXIT_SUCCESS
    reloaded = driver.load_state(state_file)
    assert reloaded["bugbot_down"] is True
    all_runnable = reloaded.get("runnable_review_ids")
    assert isinstance(all_runnable, list)
    assert "bugbot" not in all_runnable

