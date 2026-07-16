"""Tests for select_converge_pacer — host tool surface → pacer mapping."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import select_converge_pacer as pacer_module  # noqa: E402
from skills_pr_loop_constants.pacer_constants import (  # noqa: E402
    CLI_HAS_SCHEDULE_WAKEUP_FLAG,
    CLI_HAS_WORKFLOW_FLAG,
    CLI_SKILL_FLAG,
    ENTRY_SKILL_AUTOCONVERGE,
    ENTRY_SKILL_PR_CONVERGE,
    EXIT_SUCCESS,
    EXIT_USAGE_ERROR,
    PACER_PORTABLE,
    PACER_SCHEDULE_WAKEUP,
    PACER_WORKFLOW,
    RESULT_KEY_ENTRY_SKILL,
    RESULT_KEY_HAS_SCHEDULE_WAKEUP,
    RESULT_KEY_HAS_WORKFLOW,
    RESULT_KEY_PACER,
)

SCRIPT_PATH = _SCRIPTS_DIR / "select_converge_pacer.py"


def test_autoconverge_with_workflow_selects_workflow() -> None:
    selection = pacer_module.select_converge_pacer(
        entry_skill=ENTRY_SKILL_AUTOCONVERGE,
        has_workflow=True,
        has_schedule_wakeup=False,
    )
    assert selection.pacer == PACER_WORKFLOW
    assert selection.entry_skill == ENTRY_SKILL_AUTOCONVERGE


def test_autoconverge_without_workflow_selects_portable() -> None:
    selection = pacer_module.select_converge_pacer(
        entry_skill=ENTRY_SKILL_AUTOCONVERGE,
        has_workflow=False,
        has_schedule_wakeup=True,
    )
    assert selection.pacer == PACER_PORTABLE


def test_pr_converge_with_schedule_wakeup_selects_schedule_wakeup() -> None:
    selection = pacer_module.select_converge_pacer(
        entry_skill=ENTRY_SKILL_PR_CONVERGE,
        has_workflow=False,
        has_schedule_wakeup=True,
    )
    assert selection.pacer == PACER_SCHEDULE_WAKEUP
    assert selection.entry_skill == ENTRY_SKILL_PR_CONVERGE


def test_pr_converge_without_schedule_wakeup_selects_portable() -> None:
    selection = pacer_module.select_converge_pacer(
        entry_skill=ENTRY_SKILL_PR_CONVERGE,
        has_workflow=True,
        has_schedule_wakeup=False,
    )
    assert selection.pacer == PACER_PORTABLE


def test_third_party_surface_selects_portable_for_both_entries() -> None:
    for each_skill in (ENTRY_SKILL_AUTOCONVERGE, ENTRY_SKILL_PR_CONVERGE):
        selection = pacer_module.select_converge_pacer(
            entry_skill=each_skill,
            has_workflow=False,
            has_schedule_wakeup=False,
        )
        assert selection.pacer == PACER_PORTABLE, each_skill


def test_unknown_entry_skill_raises() -> None:
    with pytest.raises(ValueError, match="entry skill must be one of"):
        pacer_module.select_converge_pacer(
            entry_skill="bugteam",
            has_workflow=False,
            has_schedule_wakeup=False,
        )


def test_parse_bool_flag_accepts_common_tokens() -> None:
    assert pacer_module.parse_bool_flag("1") is True
    assert pacer_module.parse_bool_flag("true") is True
    assert pacer_module.parse_bool_flag("YES") is True
    assert pacer_module.parse_bool_flag("0") is False
    assert pacer_module.parse_bool_flag("false") is False
    assert pacer_module.parse_bool_flag("OFF") is False


def test_parse_bool_flag_rejects_unknown_token() -> None:
    with pytest.raises(ValueError, match="boolean token"):
        pacer_module.parse_bool_flag("maybe")


def test_selection_as_json_dict_uses_stable_keys() -> None:
    selection = pacer_module.select_converge_pacer(
        entry_skill=ENTRY_SKILL_PR_CONVERGE,
        has_workflow=False,
        has_schedule_wakeup=False,
    )
    payload = pacer_module.selection_as_json_dict(selection)
    assert payload[RESULT_KEY_PACER] == PACER_PORTABLE
    assert payload[RESULT_KEY_ENTRY_SKILL] == ENTRY_SKILL_PR_CONVERGE
    assert payload[RESULT_KEY_HAS_WORKFLOW] is False
    assert payload[RESULT_KEY_HAS_SCHEDULE_WAKEUP] is False


def test_cli_prints_json_and_exits_zero() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--skill",
            ENTRY_SKILL_AUTOCONVERGE,
            "--has-workflow",
            "0",
            "--has-schedule-wakeup",
            "0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == EXIT_SUCCESS, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload[RESULT_KEY_PACER] == PACER_PORTABLE
    assert payload[RESULT_KEY_ENTRY_SKILL] == ENTRY_SKILL_AUTOCONVERGE


def test_cli_rejects_bad_bool_with_usage_exit() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--skill",
            ENTRY_SKILL_PR_CONVERGE,
            "--has-workflow",
            "nope",
            "--has-schedule-wakeup",
            "0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == EXIT_USAGE_ERROR
    assert "boolean token" in completed.stderr


def test_main_returns_usage_error_on_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_value_error(**_kwargs: object) -> object:
        raise ValueError("entry skill must be one of")

    monkeypatch.setattr(
        pacer_module, "select_converge_pacer", raise_value_error
    )
    exit_code = pacer_module.main(
        [
            "--skill",
            ENTRY_SKILL_PR_CONVERGE,
            "--has-workflow",
            "0",
            "--has-schedule-wakeup",
            "0",
        ]
    )
    assert exit_code == EXIT_USAGE_ERROR


def test_build_argument_parser_requires_skill_and_host_flags() -> None:
    parser = pacer_module.build_argument_parser()
    all_option_strings = {
        each_option
        for each_action in parser._actions
        for each_option in each_action.option_strings
    }
    assert CLI_SKILL_FLAG in all_option_strings
    assert CLI_HAS_WORKFLOW_FLAG in all_option_strings
    assert CLI_HAS_SCHEDULE_WAKEUP_FLAG in all_option_strings
    parsed_namespace = parser.parse_args(
        [
            CLI_SKILL_FLAG,
            ENTRY_SKILL_AUTOCONVERGE,
            CLI_HAS_WORKFLOW_FLAG,
            "1",
            CLI_HAS_SCHEDULE_WAKEUP_FLAG,
            "0",
        ]
    )
    assert parsed_namespace.skill == ENTRY_SKILL_AUTOCONVERGE
    assert parsed_namespace.has_workflow == "1"
    assert parsed_namespace.has_schedule_wakeup == "0"
