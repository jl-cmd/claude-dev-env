"""Behavior tests for the code_rules_enforcer code-rules check module."""

from __future__ import annotations

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
    validate_content,
)

code_rules_enforcer = SimpleNamespace(
    FUNCTION_LENGTH_BLOCKING_THRESHOLD=FUNCTION_LENGTH_BLOCKING_THRESHOLD,
    validate_content=validate_content,
)


DUPLICATED_FORMAT_PRODUCTION_FILE_PATH = "packages/app/services/api_client.py"

INCOMPLETE_MOCK_TEST_FILE_PATH = "packages/app/tests/test_orders.py"


def _oversized_function_source(name: str) -> str:
    body_line_count = code_rules_enforcer.FUNCTION_LENGTH_BLOCKING_THRESHOLD - 1
    body_lines = [
        f"    bound_{each_index} = {each_index}" for each_index in range(body_line_count)
    ]
    return f"def {name}() -> None:\n" + "\n".join(body_lines) + "\n"


def test_should_emit_advisories_for_incomplete_mocks_and_format_patterns_via_validate_content(
    capsys: object,
) -> None:
    incomplete_mock_source = (
        "mock_order = {'id': 1}\n"
        "\n"
        "def test_order_total() -> None:\n"
        "    total = mock_order['total']\n"
        "    assert total > 0\n"
    )
    code_rules_enforcer.validate_content(
        incomplete_mock_source, INCOMPLETE_MOCK_TEST_FILE_PATH
    )
    captured = getattr(capsys, "readouterr")()
    assert "mock_order" in captured.err and "total" in captured.err, (
        f"Expected incomplete-mock advisory from validate_content, got: {captured.err!r}"
    )

    repeated_pattern_source = (
        "def get_user(user_id: str) -> str:\n"
        "    return f'/api/{user_id}'\n"
        "\n"
        "def get_order(order_id: str) -> str:\n"
        "    return f'/api/{order_id}'\n"
        "\n"
        "def get_product(product_id: str) -> str:\n"
        "    return f'/api/{product_id}'\n"
    )
    code_rules_enforcer.validate_content(
        repeated_pattern_source, DUPLICATED_FORMAT_PRODUCTION_FILE_PATH
    )
    captured = getattr(capsys, "readouterr")()
    assert "/api/" in captured.err and "3" in captured.err, (
        f"Expected duplicated-format advisory from validate_content, got: {captured.err!r}"
    )


def test_validate_content_honors_empty_full_file_content_for_thin_wrapper_check() -> None:
    """An empty `full_file_content` must not be silently replaced with the pre-edit fragment.

    Regression for loop1-8: the `or` short-circuit at the thin-wrapper call
    site treated `""` identically to `None`, so an Edit collapsing a file to
    empty was scanned against the pre-edit fragment instead of the empty
    post-edit content. Mirror the canonical idiom at line 3438.
    """
    pre_edit_fragment_with_imports_only = (
        "from real_module import do_thing\n__all__ = ['do_thing']\n"
    )
    issues = code_rules_enforcer.validate_content(
        pre_edit_fragment_with_imports_only,
        "/project/src/aliases.py",
        full_file_content="",
    )
    assert not any("thin wrapper" in each.lower() for each in issues), (
        f"empty post-edit file must not be flagged as a thin wrapper, got: {issues!r}"
    )


def test_function_length_edit_does_not_block_untouched_long_function() -> None:
    """loop5-1: editing a short region of a file that already contains an
    untouched oversized function must not produce a blocking function-length
    violation at the PreToolUse layer."""
    untouched_long_function = _oversized_function_source("untouched_long")
    short_helper_before = "def short_helper() -> int:\n    return 1\n"
    short_helper_after = "def short_helper() -> int:\n    return 2\n"
    prior_full_file = untouched_long_function + "\n" + short_helper_before
    post_edit_full_file = untouched_long_function + "\n" + short_helper_after
    issues = code_rules_enforcer.validate_content(
        short_helper_after,
        "/project/src/edited_module.py",
        old_content=short_helper_before,
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )
    assert not any(
        "untouched_long" in each_issue for each_issue in issues
    ), f"untouched long function must not block on an unrelated edit, got: {issues!r}"


def test_function_length_edit_blocks_function_grown_on_changed_lines() -> None:
    """loop5-1: when the edit itself grows a function past the threshold, the
    function-length violation must still block at the PreToolUse layer."""
    short_function_before = "def grows_now() -> int:\n    return 1\n"
    grown_function_after = _oversized_function_source("grows_now")
    prior_full_file = short_function_before
    post_edit_full_file = grown_function_after
    issues = code_rules_enforcer.validate_content(
        grown_function_after,
        "/project/src/edited_module.py",
        old_content=short_function_before,
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )
    assert any(
        "grows_now" in each_issue for each_issue in issues
    ), f"function grown past threshold on changed lines must block, got: {issues!r}"


def test_isolation_edit_does_not_block_untouched_probe() -> None:
    """loop5-3: editing a short region of a test file that already contains an
    untouched HOME probe must not block at the PreToolUse layer."""
    untouched_probe_function = (
        "def test_reads_home() -> None:\n"
        "    target_path = Path.home()\n"
        "    assert target_path\n"
    )
    short_test_before = "def test_addition() -> None:\n    assert 1 + 1 == 2\n"
    short_test_after = "def test_addition() -> None:\n    assert 2 + 2 == 4\n"
    header = "from pathlib import Path\n"
    prior_full_file = header + untouched_probe_function + "\n" + short_test_before
    post_edit_full_file = header + untouched_probe_function + "\n" + short_test_after
    issues = code_rules_enforcer.validate_content(
        short_test_after,
        "/project/src/test_edited_module.py",
        old_content=short_test_before,
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )
    assert not any(
        "test_reads_home" in each_issue for each_issue in issues
    ), f"untouched isolation probe must not block on an unrelated edit, got: {issues!r}"


