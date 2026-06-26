"""Tests for check_docstring_punctuation_mark_enumeration_coverage — O6 glyph drift.

A module defines a tuple of punctuation-mark glyphs (an em-dash, a spaced
double-hyphen, a semicolon) and a docstring enumerates those marks by their
English names while omitting one the tuple holds. The prose names two marks but
the detection set holds three, so a reader who trusts the enumeration believes a
mark that is active never triggers the check. This is the deterministic
glyph-prose slice of Category O6 docstring-prose-vs-implementation drift, the
companion to check_docstring_tuple_enumeration_match for glyph members named in
prose rather than identifier members named in inline code.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_enforcer_module() -> ModuleType:
    module_path = Path(__file__).parent / "code_rules_enforcer.py"
    spec = importlib.util.spec_from_file_location("code_rules_enforcer", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


code_rules_enforcer = _load_enforcer_module()


def check_docstring_punctuation_mark_enumeration_coverage(
    content: str, file_path: str
) -> list[str]:
    return code_rules_enforcer.check_docstring_punctuation_mark_enumeration_coverage(
        content, file_path
    )


def validate_content(content: str, file_path: str, old_content: str) -> list[str]:
    return code_rules_enforcer.validate_content(content, file_path, old_content)


PRODUCTION_FILE_PATH = "/project/src/runon_detector.py"
TEST_FILE_PATH = "/project/src/test_runon_detector.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/code_rules_docstrings.py"


def _drifted_two_marks_named_function() -> str:
    return (
        'ALL_RUNON_JOINER_MARKERS = ("—", " -- ", ";")\n'
        "\n"
        "\n"
        "def _sentence_carries_joiner(sentence_text: str) -> bool:\n"
        '    """Report whether the sentence chains clauses with a joiner mark.\n'
        "\n"
        "    The run-on marks are an em-dash or a semicolon, the two glyphs that\n"
        "    fuse independent clauses into one dense sentence.\n"
        '    """\n'
        "    return any(each in sentence_text for each in ALL_RUNON_JOINER_MARKERS)\n"
    )


def _complete_three_marks_named_function() -> str:
    return (
        'ALL_RUNON_JOINER_MARKERS = ("—", " -- ", ";")\n'
        "\n"
        "\n"
        "def _sentence_carries_joiner(sentence_text: str) -> bool:\n"
        '    """Report whether the sentence chains clauses with a joiner mark.\n'
        "\n"
        "    The run-on marks are an em-dash, a spaced double-hyphen, or a\n"
        "    semicolon, the glyphs that fuse independent clauses into one\n"
        "    dense sentence.\n"
        '    """\n'
        "    return any(each in sentence_text for each in ALL_RUNON_JOINER_MARKERS)\n"
    )


def _single_mark_named_function() -> str:
    return (
        'ALL_RUNON_JOINER_MARKERS = ("—", " -- ", ";")\n'
        "\n"
        "\n"
        "def _sentence_carries_joiner(sentence_text: str) -> bool:\n"
        '    """Report whether the sentence chains clauses with an em-dash.\n'
        "\n"
        "    The em-dash is the glyph that fuses clauses into one sentence.\n"
        '    """\n'
        "    return any(each in sentence_text for each in ALL_RUNON_JOINER_MARKERS)\n"
    )


def _non_glyph_tuple_function() -> str:
    return (
        'ALL_OUTCOME_LABELS = ("alpha", "beta", "gamma")\n'
        "\n"
        "\n"
        "def describe_outcome(label_text: str) -> bool:\n"
        '    """Report the outcome named by an em-dash or a semicolon label.\n'
        "\n"
        "    The labels carry a semicolon between the segments of each name.\n"
        '    """\n'
        "    return label_text in ALL_OUTCOME_LABELS\n"
    )


def test_should_flag_omitted_double_hyphen_mark() -> None:
    issues = check_docstring_punctuation_mark_enumeration_coverage(
        _drifted_two_marks_named_function(), PRODUCTION_FILE_PATH
    )
    assert any("--" in each for each in issues), (
        f"The docstring naming em-dash and semicolon but omitting the double-hyphen "
        f"that ALL_RUNON_JOINER_MARKERS holds must be flagged, got: {issues!r}"
    )


def test_should_report_category_o6_in_the_message() -> None:
    issues = check_docstring_punctuation_mark_enumeration_coverage(
        _drifted_two_marks_named_function(), PRODUCTION_FILE_PATH
    )
    assert any("O6" in each for each in issues), (
        f"Expected the Category O6 label in the message, got: {issues!r}"
    )


def test_should_not_flag_complete_enumeration() -> None:
    issues = check_docstring_punctuation_mark_enumeration_coverage(
        _complete_three_marks_named_function(), PRODUCTION_FILE_PATH
    )
    assert issues == [], f"A docstring naming all three marks must not be flagged, got: {issues!r}"


def test_should_not_flag_single_named_mark_below_threshold() -> None:
    issues = check_docstring_punctuation_mark_enumeration_coverage(
        _single_mark_named_function(), PRODUCTION_FILE_PATH
    )
    assert issues == [], f"A docstring naming a single mark is not an enumeration, got: {issues!r}"


