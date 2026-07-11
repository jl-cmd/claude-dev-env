"""Unit tests for the orphan-CSS-class check in code_rules_enforcer hook."""

import importlib.util
import pathlib
import sys
import tempfile
import textwrap
from collections.abc import Iterator
from pathlib import Path

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "code_rules_orphan_css_class",
    _HOOK_DIR / "code_rules_orphan_css_class.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)
check_orphan_css_classes = hook_module.check_orphan_css_classes

PRODUCTION_FILE_PATH = "packages/app/render/report.py"
TEST_FILE_PATH = "packages/app/render/test_report.py"

MARKUP_WITH_ORPHAN = (
    "def render() -> str:\n"
    '    style = "<style>.card { color: red; }</style>"\n'
    '    body = \'<div class="card">x</div><div class="ghost">y</div>\'\n'
    "    return style + body\n"
)

MARKUP_ALL_DEFINED = (
    "def render() -> str:\n"
    '    style = "<style>.card { color: red; } .row { margin: 0; }</style>"\n'
    '    body = \'<div class="card"><span class="row">x</span></div>\'\n'
    "    return style + body\n"
)


def test_should_flag_class_with_no_matching_selector() -> None:
    issues = check_orphan_css_classes(MARKUP_WITH_ORPHAN, PRODUCTION_FILE_PATH)
    assert any("'ghost'" in each_issue for each_issue in issues), (
        f"Expected 'ghost' flagged as orphan, got: {issues}"
    )


def test_should_not_flag_class_with_matching_selector() -> None:
    issues = check_orphan_css_classes(MARKUP_WITH_ORPHAN, PRODUCTION_FILE_PATH)
    assert not any("'card'" in each_issue for each_issue in issues), (
        f"'card' has a .card selector and must not flag, got: {issues}"
    )


def test_should_not_flag_when_every_class_is_defined() -> None:
    issues = check_orphan_css_classes(MARKUP_ALL_DEFINED, PRODUCTION_FILE_PATH)
    assert issues == [], f"Every class is defined; expected no issues, got: {issues}"


def test_should_flag_each_class_in_a_multi_class_attribute() -> None:
    content = (
        "def render() -> str:\n"
        '    style = "<style>.pf { padding: 0; }</style>"\n'
        "    body = '<div class=\"pf problem\">x</div>'\n"
        "    return style + body\n"
    )
    issues = check_orphan_css_classes(content, PRODUCTION_FILE_PATH)
    assert any("'problem'" in each_issue for each_issue in issues), (
        f"Second class 'problem' in the attribute must flag, got: {issues}"
    )
    assert not any("'pf'" in each_issue for each_issue in issues), (
        f"First class 'pf' has a selector and must not flag, got: {issues}"
    )


def test_should_not_flag_when_no_style_block_present() -> None:
    content = "def render() -> str:\n    return '<div class=\"card\">x</div>'\n"
    issues = check_orphan_css_classes(content, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"No <style> source nearby; the stylesheet lives outside the scan, got: {issues}"
    )


def test_should_not_flag_when_no_class_attribute_present() -> None:
    content = (
        'def render() -> str:\n    return "<style>.card { color: red; }</style><div>x</div>"\n'
    )
    issues = check_orphan_css_classes(content, PRODUCTION_FILE_PATH)
    assert issues == [], f"No class attribute in markup; got: {issues}"


def test_should_skip_test_files() -> None:
    issues = check_orphan_css_classes(MARKUP_WITH_ORPHAN, TEST_FILE_PATH)
    assert issues == [], f"Test files are exempt; got: {issues}"


def test_should_include_line_number_and_class_name() -> None:
    issues = check_orphan_css_classes(MARKUP_WITH_ORPHAN, PRODUCTION_FILE_PATH)
    orphan_issue = next(each for each in issues if "'ghost'" in each)
    assert "Line 3" in orphan_issue, (
        f"Orphan 'ghost' sits on line 3 of the markup; got: {orphan_issue}"
    )


def test_should_report_each_orphan_class_once() -> None:
    content = (
        "def render() -> str:\n"
        '    style = "<style>.card { color: red; }</style>"\n'
        "    a = '<div class=\"ghost\">x</div>'\n"
        "    b = '<div class=\"ghost\">y</div>'\n"
        "    return style + a + b\n"
    )
    issues = check_orphan_css_classes(content, PRODUCTION_FILE_PATH)
    ghost_issues = [each for each in issues if "'ghost'" in each]
    assert len(ghost_issues) == 1, f"A repeated orphan class reports once; got: {ghost_issues}"


def test_should_handle_syntax_error_gracefully() -> None:
    content = "def broken(\n    this is not python\n"
    issues = check_orphan_css_classes(content, PRODUCTION_FILE_PATH)
    assert issues == [], f"A syntax error yields no issues; got: {issues}"


_SIBLING_MARKUP_SOURCE = textwrap.dedent(
    """\
    from report_constants import HTML_STYLE_BLOCK


    def render() -> str:
        body = (
            '<details class="appendix">'
            '<div class="appendix-body">x</div></details>'
        )
        return HTML_STYLE_BLOCK + body
    """
)


@pytest.fixture
def production_render_package() -> Iterator[Path]:
    """Yield a neutrally named package directory for the markup and constants modules.

    pytest's ``tmp_path`` carries the test function name, so any path under it
    holds a ``test_`` segment that the enforcer's ``is_test_file`` predicate
    matches and exempts. A package created under the default ``tempfile`` prefix
    keeps that segment out of the path, so the cross-module orphan-class check
    runs against the markup module as production code.

    Yields:
        A freshly created package directory, removed when the test finishes.
    """
    with tempfile.TemporaryDirectory() as base_directory:
        package_directory = Path(base_directory) / "render"
        package_directory.mkdir()
        yield package_directory


def test_should_resolve_selectors_from_a_sibling_module(
    production_render_package: Path,
) -> None:
    constants_module = production_render_package / "report_constants.py"
    constants_module.write_text(
        'HTML_STYLE_BLOCK = "<style>.appendix { margin: 0; }'
        ' .appendix-body { padding: 0; }</style>"\n',
        encoding="utf-8",
    )
    markup_module = production_render_package / "report.py"
    markup_module.write_text(_SIBLING_MARKUP_SOURCE, encoding="utf-8")
    issues = check_orphan_css_classes(_SIBLING_MARKUP_SOURCE, str(markup_module))
    assert issues == [], (
        f"A sibling module defines every selector; expected no issues, got: {issues}"
    )


def test_should_flag_orphan_even_when_a_sibling_defines_other_selectors(
    production_render_package: Path,
) -> None:
    constants_module = production_render_package / "report_constants.py"
    constants_module.write_text(
        'HTML_STYLE_BLOCK = "<style>.appendix { margin: 0; }</style>"\n',
        encoding="utf-8",
    )
    markup_module = production_render_package / "report.py"
    markup_module.write_text(_SIBLING_MARKUP_SOURCE, encoding="utf-8")
    issues = check_orphan_css_classes(_SIBLING_MARKUP_SOURCE, str(markup_module))
    assert any("'appendix-body'" in each_issue for each_issue in issues), (
        f"'appendix-body' has no selector in any sibling; must flag, got: {issues}"
    )
    assert not any(
        "'appendix'" in each_issue and "appendix-body" not in each_issue
        for each_issue in issues
    ), f"'appendix' is defined in the sibling and must not flag, got: {issues}"