def test_isolation_edit_blocks_probe_added_on_changed_lines() -> None:
    """loop5-3: when the edit introduces a HOME probe, the isolation violation
    must still block at the PreToolUse layer."""
    test_before = "def test_writes() -> None:\n    assert True\n"
    test_after = (
        "def test_writes() -> None:\n"
        "    target_path = Path.home()\n"
        "    assert target_path\n"
    )
    header = "from pathlib import Path\n"
    prior_full_file = header + test_before
    post_edit_full_file = header + test_after
    issues = code_rules_enforcer.validate_content(
        test_after,
        "/project/src/test_edited_module.py",
        old_content=test_before,
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )
    assert any(
        "test_writes" in each_issue and "Path.home" in each_issue
        for each_issue in issues
    ), f"isolation probe added on changed lines must block, got: {issues!r}"


def test_isolation_edit_blocks_probe_unisolated_by_signature_line_change() -> None:
    """Removing the ``monkeypatch`` fixture from a test's signature line
    un-isolates a HOME probe in its unchanged body; the violation must block
    because the enclosing function's span covers the changed signature line."""
    test_before = (
        "def test_reads_home(monkeypatch) -> None:\n"
        "    target_path = Path.home()\n"
        "    assert target_path\n"
    )
    test_after = (
        "def test_reads_home() -> None:\n"
        "    target_path = Path.home()\n"
        "    assert target_path\n"
    )
    header = "from pathlib import Path\n"
    prior_full_file = header + test_before
    post_edit_full_file = header + test_after
    issues = code_rules_enforcer.validate_content(
        test_after,
        "/project/src/test_edited_module.py",
        old_content=test_before,
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )
    assert any(
        "test_reads_home" in each_issue and "Path.home" in each_issue
        for each_issue in issues
    ), f"signature-line change that un-isolates a probe must block, got: {issues!r}"


def test_function_length_reports_only_in_scope_violation_on_terminal_edit() -> None:
    """A terminal diff-scoped Edit reports only the function whose changed-line
    span grew past the threshold; untouched oversized functions earlier in the
    file are out of scope and dropped, regardless of how many precede it."""
    leading_function_count = 6
    leading_functions = "\n".join(
        _oversized_function_source(f"leading_long_{each_index}")
        for each_index in range(leading_function_count)
    )
    short_target_before = "def target_function() -> int:\n    return 1\n"
    grown_target_after = _oversized_function_source("target_function")
    prior_full_file = leading_functions + "\n" + short_target_before
    post_edit_full_file = leading_functions + "\n" + grown_target_after
    issues = code_rules_enforcer.validate_content(
        grown_target_after,
        "/project/src/many_functions.py",
        old_content=short_target_before,
        full_file_content=post_edit_full_file,
        prior_full_file_content=prior_full_file,
    )
    function_length_issues = [
        each_issue for each_issue in issues if "defined at line" in each_issue
    ]
    assert any(
        "target_function" in each_issue for each_issue in function_length_issues
    ), f"in-scope grown function must still block, got: {issues!r}"
    assert not any(
        "leading_long_" in each_issue for each_issue in function_length_issues
    ), f"untouched functions must stay out of scope, got: {function_length_issues!r}"


def test_new_file_write_reports_every_in_scope_long_function_uncapped() -> None:
    """loop7-bugbot: a new-file Write passes ``all_changed_lines is None``; every
    line was just authored and is in scope, so every long function is reported
    with no ceiling on the count."""
    function_count = 6
    all_functions = "\n".join(
        _oversized_function_source(f"new_long_{each_index}")
        for each_index in range(function_count)
    )
    issues = code_rules_enforcer.validate_content(
        all_functions,
        "/project/src/freshly_written_module.py",
        old_content="",
    )
    function_length_issues = [
        each_issue for each_issue in issues if "defined at line" in each_issue
    ]
    assert len(function_length_issues) == function_count, (
        "every long function in a new file is in scope and must be reported, "
        f"got: {function_length_issues!r}"
    )


def test_new_file_write_reports_every_in_scope_isolation_probe_uncapped() -> None:
    """loop7-bugbot: a new test file Write passes ``all_changed_lines is None``;
    every HOME probe is in scope, so each one is reported with no count ceiling."""
    probe_count = 6
    probing_tests = "".join(
        f"def test_probe_{each_index}() -> None:\n"
        f"    home_dir_{each_index} = Path.home()\n"
        f"    assert home_dir_{each_index}\n"
        for each_index in range(probe_count)
    )
    source = "from pathlib import Path\n" + probing_tests
    issues = code_rules_enforcer.validate_content(
        source,
        "/project/src/test_freshly_written_module.py",
        old_content="",
    )
    home_probe_issues = [
        each_issue for each_issue in issues if "Path.home" in each_issue
    ]
    assert len(home_probe_issues) == probe_count, (
        "every HOME probe in a new test file is in scope and must be reported, "
        f"got: {home_probe_issues!r}"
    )
