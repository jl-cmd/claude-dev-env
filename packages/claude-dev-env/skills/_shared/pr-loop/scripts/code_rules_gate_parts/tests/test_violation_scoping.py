"""Behavioral tests for the violation_scoping parts module."""

from code_rules_gate_parts import violation_scoping


def test_hunk_header_pattern_matches_a_unified_zero_header() -> None:
    match_result = violation_scoping.hunk_header_pattern().match("@@ -1,0 +5,3 @@")
    assert match_result is not None
    assert match_result.group(1) == "5"


def test_violation_line_pattern_extracts_the_line_prefix() -> None:
    match_result = violation_scoping.violation_line_pattern().match("Line 7: issue")
    assert match_result is not None
    assert match_result.group(1) == "7"


def test_parse_added_line_numbers_reads_hunk_headers() -> None:
    diff_text = "@@ -0,0 +3,2 @@\n+alpha\n+beta\n"
    assert violation_scoping.parse_added_line_numbers(diff_text) == {3, 4}


def test_extract_violation_line_number_reads_the_prefix() -> None:
    assert violation_scoping.extract_violation_line_number("Line 9: issue") == 9
    assert violation_scoping.extract_violation_line_number("no prefix") is None


def test_function_length_span_range_covers_the_declared_span() -> None:
    message = "Function 'f' (defined at line 4) is 3 lines - too long"
    assert violation_scoping.function_length_span_range(message) == range(4, 7)


def test_isolation_span_range_covers_enclosing_test() -> None:
    message = "Line 5: Test 'f' (defined at line 4, spanning 3 lines) probes HOME"
    assert violation_scoping.isolation_span_range(message) == range(4, 7)


def test_banned_noun_span_range_is_one_line() -> None:
    message = "Line 8: Identifier 'result' (binding span at line 8, spanning 1 lines)"
    assert violation_scoping.banned_noun_span_range(message) == range(8, 9)


def test_duplicate_body_span_range_covers_copy() -> None:
    message = "Function 'f' duplicates a.py::f — (duplicate body span at line 2, spanning 4 lines)"
    assert violation_scoping.duplicate_body_span_range(message) == range(2, 6)


def test_inline_duplicate_body_span_lines_unions_both_spans() -> None:
    message = (
        "same body (inline duplicate body spans: helper at line 2 spanning 2 lines, "
        "enclosing at line 10 spanning 2 lines)"
    )
    span_lines = violation_scoping.inline_duplicate_body_span_lines(message)
    assert span_lines == frozenset({2, 3, 10, 11})


def test_enclosing_span_range_dispatches_to_first_extractor() -> None:
    message = "Function 'f' (defined at line 4) is 3 lines - too long"
    assert violation_scoping.enclosing_span_range(message) == range(4, 7)


def test_split_violations_by_scope_partitions_by_added_line() -> None:
    blocking, advisory = violation_scoping.split_violations_by_scope(
        ["Line 5: touched", "Line 9: untouched"], {5}
    )
    assert blocking == ["Line 5: touched"]
    assert advisory == ["Line 9: untouched"]


def test_split_violations_by_scope_blocks_everything_when_scope_is_none() -> None:
    blocking, advisory = violation_scoping.split_violations_by_scope(
        ["Line 5: a", "Line 9: b"], None
    )
    assert blocking == ["Line 5: a", "Line 9: b"]
    assert advisory == []
