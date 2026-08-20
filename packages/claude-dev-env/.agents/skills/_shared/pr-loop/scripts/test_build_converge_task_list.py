"""Tests for build_converge_task_list — runnable gates and final CLEAN task."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build_converge_task_list as task_list_module  # noqa: E402
from skills_pr_loop_constants.converge_task_list_constants import (  # noqa: E402
    EXIT_SUCCESS,
    RESULT_KEY_DONE_WHEN,
    RESULT_KEY_FINAL_TASK_ID,
    RESULT_KEY_RUNNABLE_REVIEW_IDS,
    RESULT_KEY_SKIPPED_REVIEW_IDS,
    RESULT_KEY_TASKS,
    SKIP_REASON_BUGBOT_DOWN,
    SKIP_REASON_CODEX_NOT_REQUIRED,
    SKIP_REASON_COPILOT_DOWN,
    TASK_FIELD_ID,
    TASK_FIELD_IS_RUNNABLE,
    TASK_FIELD_KIND,
    TASK_ID_ALL_CLEAN_SAME_HEAD,
    TASK_ID_BUGBOT,
    TASK_ID_BUGTEAM,
    TASK_ID_CODE_REVIEW,
    TASK_ID_CODEX,
    TASK_ID_COPILOT,
    TASK_KIND_FINAL,
    TASK_KIND_REVIEW,
)

SCRIPT_PATH = _SCRIPTS_DIR / "build_converge_task_list.py"


def test_default_flags_code_review_and_bugteam_runnable_final_last() -> None:
    payload = task_list_module.build_converge_task_list(
        is_bugbot_down=False,
        is_copilot_down=False,
        is_codex_down=False,
        is_codex_required=False,
    )
    all_tasks = payload[RESULT_KEY_TASKS]
    assert isinstance(all_tasks, list)
    assert all_tasks[0][TASK_FIELD_ID] == TASK_ID_CODE_REVIEW
    assert all_tasks[1][TASK_FIELD_ID] == TASK_ID_BUGTEAM
    assert all_tasks[-1][TASK_FIELD_ID] == TASK_ID_ALL_CLEAN_SAME_HEAD
    assert all_tasks[-1][TASK_FIELD_KIND] == TASK_KIND_FINAL
    assert payload[RESULT_KEY_FINAL_TASK_ID] == TASK_ID_ALL_CLEAN_SAME_HEAD
    assert TASK_ID_CODE_REVIEW in payload[RESULT_KEY_RUNNABLE_REVIEW_IDS]
    assert TASK_ID_BUGTEAM in payload[RESULT_KEY_RUNNABLE_REVIEW_IDS]
    assert TASK_ID_BUGBOT in payload[RESULT_KEY_RUNNABLE_REVIEW_IDS]
    assert TASK_ID_COPILOT in payload[RESULT_KEY_RUNNABLE_REVIEW_IDS]
    assert TASK_ID_CODEX in payload[RESULT_KEY_SKIPPED_REVIEW_IDS]


def test_down_flags_skip_external_reviews() -> None:
    payload = task_list_module.build_converge_task_list(
        is_bugbot_down=True,
        is_copilot_down=True,
        is_codex_down=True,
        is_codex_required=True,
    )
    all_tasks = payload[RESULT_KEY_TASKS]
    assert isinstance(all_tasks, list)
    all_tasks_by_id = {
        each_task[TASK_FIELD_ID]: each_task for each_task in all_tasks
    }
    assert all_tasks_by_id[TASK_ID_BUGBOT][TASK_FIELD_IS_RUNNABLE] is False
    assert all_tasks_by_id[TASK_ID_COPILOT][TASK_FIELD_IS_RUNNABLE] is False
    assert all_tasks_by_id[TASK_ID_CODEX][TASK_FIELD_IS_RUNNABLE] is False
    assert payload[RESULT_KEY_RUNNABLE_REVIEW_IDS] == [
        TASK_ID_CODE_REVIEW,
        TASK_ID_BUGTEAM,
    ]
    assert SKIP_REASON_BUGBOT_DOWN in str(all_tasks_by_id[TASK_ID_BUGBOT])
    assert SKIP_REASON_COPILOT_DOWN in str(all_tasks_by_id[TASK_ID_COPILOT])


def test_codex_required_is_runnable() -> None:
    payload = task_list_module.build_converge_task_list(
        is_bugbot_down=True,
        is_copilot_down=True,
        is_codex_down=False,
        is_codex_required=True,
    )
    assert TASK_ID_CODEX in payload[RESULT_KEY_RUNNABLE_REVIEW_IDS]
    assert SKIP_REASON_CODEX_NOT_REQUIRED not in str(payload)


def test_final_task_always_last_and_runnable() -> None:
    payload = task_list_module.build_converge_task_list(
        is_bugbot_down=True,
        is_copilot_down=False,
        is_codex_down=False,
        is_codex_required=True,
    )
    all_tasks = payload[RESULT_KEY_TASKS]
    assert isinstance(all_tasks, list)
    final_task = all_tasks[-1]
    assert final_task[TASK_FIELD_ID] == TASK_ID_ALL_CLEAN_SAME_HEAD
    assert final_task[TASK_FIELD_IS_RUNNABLE] is True
    assert final_task[TASK_FIELD_KIND] == TASK_KIND_FINAL
    assert payload[RESULT_KEY_DONE_WHEN]


def test_cli_prints_json() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--bugbot-down",
            "1",
            "--copilot-down",
            "0",
            "--codex-required",
            "0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == EXIT_SUCCESS, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload[RESULT_KEY_FINAL_TASK_ID] == TASK_ID_ALL_CLEAN_SAME_HEAD
    assert TASK_ID_BUGBOT in payload[RESULT_KEY_SKIPPED_REVIEW_IDS]
    assert any(
        each_task[TASK_FIELD_KIND] == TASK_KIND_REVIEW
        for each_task in payload[RESULT_KEY_TASKS]
    )


def test_main_returns_usage_on_bad_bool() -> None:
    exit_code = task_list_module.main(["--bugbot-down", "maybe"])
    assert exit_code == task_list_module.EXIT_USAGE_ERROR
