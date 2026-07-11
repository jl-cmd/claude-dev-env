"""Behavior tests for the code_rules_enforcer code-rules check module."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_annotations_length import (  # noqa: E402
    FUNCTION_LENGTH_BLOCKING_THRESHOLD,
)
from code_rules_enforcer import (  # noqa: E402
    main,
    prior_and_post_edit_content,
    validate_content,
)

code_rules_enforcer = SimpleNamespace(
    FUNCTION_LENGTH_BLOCKING_THRESHOLD=FUNCTION_LENGTH_BLOCKING_THRESHOLD,
    main=main,
    prior_and_post_edit_content=prior_and_post_edit_content,
    sys=sys,
    validate_content=validate_content,
)


def _oversized_function_source(name: str) -> str:
    body_line_count = code_rules_enforcer.FUNCTION_LENGTH_BLOCKING_THRESHOLD - 1
    body_lines = [
        f"    bound_{each_index} = {each_index}" for each_index in range(body_line_count)
    ]
    return f"def {name}() -> None:\n" + "\n".join(body_lines) + "\n"


def _run_main_with_edit_payload(
    file_path: str,
    old_string: str,
    new_string: str,
    monkeypatch: object,
    capsys: object,
) -> str:
    """Drive ``main()`` through its stdin entry point for an Edit and return stdout.

    Args:
        file_path: The on-disk path the Edit targets.
        old_string: The Edit's ``old_string`` fragment.
        new_string: The Edit's ``new_string`` fragment.
        monkeypatch: The pytest fixture used to redirect ``sys.stdin``.
        capsys: The pytest fixture used to capture the deny payload on stdout.

    Returns:
        The captured stdout, which holds the deny payload when violations fire.
    """
    edit_payload = json.dumps(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": file_path,
                "old_string": old_string,
                "new_string": new_string,
            },
        }
    )
    getattr(monkeypatch, "setattr")(code_rules_enforcer.sys, "stdin", io.StringIO(edit_payload))
    try:
        code_rules_enforcer.main([])
    except SystemExit:
        pass
    captured = getattr(capsys, "readouterr")()
    return captured.out


def test_banned_noun_word_keeps_in_scope_binding_among_untouched_ones() -> None:
    """loop7-P1: an Edit whose changed line introduces a banned-noun identifier
    among several pre-existing untouched ones must still report the new in-scope
    binding while leaving the untouched bindings out of scope."""
    leading_count = 5
    leading_bindings = "".join(
        f"LEADING_{each_index}_RESULT_PATH = {each_index}\n"
        for each_index in range(leading_count)
    )
    target_before = "PLACEHOLDER_NAME = 0\n"
    target_after = "INTRODUCED_RESULT_PATH = 0\n"
    prior_full_file = leading_bindings + target_before
    post_edit_full_file = leading_bindings + target_after
    issues = code_rules_enforcer.validate_content(
        target_after,
        "/project/src/many_nouns.py",
        old_content=target_before,
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )
    assert any(
        "INTRODUCED_RESULT_PATH" in each_issue for each_issue in issues
    ), f"in-scope banned-noun past the cap window must still block, got: {issues!r}"


def test_banned_noun_edit_drops_untouched_out_of_scope_binding() -> None:
    """An Edit that touches none of the banned-noun bindings reports nothing —
    the check now routes through the reconstructed effective content and the
    edit's changed lines, exactly like check_function_length, so an untouched
    binding outside the edit hunk must not block."""
    leading = "".join(
        f"LEADING_{each_index}_RESULT_PATH = {each_index}\n" for each_index in range(5)
    )
    edited_tail = "def compute_total() -> int:\n    running_sum = 0\n    return running_sum\n"
    prior_full_file = leading + "def compute_total() -> int:\n    running_sum = 0\n    return 0\n"
    post_edit_full_file = leading + edited_tail
    issues = code_rules_enforcer.validate_content(
        edited_tail,
        "/project/src/many_nouns.py",
        old_content="def compute_total() -> int:\n    running_sum = 0\n    return 0\n",
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )
    assert not any(
        "RESULT_PATH" in each_issue for each_issue in issues
    ), f"untouched banned-noun bindings must stay out of scope, got: {issues!r}"


def test_banned_noun_edit_keeps_touched_binding_in_scope() -> None:
    """An Edit whose changed line introduces a banned-noun binding reports it,
    using the reconstructed effective content and the edit's changed lines."""
    leading = "".join(
        f"LEADING_{each_index}_VALUE_PATH = {each_index}\n" for each_index in range(5)
    )
    prior_tail = "PLACEHOLDER_NAME = 0\n"
    edited_tail = "INTRODUCED_RESULT_PATH = 0\n"
    prior_full_file = leading + prior_tail
    post_edit_full_file = leading + edited_tail
    issues = code_rules_enforcer.validate_content(
        edited_tail,
        "/project/src/introduces_noun.py",
        old_content=prior_tail,
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )
    assert any(
        "INTRODUCED_RESULT_PATH" in each_issue for each_issue in issues
    ), f"introduced banned-noun binding must block, got: {issues!r}"


