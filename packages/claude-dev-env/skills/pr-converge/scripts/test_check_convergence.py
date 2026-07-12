"""Tests for check_convergence.

Covers the bugteam audit gate (`_check_bugteam_clean`) which identifies
bugteam reviews by body header signature, the down-flag resolvers, the
reviewer-bypass paths through ``check_all``, and the ``main`` entry point.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Callable

import pytest

import _path_setup  # noqa: F401
from pr_converge_skill_constants.constants import EXIT_CODE_GH_ERROR

_SCRIPTS_DIRECTORY = Path(__file__).absolute().parent
_PR_CONVERGE_DIRECTORY = _SCRIPTS_DIRECTORY.parent

if str(_PR_CONVERGE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_PR_CONVERGE_DIRECTORY))


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
        "check_convergence_under_test", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_convergence = _load_module()

CURRENT_HEAD_SHA = "abcdef1234567890abcdef1234567890abcdef12"
OTHER_HEAD_SHA = "0000000000000000000000000000000000000000"
CLEAN_BUGTEAM_BODY = (
    "**Bugteam audit completed** —— Clean — no findings\n"
    "\n"
    "---\n"
    "### Audit pass clean\n"
    "\n"
    "The Bugteam audit pass against commit `abcdef1` found no findings.\n"
)
DIRTY_BUGTEAM_BODY = (
    "**Bugteam audit completed** —— Findings requested\n"
    "\n"
    "---\n"
    "### Findings recorded as inline review comments\n"
    "\n"
    "The Bugteam audit pass against commit `abcdef1` surfaced 2 finding(s).\n"
)
NON_BUGTEAM_BODY = (
    "Cursor Bugbot has reviewed your changes and found 0 potential issues."
)

_ALL_LEAF_GATE_NAMES = [
    "_check_bugbot",
    "_check_bugbot_not_dirty",
    "_check_bugteam_clean",
    "_check_bot_review",
    "_count_unresolved_bot_threads",
    "_get_mergeable",
    "_check_no_pending_reviews",
]


def _make_stub_gh_paginated(
    all_review_objects: list[dict[str, object]],
) -> Callable[[str], tuple[int, str]]:
    pages_payload = [all_review_objects]
    serialized = json.dumps(pages_payload)

    def stub_gh_api_paginated(endpoint_path: str) -> tuple[int, str]:
        return 0, serialized

    return stub_gh_api_paginated


def _passing_head_sha(**_call_keywords: object) -> str:
    return CURRENT_HEAD_SHA


def _passing_gate(**_call_keywords: object) -> tuple[bool, str]:
    return True, "stub passing"


def _raise_if_called(gate_label: str) -> Callable[..., tuple[bool, str]]:
    def _stub(**_call_keywords: object) -> tuple[bool, str]:
        raise AssertionError(f"{gate_label} must not run when its gate is bypassed")

    return _stub


def _patch_all_gates_passing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check_convergence, "_get_pr_head_sha", _passing_head_sha)
    for each_gate_name in _ALL_LEAF_GATE_NAMES:
        monkeypatch.setattr(check_convergence, each_gate_name, _passing_gate)


def should_pass_when_clean_bugteam_review_present_on_current_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviews_payload = [
        {
            "id": 1001,
            "body": CLEAN_BUGTEAM_BODY,
            "commit_id": CURRENT_HEAD_SHA,
            "submitted_at": "2026-05-17T12:00:00Z",
        }
    ]
    monkeypatch.setattr(
        check_convergence, "_gh_api_paginated", _make_stub_gh_paginated(reviews_payload)
    )
    passed, detail = check_convergence._check_bugteam_clean(
        owner="JonEcho", repo="tests", number=42, head_sha=CURRENT_HEAD_SHA
    )
    assert passed is True
    assert "clean bugteam audit" in detail
    assert CURRENT_HEAD_SHA[:7] in detail


def should_fail_when_dirty_bugteam_review_present_on_current_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviews_payload = [
        {
            "id": 1002,
            "body": DIRTY_BUGTEAM_BODY,
            "commit_id": CURRENT_HEAD_SHA,
            "submitted_at": "2026-05-17T12:00:00Z",
        }
    ]
    monkeypatch.setattr(
        check_convergence, "_gh_api_paginated", _make_stub_gh_paginated(reviews_payload)
    )
    passed, detail = check_convergence._check_bugteam_clean(
        owner="JonEcho", repo="tests", number=42, head_sha=CURRENT_HEAD_SHA
    )
    assert passed is False
    assert "dirty bugteam audit" in detail
    assert CURRENT_HEAD_SHA[:7] in detail


def should_fail_when_no_bugteam_review_present_on_current_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviews_payload = [
        {
            "id": 1003,
            "body": NON_BUGTEAM_BODY,
            "commit_id": CURRENT_HEAD_SHA,
            "submitted_at": "2026-05-17T12:00:00Z",
        },
        {
            "id": 1004,
            "body": CLEAN_BUGTEAM_BODY,
            "commit_id": OTHER_HEAD_SHA,
            "submitted_at": "2026-05-17T11:00:00Z",
        },
    ]
    monkeypatch.setattr(
        check_convergence, "_gh_api_paginated", _make_stub_gh_paginated(reviews_payload)
    )
    passed, detail = check_convergence._check_bugteam_clean(
        owner="JonEcho", repo="tests", number=42, head_sha=CURRENT_HEAD_SHA
    )
    assert passed is False
    assert "no bugteam review found" in detail


def should_fail_with_shape_detail_when_gh_returns_non_list_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error_object_payload = {"message": "Not Found", "documentation_url": "https://docs.github.com/rest"}
    serialized_error = json.dumps(error_object_payload)

    def stub_gh_api_paginated_returning_object(endpoint_path: str) -> tuple[int, str]:
        return 0, serialized_error

    monkeypatch.setattr(
        check_convergence, "_gh_api_paginated", stub_gh_api_paginated_returning_object
    )
    passed, detail = check_convergence._check_bugteam_clean(
        owner="JonEcho", repo="tests", number=42, head_sha=CURRENT_HEAD_SHA
    )
    assert passed is False
    assert "unexpected gh api response shape" in detail


def test_private_helpers_recognize_clean_new_header_body() -> None:
    assert check_convergence._is_bugteam_review(CLEAN_BUGTEAM_BODY) is True
    assert check_convergence._is_clean_bugteam_review(CLEAN_BUGTEAM_BODY) is True


def test_private_helpers_recognize_dirty_new_header_body() -> None:
    assert check_convergence._is_bugteam_review(DIRTY_BUGTEAM_BODY) is True
    assert check_convergence._is_clean_bugteam_review(DIRTY_BUGTEAM_BODY) is False


def test_private_helpers_reject_non_bugteam_body() -> None:
    assert check_convergence._is_bugteam_review(NON_BUGTEAM_BODY) is False
    assert check_convergence._is_clean_bugteam_review(NON_BUGTEAM_BODY) is False


CLEAN_LEGACY_BUGTEAM_BODY = "## /bugteam loop 1 audit: 0 P0 / 0 P1 / 0 P2 → clean"
DIRTY_LEGACY_BUGTEAM_BODY = "## /bugteam loop 1 audit: 1 P0 / 0 P1 / 0 P2 → dirty"


def test_private_helpers_recognize_clean_legacy_header_body() -> None:
    assert check_convergence._is_bugteam_review(CLEAN_LEGACY_BUGTEAM_BODY) is True
    assert check_convergence._is_clean_bugteam_review(CLEAN_LEGACY_BUGTEAM_BODY) is True


def test_private_helpers_recognize_dirty_legacy_header_body() -> None:
    assert check_convergence._is_bugteam_review(DIRTY_LEGACY_BUGTEAM_BODY) is True
    assert check_convergence._is_clean_bugteam_review(DIRTY_LEGACY_BUGTEAM_BODY) is False


def should_resolve_bugbot_down_true_when_flag_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    assert check_convergence._resolve_bugbot_down(True) is True


def should_resolve_bugbot_down_true_when_env_disables_bugbot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "bugbot")
    assert check_convergence._resolve_bugbot_down(False) is True


def should_resolve_bugbot_down_true_when_flag_unset_and_env_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    monkeypatch.delenv("CLAUDE_REVIEWS_ENABLED", raising=False)
    assert check_convergence._resolve_bugbot_down(False) is True


def should_resolve_bugbot_down_false_when_enabled_lists_bugbot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    monkeypatch.setenv("CLAUDE_REVIEWS_ENABLED", "bugbot")
    assert check_convergence._resolve_bugbot_down(False) is False


def should_resolve_copilot_down_true_when_flag_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    assert check_convergence._resolve_copilot_down(True) is True


def should_resolve_copilot_down_true_when_env_disables_copilot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "copilot")
    assert check_convergence._resolve_copilot_down(False) is True


def should_resolve_copilot_down_false_when_flag_unset_and_env_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_REVIEWS_DISABLED", raising=False)
    assert check_convergence._resolve_copilot_down(False) is False


def should_resolve_copilot_down_false_when_env_disables_only_bugbot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "bugbot")
    assert check_convergence._resolve_copilot_down(False) is False


def should_bypass_bugbot_gates_when_bugbot_down_is_true(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _patch_all_gates_passing(monkeypatch)
    monkeypatch.setattr(check_convergence, "_check_bugbot", _raise_if_called("_check_bugbot"))
    monkeypatch.setattr(
        check_convergence, "_check_bugbot_not_dirty", _raise_if_called("_check_bugbot_not_dirty")
    )
    exit_code = check_convergence.check_all(
        owner="o", repo="r", number=1, is_bugbot_down=True, is_copilot_down=False
    )
    assert "bypassed (bugbot_down)" in capsys.readouterr().out
    assert exit_code == 0


def should_bypass_copilot_gates_when_copilot_down_is_true(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _patch_all_gates_passing(monkeypatch)
    monkeypatch.setattr(check_convergence, "_check_bot_review", _raise_if_called("_check_bot_review"))
    monkeypatch.setattr(
        check_convergence, "_check_no_pending_reviews", _raise_if_called("_check_no_pending_reviews")
    )
    exit_code = check_convergence.check_all(
        owner="o", repo="r", number=1, is_bugbot_down=False, is_copilot_down=True
    )
    assert "bypassed (copilot_down)" in capsys.readouterr().out
    assert exit_code == 0


def should_accept_copilot_down_flag_in_parsed_arguments() -> None:
    arguments = check_convergence.parse_arguments(
        ["--owner", "o", "--repo", "r", "--pr-number", "1", "--copilot-down"]
    )
    assert arguments.copilot_down is True


def should_return_zero_from_print_conditions_when_every_condition_passes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = check_convergence._print_conditions(
        [("gate one", (True, "ok")), ("gate two", (True, "ok"))]
    )
    captured_stdout = capsys.readouterr().out
    assert exit_code == 0
    assert "All pre-conditions met" in captured_stdout


def should_return_one_from_print_conditions_when_any_condition_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = check_convergence._print_conditions(
        [("gate one", (True, "ok")), ("gate two", (False, "nope"))]
    )
    captured_stdout = capsys.readouterr().out
    assert exit_code == 1
    assert "One or more pre-conditions not met" in captured_stdout


def should_propagate_systemexit_from_get_pr_head_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    def stub_get_pr_head_sha_raising_systemexit(**_call_keywords: object) -> str:
        raise SystemExit(EXIT_CODE_GH_ERROR)

    monkeypatch.setattr(
        check_convergence, "_get_pr_head_sha", stub_get_pr_head_sha_raising_systemexit
    )
    with pytest.raises(SystemExit) as exc_info:
        check_convergence.check_all(
            owner="o", repo="r", number=1, is_bugbot_down=False, is_copilot_down=False
        )
    assert exc_info.value.code == EXIT_CODE_GH_ERROR


def should_derive_copilot_down_from_env_when_main_omits_the_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLAUDE_REVIEWS_DISABLED", "copilot")
    captured_copilot_down: list[bool] = []

    def stub_check_all(
        *,
        owner: str,
        repo: str,
        number: int,
        is_bugbot_down: bool,
        is_copilot_down: bool,
        is_bugteam_post_blocked: bool = False,
    ) -> int:
        captured_copilot_down.append(is_copilot_down)
        return 0

    monkeypatch.setattr(check_convergence, "check_all", stub_check_all)
    exit_code = check_convergence.main(["--owner", "o", "--repo", "r", "--pr-number", "1"])
    assert exit_code == 0
    assert captured_copilot_down == [True]
