from __future__ import annotations

import git_hooks_constants


def test_pre_push_gate_script_not_found_message_contains_path_placeholder() -> None:
    assert "{path}" in git_hooks_constants.PRE_PUSH_GATE_SCRIPT_NOT_FOUND_MESSAGE


def test_no_parseable_stdin_lines_message_exists_and_describes_problem() -> None:
    assert "no parseable stdin lines" in git_hooks_constants.NO_PARSEABLE_STDIN_LINES_MESSAGE


def test_pre_push_cut_leftovers_are_removed() -> None:
    for removed_name in (
        "ALL_DEFAULT_BRANCH_FALLBACK_REFERENCES",
        "ORIGIN_HEAD_SYMBOLIC_REFERENCE",
        "ORIGIN_REMOTE_TRACKING_REFERENCE_PREFIX",
        "UNRESOLVABLE_MERGE_BASE_SENTINEL",
        "UNRESOLVABLE_MERGE_BASE_MESSAGE",
        "NO_PARSEABLE_STDIN_LINES_SENTINEL",
    ):
        assert not hasattr(git_hooks_constants, removed_name)