def test_banned_noun_edit_does_not_reflag_param_when_unrelated_body_line_changes() -> None:
    """Editing a body line of a function that already has a banned-noun
    parameter must not re-flag that pre-existing parameter: the binding-line
    span keeps the parameter out of scope unless its own declaration line is in
    the changed set."""
    prior_full_file = (
        "def transform(canned_results: int) -> int:\n"
        "    midpoint = canned_results\n"
        "    return midpoint\n"
    )
    post_edit_full_file = (
        "def transform(canned_results: int) -> int:\n"
        "    midpoint = canned_results + 1\n"
        "    return midpoint\n"
    )
    issues = code_rules_enforcer.validate_content(
        "    midpoint = canned_results + 1\n",
        "/project/src/has_param.py",
        old_content="    midpoint = canned_results\n",
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )
    assert not any(
        "canned_results" in each_issue for each_issue in issues
    ), f"pre-existing param must not re-flag on unrelated body edit, got: {issues!r}"


def test_unreadable_prior_yields_no_prior_and_no_reconstruction() -> None:
    """When the on-disk prior cannot be read for an Edit, the prior/post helper
    returns (None, None): a missing prior must not be fabricated as an empty
    string that would diff every line as changed and defeat edit scoping."""
    missing_path = "/project/src/does_not_exist_anywhere.py"
    prior_content, post_edit_content = code_rules_enforcer.prior_and_post_edit_content(
        missing_path,
        old_string="placeholder = 0\n",
        new_string="placeholder = 1\n",
    )
    assert prior_content is None
    assert post_edit_content is None


def test_edit_with_missing_old_string_runs_whole_file_against_on_disk_content(
    tmp_path_factory: object, monkeypatch: object, capsys: object,
) -> None:
    """When an Edit's old_string is absent from the file, ``prior_and_post_edit_content``
    yields ``(None, None)``; ``main()`` must analyze the real on-disk file whole-file
    rather than the new_string fragment, so an oversized function elsewhere in the
    file is still reported with its true line numbers."""
    production_directory = getattr(tmp_path_factory, "mktemp")("production_pkg")
    untouched_long_function = _oversized_function_source("untouched_long")
    short_helper = "def short_helper() -> int:\n    return 1\n"
    on_disk_content = untouched_long_function + "\n" + short_helper
    source_file = production_directory / "edited_module.py"
    source_file.write_text(on_disk_content, encoding="utf-8")
    absent_fragment_old = "def absent_function() -> int:\n    return 0\n"
    short_fragment_new = "def absent_function() -> int:\n    return 2\n"
    stdout = _run_main_with_edit_payload(
        str(source_file), absent_fragment_old, short_fragment_new, monkeypatch, capsys,
    )
    assert "untouched_long" in stdout, (
        "an unreconstructable Edit must fall back to whole-file on-disk analysis, "
        f"so the oversized function is still reported; got stdout: {stdout!r}"
    )


def test_edit_with_unreadable_file_does_not_analyze_fragment_as_whole_file(
    tmp_path_factory: object, monkeypatch: object, capsys: object,
) -> None:
    """When the on-disk file cannot be read, no well-defined post-edit content
    exists; ``main()`` must exit cleanly rather than analyze the new_string
    fragment as if it were the whole file, so the fragment's own function-length
    violation does not surface as a deny payload."""
    production_directory = getattr(tmp_path_factory, "mktemp")("production_pkg")
    missing_path = str(production_directory / "never_created.py")
    oversized_fragment_old = "def grows() -> int:\n    return 0\n"
    oversized_fragment_new = _oversized_function_source("grows")
    stdout = _run_main_with_edit_payload(
        missing_path,
        oversized_fragment_old,
        oversized_fragment_new,
        monkeypatch,
        capsys,
    )
    assert stdout == "", (
        "an unreadable Edit target has no well-defined whole-file content, so the "
        f"fragment must not be analyzed as the whole file; got stdout: {stdout!r}"
    )
