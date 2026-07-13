"""Contract-pin and flag tests for check_convergence.

::

    check_all(all gates passing,
        is_bugteam_post_blocked=False,
    )       -> exit 0, "All pre-conditions met ..."
    check_all(one gate failing,
        is_bugteam_post_blocked=False,
    )        -> exit 1, "One or more ... do not mark ready."
    _get_pr_head_sha raises SystemExit -> exit 2 propagates
    parse_arguments([... --bugteam-post-blocked]) -> bugteam_post_blocked True

The pin tests fix the stdout the four consumers parse (converge.mjs, pr-converge,
bugteam, qbug) byte-for-byte, plus the exit codes and CLI surface. The flag tests
drive the ``--bugteam-post-blocked`` bypass.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

import _pr_converge_path_setup  # noqa: F401
from pr_converge_skill_constants.constants import EXIT_CODE_GH_ERROR

_SCRIPTS_DIRECTORY = Path(__file__).absolute().parent
_PR_CONVERGE_DIRECTORY = _SCRIPTS_DIRECTORY.parent

CURRENT_HEAD_SHA = "abcdef1234567890abcdef1234567890abcdef12"

_ALL_LEAF_GATE_NAMES = [
    "_check_bugbot",
    "_check_bugbot_not_dirty",
    "_check_bugteam_clean",
    "_check_bot_review",
    "_count_unresolved_bot_threads",
    "_get_mergeable",
    "_check_no_pending_reviews",
]

EXPECTED_ALL_PASS_STDOUT = (
    "HEAD: abcdef1\n\n"
    "1. bugbot_clean_at == current_head: PASS — clean\n"
    "2. bugbot review body clean: PASS — clean\n"
    "3. bugteam_clean_at == current_head: PASS — clean\n"
    "4. copilot_clean_at == current_head: PASS — clean\n"
    "5. zero unresolved bot threads: PASS — clean\n"
    "6. PR is mergeable: PASS — clean\n"
    "7. no pending requested reviews: PASS — clean\n\n"
    "All pre-conditions met — PR is ready to mark ready.\n"
)

EXPECTED_BUGBOT_DOWN_STDOUT = (
    "HEAD: abcdef1\n\n"
    "1. bugbot_clean_at == current_head: PASS — bypassed (bugbot_down)\n"
    "2. bugteam_clean_at == current_head: PASS — clean\n"
    "3. copilot_clean_at == current_head: PASS — clean\n"
    "4. zero unresolved bot threads: PASS — clean\n"
    "5. PR is mergeable: PASS — clean\n"
    "6. no pending requested reviews: PASS — clean\n\n"
    "All pre-conditions met — PR is ready to mark ready.\n"
)

EXPECTED_COPILOT_DOWN_STDOUT = (
    "HEAD: abcdef1\n\n"
    "1. bugbot_clean_at == current_head: PASS — clean\n"
    "2. bugbot review body clean: PASS — clean\n"
    "3. bugteam_clean_at == current_head: PASS — clean\n"
    "4. copilot_clean_at == current_head: PASS — bypassed (copilot_down)\n"
    "5. zero unresolved bot threads: PASS — clean\n"
    "6. PR is mergeable: PASS — clean\n"
    "7. no pending requested reviews: PASS — bypassed (copilot_down)\n\n"
    "All pre-conditions met — PR is ready to mark ready.\n"
)

EXPECTED_FAIL_SUMMARY = "One or more pre-conditions not met — do not mark ready.\n"

EXPECTED_COPILOT_PROBE_ERROR_STDOUT = (
    "HEAD: abcdef1\n\n"
    "1. bugbot_clean_at == current_head: PASS — clean\n"
    "2. bugbot review body clean: PASS — clean\n"
    "3. bugteam_clean_at == current_head: PASS — clean\n"
    "4. copilot_clean_at == current_head: FAIL — enforced (probe error: quota API down)\n"
    "5. zero unresolved bot threads: PASS — clean\n"
    "6. PR is mergeable: PASS — clean\n"
    "7. no pending requested reviews: FAIL — enforced (probe error: quota API down)\n\n"
    "One or more pre-conditions not met — do not mark ready.\n"
)


def _load_check_convergence() -> ModuleType:
    if str(_PR_CONVERGE_DIRECTORY) not in sys.path:
        sys.path.insert(0, str(_PR_CONVERGE_DIRECTORY))
    if str(_SCRIPTS_DIRECTORY) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIRECTORY))
    module_path = _SCRIPTS_DIRECTORY / "check_convergence.py"
    spec = importlib.util.spec_from_file_location(
        "check_convergence_contract_under_test", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_convergence = _load_check_convergence()


def _clean_head(**_call_keywords: object) -> str:
    return CURRENT_HEAD_SHA


def _clean_gate(**_call_keywords: object) -> tuple[bool, str]:
    return True, "clean"


def _refuse_bugteam_clean(**_call_keywords: object) -> tuple[bool, str]:
    raise AssertionError(
        "_check_bugteam_clean must not run when is_bugteam_post_blocked=True"
    )


def _patch_gates_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check_convergence, "_get_pr_head_sha", _clean_head)
    for each_gate_name in _ALL_LEAF_GATE_NAMES:
        monkeypatch.setattr(check_convergence, each_gate_name, _clean_gate)


def test_all_pass_stdout_and_exit_code_match_the_pinned_contract(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _patch_gates_clean(monkeypatch)
    exit_code = check_convergence.check_all(
        owner="o", repo="r", number=1, is_bugbot_down=False, is_copilot_down=False
    , is_bugteam_post_blocked=False)
    assert capsys.readouterr().out == EXPECTED_ALL_PASS_STDOUT
    assert exit_code == 0


def test_bugbot_down_bypass_line_matches_the_pinned_contract(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _patch_gates_clean(monkeypatch)
    exit_code = check_convergence.check_all(
        owner="o", repo="r", number=1, is_bugbot_down=True, is_copilot_down=False
    , is_bugteam_post_blocked=False)
    assert capsys.readouterr().out == EXPECTED_BUGBOT_DOWN_STDOUT
    assert exit_code == 0


def test_copilot_down_bypass_lines_match_the_pinned_contract(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _patch_gates_clean(monkeypatch)
    exit_code = check_convergence.check_all(
        owner="o", repo="r", number=1, is_bugbot_down=False, is_copilot_down=True
    , is_bugteam_post_blocked=False)
    assert capsys.readouterr().out == EXPECTED_COPILOT_DOWN_STDOUT
    assert exit_code == 0


def test_a_failing_gate_yields_exit_one_and_the_fail_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _patch_gates_clean(monkeypatch)

    def _blocked_mergeable(**_call_keywords: object) -> tuple[bool, str]:
        return False, "blocked"

    monkeypatch.setattr(check_convergence, "_get_mergeable", _blocked_mergeable)
    exit_code = check_convergence.check_all(
        owner="o", repo="r", number=1, is_bugbot_down=False, is_copilot_down=False
    , is_bugteam_post_blocked=False)
    captured_stdout = capsys.readouterr().out
    assert "6. PR is mergeable: FAIL — blocked\n" in captured_stdout
    assert captured_stdout.endswith(EXPECTED_FAIL_SUMMARY)
    assert exit_code == 1


def test_gh_error_exit_code_is_two_and_propagates_from_head_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_gh_error(**_call_keywords: object) -> str:
        raise SystemExit(EXIT_CODE_GH_ERROR)

    monkeypatch.setattr(check_convergence, "_get_pr_head_sha", _raise_gh_error)
    with pytest.raises(SystemExit) as raised:
        check_convergence.check_all(
            owner="o", repo="r", number=1, is_bugbot_down=False, is_copilot_down=False
        , is_bugteam_post_blocked=False)
    assert EXIT_CODE_GH_ERROR == 2
    assert raised.value.code == 2


def test_existing_cli_flags_stay_on_the_argument_surface() -> None:
    arguments = check_convergence.parse_arguments(
        [
            "--owner",
            "o",
            "--repo",
            "r",
            "--pr-number",
            "1",
            "--bugbot-down",
            "--copilot-down",
        ]
    )
    assert arguments.owner == "o"
    assert arguments.repo == "r"
    assert getattr(arguments, "pr_number") == 1
    assert arguments.bugbot_down is True
    assert arguments.copilot_down is True


def test_skip_bugteam_gate_when_bugteam_post_blocked_is_true(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _patch_gates_clean(monkeypatch)
    monkeypatch.setattr(
        check_convergence, "_check_bugteam_clean", _refuse_bugteam_clean
    )
    exit_code = check_convergence.check_all(
        owner="o",
        repo="r",
        number=1,
        is_bugbot_down=False,
        is_copilot_down=False,
        is_bugteam_post_blocked=True,
    )
    assert "bypassed (bugteam_post_blocked)" in capsys.readouterr().out
    assert exit_code == 0


def test_run_bugteam_gate_when_bugteam_post_blocked_is_false(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    invoked_gate_names: list[str] = []

    def _recording_bugteam_clean(**_call_keywords: object) -> tuple[bool, str]:
        invoked_gate_names.append("_check_bugteam_clean")
        return True, "clean"

    _patch_gates_clean(monkeypatch)
    monkeypatch.setattr(
        check_convergence, "_check_bugteam_clean", _recording_bugteam_clean
    )
    exit_code = check_convergence.check_all(
        owner="o",
        repo="r",
        number=1,
        is_bugbot_down=False,
        is_copilot_down=False,
        is_bugteam_post_blocked=False,
    )
    assert "_check_bugteam_clean" in invoked_gate_names
    assert "bypassed (bugteam_post_blocked)" not in capsys.readouterr().out
    assert exit_code == 0


def test_bugteam_post_blocked_flag_round_trips_through_parse_arguments() -> None:
    arguments = check_convergence.parse_arguments(
        ["--owner", "o", "--repo", "r", "--pr-number", "1", "--bugteam-post-blocked"]
    )
    assert arguments.bugteam_post_blocked is True


def test_bugteam_post_blocked_defaults_to_false_when_flag_absent() -> None:
    arguments = check_convergence.parse_arguments(
        ["--owner", "o", "--repo", "r", "--pr-number", "1"]
    )
    assert arguments.bugteam_post_blocked is False


def test_resolve_bugteam_post_blocked_true_when_flag_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    assert check_convergence._resolve_bugteam_post_blocked(True) is True


def test_resolve_bugteam_post_blocked_true_when_env_disables_bugteam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "bugteam")
    assert check_convergence._resolve_bugteam_post_blocked(False) is True


def test_resolve_bugteam_post_blocked_false_when_flag_unset_and_env_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    assert check_convergence._resolve_bugteam_post_blocked(False) is False


def test_resolve_bugteam_post_blocked_false_when_env_disables_only_copilot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "copilot")
    assert check_convergence._resolve_bugteam_post_blocked(False) is False


def test_env_bugteam_token_does_not_disable_copilot_or_bugbot_opt_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "bugteam")
    assert check_convergence._resolve_copilot_down(False) is False
    assert check_convergence._resolve_bugteam_post_blocked(False) is True


def test_main_derives_bugteam_post_blocked_from_env_when_flag_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "bugteam")
    captured_bugteam_post_blocked: list[bool] = []

    def stub_check_all(
        *,
        owner: str,
        repo: str,
        number: int,
        is_bugbot_down: bool,
        is_copilot_down: bool,
        is_bugteam_post_blocked: bool = False,
        **_bypass_note_kwargs: str,
    ) -> int:
        captured_bugteam_post_blocked.append(is_bugteam_post_blocked)
        return 0

    monkeypatch.setattr(check_convergence, "check_all", stub_check_all)
    exit_code = check_convergence.main(["--owner", "o", "--repo", "r", "--pr-number", "1"])
    assert exit_code == 0
    assert captured_bugteam_post_blocked == [True]


def test_copilot_probe_error_fail_lines_match_the_pinned_contract(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _patch_gates_clean(monkeypatch)
    monkeypatch.setattr(
        check_convergence,
        "_check_bot_review",
        lambda **_keywords: (_ for _ in ()).throw(
            AssertionError("copilot live gate must not run on probe error")
        ),
    )
    monkeypatch.setattr(
        check_convergence,
        "_check_no_pending_reviews",
        lambda **_keywords: (_ for _ in ()).throw(
            AssertionError("pending live gate must not run on probe error")
        ),
    )
    exit_code = check_convergence.check_all(
        owner="o",
        repo="r",
        number=1,
        is_bugbot_down=False,
        is_copilot_down=False,
        is_bugteam_post_blocked=False,
        copilot_probe_error_reason="quota API down",
    )
    assert capsys.readouterr().out == EXPECTED_COPILOT_PROBE_ERROR_STDOUT
    assert exit_code == 1