def test_should_not_flag_non_glyph_tuple() -> None:
    issues = check_docstring_punctuation_mark_enumeration_coverage(
        _non_glyph_tuple_function(), PRODUCTION_FILE_PATH
    )
    assert issues == [], f"A tuple of non-punctuation members must not be flagged, got: {issues!r}"


def test_should_flag_on_hook_infrastructure_where_the_drift_lives() -> None:
    issues = check_docstring_punctuation_mark_enumeration_coverage(
        _drifted_two_marks_named_function(), HOOK_INFRASTRUCTURE_PATH
    )
    assert any("--" in each for each in issues), (
        f"The drift lives in hook modules, so the gate must run there, got: {issues!r}"
    )


def test_should_skip_test_file() -> None:
    issues = check_docstring_punctuation_mark_enumeration_coverage(
        _drifted_two_marks_named_function(), TEST_FILE_PATH
    )
    assert issues == [], f"Test files exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    unparseable_naming_marks = 'def fetch(\n    """An em-dash and a semicolon."""\n'
    issues = check_docstring_punctuation_mark_enumeration_coverage(
        unparseable_naming_marks, PRODUCTION_FILE_PATH
    )
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def _drifted_annotated_tuple_function() -> str:
    return (
        'ALL_RUNON_JOINER_MARKERS: tuple[str, ...] = ("—", " -- ", ";")\n'
        "\n"
        "\n"
        "def _sentence_carries_joiner(sentence_text: str) -> bool:\n"
        '    """Report whether the sentence chains clauses with a joiner mark.\n'
        "\n"
        "    The run-on marks are an em-dash or a semicolon.\n"
        '    """\n'
        "    return any(each in sentence_text for each in ALL_RUNON_JOINER_MARKERS)\n"
    )


def test_should_flag_annotated_same_module_tuple_drift() -> None:
    issues = check_docstring_punctuation_mark_enumeration_coverage(
        _drifted_annotated_tuple_function(), PRODUCTION_FILE_PATH
    )
    assert any("--" in each for each in issues), (
        f"An annotated marker tuple in the same module must be checked, got: {issues!r}"
    )


def test_should_flag_drift_against_imported_companion_tuple(tmp_path: Path) -> None:
    companion_directory = tmp_path / "marks_package"
    companion_directory.mkdir()
    (companion_directory / "joiner_marks.py").write_text(
        'ALL_RUNON_JOINER_MARKERS: tuple[str, ...] = ("—", " -- ", ";")\n',
        encoding="utf-8",
    )
    consumer_directory = tmp_path / "blocking"
    consumer_directory.mkdir()
    consumer_source = (
        "from marks_package.joiner_marks import ALL_RUNON_JOINER_MARKERS\n"
        "\n"
        "\n"
        "def _sentence_carries_joiner(sentence_text: str) -> bool:\n"
        '    """Report whether the sentence chains clauses with a joiner mark.\n'
        "\n"
        "    The run-on marks are an em-dash or a semicolon, the two glyphs that\n"
        "    fuse independent clauses into one dense sentence.\n"
        '    """\n'
        "    return any(each in sentence_text for each in ALL_RUNON_JOINER_MARKERS)\n"
    )
    consumer_path = consumer_directory / "runon_consumer.py"
    consumer_path.write_text(consumer_source, encoding="utf-8")
    issues = check_docstring_punctuation_mark_enumeration_coverage(
        consumer_source, str(consumer_path)
    )
    assert any("--" in each for each in issues), (
        f"A docstring drifting from an imported companion marker tuple must be "
        f"flagged so the split-file shape is caught, got: {issues!r}"
    )


def test_should_not_resolve_companion_when_no_marks_named(tmp_path: Path) -> None:
    companion_directory = tmp_path / "marks_package"
    companion_directory.mkdir()
    (companion_directory / "joiner_marks.py").write_text(
        'ALL_RUNON_JOINER_MARKERS: tuple[str, ...] = ("—", " -- ", ";")\n',
        encoding="utf-8",
    )
    consumer_directory = tmp_path / "blocking"
    consumer_directory.mkdir()
    consumer_source = (
        "from marks_package.joiner_marks import ALL_RUNON_JOINER_MARKERS\n"
        "\n"
        "\n"
        "def _sentence_carries_joiner(sentence_text: str) -> bool:\n"
        '    """Report whether the sentence carries any joiner glyph."""\n'
        "    return any(each in sentence_text for each in ALL_RUNON_JOINER_MARKERS)\n"
    )
    consumer_path = consumer_directory / "runon_consumer.py"
    consumer_path.write_text(consumer_source, encoding="utf-8")
    issues = check_docstring_punctuation_mark_enumeration_coverage(
        consumer_source, str(consumer_path)
    )
    assert issues == [], (
        f"A docstring naming no marks must not be flagged, got: {issues!r}"
    )


def test_validate_content_surfaces_mark_glyph_drift() -> None:
    issues = validate_content(
        _drifted_two_marks_named_function(), PRODUCTION_FILE_PATH, old_content=""
    )
    matching_issues = [each for each in issues if "--" in each and "O6" in each]
    assert matching_issues, (
        f"Expected validate_content to surface the O6 mark-glyph drift, got: {issues!r}"
    )
