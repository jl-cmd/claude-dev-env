"""Behavioral tests for the path_classification parts module."""

from tdd_enforcer_parts import path_classification


def test_production_extensions_includes_python_and_typescript() -> None:
    extensions = path_classification.production_extensions()
    assert ".py" in extensions
    assert ".tsx" in extensions


def test_skip_extensions_includes_markdown_and_json() -> None:
    extensions = path_classification.skip_extensions()
    assert ".md" in extensions
    assert ".json" in extensions


def test_is_inside_dotclaude_segment_matches_exact_segment_only() -> None:
    assert path_classification._is_inside_dotclaude_segment("/home/user/.claude/agent.py") is True
    assert path_classification._is_inside_dotclaude_segment("/src/my.claude.helpers.py") is False


def test_matches_any_skip_pattern_flags_test_file_names() -> None:
    assert (
        path_classification._matches_any_skip_pattern("test_orders.py", "pkg/test_orders.py")
        is True
    )
    assert path_classification._matches_any_skip_pattern("orders.py", "pkg/orders.py") is False


def test_extract_written_content_reads_write_and_multiedit() -> None:
    assert path_classification._extract_written_content("Write", {"content": "x"}) == "x"
    joined = path_classification._extract_written_content(
        "MultiEdit", {"edits": [{"new_string": "a"}, {"new_string": "b"}]}
    )
    assert joined == "a\nb"
