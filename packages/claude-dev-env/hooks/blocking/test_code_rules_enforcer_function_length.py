"""Tests for ``check_function_length``.

Functions whose definition span (signature line through last body statement,
inclusive) is at or above ``FUNCTION_LENGTH_BLOCKING_THRESHOLD`` (60) block the
write (small-function basis: Robert C. Martin, Clean Code Ch. 3 "Functions";
Google Python Style Guide ~40-line function review hint). Spans below the
threshold pass silently.

Cited SYNTHESIS evidence: pa#143 F4, F9, F14 (three recurrences in one PR);
pa#136 F20.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "code_rules_enforcer",
    _HOOK_DIR / "code_rules_enforcer.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)
check_function_length = hook_module.check_function_length

PRODUCTION_FILE_PATH = "/project/src/long_module.py"
TEST_FILE_PATH = "/project/src/test_long_module.py"
MIGRATION_FILE_PATH = "/project/src/migrations/0001_initial.py"
HOOK_INFRASTRUCTURE_PATH = "/packages/claude-dev-env/hooks/blocking/example.py"


def _build_function_source(name: str, body_line_count: int) -> str:
    body_lines = [
        f"    statement_{each_index} = {each_index}" for each_index in range(body_line_count)
    ]
    body_block = "\n".join(body_lines)
    return f"def {name}() -> None:\n{body_block}\n"


def test_should_not_flag_short_function() -> None:
    source = _build_function_source("compact_helper", body_line_count=5)
    issues = check_function_length(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_not_block_mid_band_function_under_blocking_threshold() -> None:
    body_line_count = hook_module.FUNCTION_LENGTH_BLOCKING_THRESHOLD - 5
    source = _build_function_source("mid_helper", body_line_count=body_line_count)
    issues = check_function_length(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_block_at_sixty_lines() -> None:
    body_line_count = hook_module.FUNCTION_LENGTH_BLOCKING_THRESHOLD - 1
    source = _build_function_source("oversized_helper", body_line_count=body_line_count)
    issues = check_function_length(source, PRODUCTION_FILE_PATH)
    assert any("oversized_helper" in each_issue for each_issue in issues)
    assert any("blocking" in each_issue.lower() for each_issue in issues)


def test_should_not_block_at_fifty_nine_line_span() -> None:
    body_line_count = hook_module.FUNCTION_LENGTH_BLOCKING_THRESHOLD - 2
    source = _build_function_source("boundary_helper", body_line_count=body_line_count)
    issues = check_function_length(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_handle_async_function_definitions() -> None:
    body_line_count = hook_module.FUNCTION_LENGTH_BLOCKING_THRESHOLD - 1
    body_lines = [
        f"    statement_{each_index} = {each_index}" for each_index in range(body_line_count)
    ]
    source = "async def long_async_helper() -> None:\n" + "\n".join(body_lines) + "\n"
    issues = check_function_length(source, PRODUCTION_FILE_PATH)
    assert any("long_async_helper" in each_issue for each_issue in issues)


def test_should_skip_test_files() -> None:
    body_line_count = hook_module.FUNCTION_LENGTH_BLOCKING_THRESHOLD - 1
    source = _build_function_source("test_long_scenario", body_line_count=body_line_count)
    issues = check_function_length(source, TEST_FILE_PATH)
    assert issues == []


def test_should_skip_migrations() -> None:
    body_line_count = hook_module.FUNCTION_LENGTH_BLOCKING_THRESHOLD - 1
    source = _build_function_source("operation_body", body_line_count=body_line_count)
    issues = check_function_length(source, MIGRATION_FILE_PATH)
    assert issues == []


def test_should_skip_hook_infrastructure() -> None:
    body_line_count = hook_module.FUNCTION_LENGTH_BLOCKING_THRESHOLD - 1
    source = _build_function_source("hook_helper", body_line_count=body_line_count)
    issues = check_function_length(source, HOOK_INFRASTRUCTURE_PATH)
    assert issues == []


def test_should_skip_when_source_does_not_parse() -> None:
    source = "def broken(:\n"
    issues = check_function_length(source, PRODUCTION_FILE_PATH)
    assert issues == []


def test_edit_drops_every_out_of_scope_long_function() -> None:
    """An edit that touches none of the oversized functions reports nothing —
    every violation is out of scope (untouched code must not block a single-file
    edit)."""
    body_line_count = hook_module.FUNCTION_LENGTH_BLOCKING_THRESHOLD - 1
    body_lines = [
        f"    statement_{each_index} = {each_index}" for each_index in range(body_line_count)
    ]
    body_block = "\n".join(body_lines)
    function_count = 8
    chunks = [
        f"def f_{each_index}() -> None:\n{body_block}\n" for each_index in range(function_count)
    ]
    source = "\n".join(chunks)
    untouched_line_far_outside_any_span = 100000
    issues = check_function_length(
        source,
        PRODUCTION_FILE_PATH,
        all_changed_lines={untouched_line_far_outside_any_span},
    )
    assert issues == []


def test_new_file_reports_every_long_function_uncapped() -> None:
    """On a new file (``all_changed_lines is None``) every line is in scope, so
    every long function is reported with no ceiling on the count."""
    body_line_count = hook_module.FUNCTION_LENGTH_BLOCKING_THRESHOLD - 1
    body_lines = [
        f"    statement_{each_index} = {each_index}" for each_index in range(body_line_count)
    ]
    body_block = "\n".join(body_lines)
    function_count = 8
    chunks = [
        f"def f_{each_index}() -> None:\n{body_block}\n" for each_index in range(function_count)
    ]
    source = "\n".join(chunks)
    issues = check_function_length(source, PRODUCTION_FILE_PATH)
    assert len(issues) == function_count


def test_should_block_nested_function_over_blocking_threshold() -> None:
    body_line_count = hook_module.FUNCTION_LENGTH_BLOCKING_THRESHOLD - 1
    inner_body = "\n".join(
        f"        inner_statement_{each_index} = {each_index}"
        for each_index in range(body_line_count)
    )
    source = f"def outer() -> None:\n    def inner() -> None:\n{inner_body}\n"
    issues = check_function_length(source, PRODUCTION_FILE_PATH)
    assert any("inner" in each_issue for each_issue in issues)


def test_blocking_message_does_not_cite_file_length_section() -> None:
    assert "6.5" not in hook_module.FUNCTION_LENGTH_BLOCKING_MESSAGE_SUFFIX
    assert "Clean Code" in hook_module.FUNCTION_LENGTH_BLOCKING_MESSAGE_SUFFIX


def _oversized_source(name: str) -> str:
    return _build_function_source(
        name, body_line_count=hook_module.FUNCTION_LENGTH_BLOCKING_THRESHOLD - 1
    )


def test_changed_lines_scope_skips_untouched_long_function() -> None:
    """loop5-1: with changed_lines naming only the short helper, an untouched
    oversized function above it must not appear in the issues."""
    untouched_long = _oversized_source("untouched_long")
    short_helper = "def short_helper() -> int:\n    return 2\n"
    full_source = untouched_long + "\n" + short_helper
    short_helper_line = len(full_source.splitlines())
    issues = check_function_length(
        full_source, PRODUCTION_FILE_PATH, all_changed_lines={short_helper_line}
    )
    assert issues == [], f"untouched long function must not be in scope, got: {issues!r}"


def test_changed_lines_scope_keeps_touched_long_function() -> None:
    """loop5-1: when a changed line falls inside the oversized function's span,
    the violation must remain in the issues."""
    long_function = _oversized_source("grows_now")
    issues = check_function_length(
        long_function, PRODUCTION_FILE_PATH, all_changed_lines={2}
    )
    assert any("grows_now" in each_issue for each_issue in issues)


def test_reports_only_in_scope_violation_among_untouched_ones() -> None:
    """loop5-2: an in-scope violation appearing after several untouched
    out-of-scope violations is still reported, while the untouched ones stay out
    of scope."""
    leading_count = 5
    leading = "\n".join(_oversized_source(f"leading_{each_index}") for each_index in range(leading_count))
    target = _oversized_source("target_function")
    full_source = leading + "\n" + target
    target_definition_line = len(leading.splitlines()) + 2
    issues = check_function_length(
        full_source, PRODUCTION_FILE_PATH, all_changed_lines={target_definition_line}
    )
    assert any("target_function" in each_issue for each_issue in issues)
    assert not any("leading_" in each_issue for each_issue in issues)
