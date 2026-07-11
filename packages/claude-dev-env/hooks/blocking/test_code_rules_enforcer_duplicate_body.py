"""Tests for cross-file duplicate top-level function body detection.

PR #567 added the 5th and 6th copies of a byte-identical ``strip_code_and_quotes``
helper across sibling Stop-hook modules. This check blocks that violation class at
Write time: a top-level function whose body matches a top-level function in a
sibling ``.py`` module in the same directory is flagged so the author extracts one
shared helper instead of copying it.

The tests write real sibling files into a neutrally named temporary directory and
run the check against them, so they exercise the on-disk directory scan rather
than a stubbed view of the filesystem. The directory is named like a production
package directory (no ``test_`` segment), because the check treats any path
containing a test marker as exempt — the same way it would skip a real test file.
"""

from __future__ import annotations

import importlib.util
import pathlib
import shutil
import sys
import tempfile
from collections.abc import Iterator

import pytest

_HOOK_DIRECTORY = pathlib.Path(__file__).parent
if str(_HOOK_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIRECTORY))

_hook_spec = importlib.util.spec_from_file_location(
    "code_rules_enforcer",
    _HOOK_DIRECTORY / "code_rules_enforcer.py",
)
assert _hook_spec is not None
assert _hook_spec.loader is not None
_hook_module = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(_hook_module)
check_duplicate_function_body_across_files = _hook_module.check_duplicate_function_body_across_files


SHARED_HELPER_SOURCE = (
    "import re\n"
    "\n"
    "def strip_code_and_quotes(text: str) -> str:\n"
    "    without_fences = re.sub(r'```.*?```', '', text, flags=re.DOTALL)\n"
    "    without_inline = re.sub(r'`[^`]*`', '', without_fences)\n"
    "    without_quotes = re.sub(r'(?m)^>.*$', '', without_inline)\n"
    "    return without_quotes.strip()\n"
)


@pytest.fixture
def module_dir() -> Iterator[pathlib.Path]:
    base_directory = pathlib.Path(tempfile.mkdtemp())
    package_directory = base_directory / "blocking"
    package_directory.mkdir()
    try:
        yield package_directory
    finally:
        shutil.rmtree(base_directory, ignore_errors=False)


def _write(directory: pathlib.Path, name: str, source: str) -> pathlib.Path:
    target = directory / name
    target.write_text(source, encoding="utf-8")
    return target


def test_should_flag_function_copied_from_sibling(module_dir: pathlib.Path) -> None:
    _write(module_dir, "existing_blocker.py", SHARED_HELPER_SOURCE)
    new_file = module_dir / "new_blocker.py"
    issues = check_duplicate_function_body_across_files(SHARED_HELPER_SOURCE, str(new_file))
    assert any("strip_code_and_quotes" in each_issue for each_issue in issues), (
        f"Expected the copied helper to be flagged, got: {issues}"
    )
    assert any("existing_blocker.py" in each_issue for each_issue in issues), (
        f"Expected the sibling source location named, got: {issues}"
    )


def test_should_not_flag_when_no_sibling_matches(module_dir: pathlib.Path) -> None:
    _write(
        module_dir,
        "unrelated.py",
        "def add(left: int, right: int) -> int:\n"
        "    total = left + right\n"
        "    doubled = total * 2\n"
        "    return doubled\n",
    )
    new_file = module_dir / "new_blocker.py"
    issues = check_duplicate_function_body_across_files(SHARED_HELPER_SOURCE, str(new_file))
    assert issues == [], f"No matching sibling body must not flag, got: {issues}"


def test_should_not_flag_trivial_short_body(module_dir: pathlib.Path) -> None:
    trivial_source = "def noop() -> None:\n    return None\n"
    _write(module_dir, "existing.py", trivial_source)
    new_file = module_dir / "new.py"
    issues = check_duplicate_function_body_across_files(trivial_source, str(new_file))
    assert issues == [], (
        f"A body under the minimum statement count is too common to flag, got: {issues}"
    )


def test_should_ignore_docstring_only_difference(module_dir: pathlib.Path) -> None:
    with_docstring = (
        "def compute(left: int, right: int) -> int:\n"
        '    """Add then scale."""\n'
        "    total = left + right\n"
        "    scaled = total * 3\n"
        "    return scaled\n"
    )
    without_docstring = (
        "def compute(left: int, right: int) -> int:\n"
        "    total = left + right\n"
        "    scaled = total * 3\n"
        "    return scaled\n"
    )
    _write(module_dir, "existing.py", with_docstring)
    new_file = module_dir / "new.py"
    issues = check_duplicate_function_body_across_files(without_docstring, str(new_file))
    assert any("compute" in each_issue for each_issue in issues), (
        f"A docstring-only difference must not hide the duplicate, got: {issues}"
    )


def test_should_skip_test_file_being_written(module_dir: pathlib.Path) -> None:
    _write(module_dir, "existing.py", SHARED_HELPER_SOURCE)
    test_file = module_dir / "test_new.py"
    issues = check_duplicate_function_body_across_files(SHARED_HELPER_SOURCE, str(test_file))
    assert issues == [], f"Test files are exempt on the writing side, got: {issues}"


def test_should_skip_test_file_siblings(module_dir: pathlib.Path) -> None:
    _write(module_dir, "test_existing.py", SHARED_HELPER_SOURCE)
    new_file = module_dir / "new_blocker.py"
    issues = check_duplicate_function_body_across_files(SHARED_HELPER_SOURCE, str(new_file))
    assert issues == [], (
        f"A matching body in a sibling test file must not flag production code, got: {issues}"
    )


def test_should_skip_dunder_init_being_written(module_dir: pathlib.Path) -> None:
    _write(module_dir, "existing.py", SHARED_HELPER_SOURCE)
    init_file = module_dir / "__init__.py"
    issues = check_duplicate_function_body_across_files(SHARED_HELPER_SOURCE, str(init_file))
    assert issues == [], f"__init__.py re-export surfaces are exempt, got: {issues}"


def test_should_not_compare_against_self(module_dir: pathlib.Path) -> None:
    existing = _write(module_dir, "blocker.py", SHARED_HELPER_SOURCE)
    issues = check_duplicate_function_body_across_files(SHARED_HELPER_SOURCE, str(existing))
    assert issues == [], (
        f"A file must not be flagged as a duplicate of its own on-disk copy, got: {issues}"
    )


def test_should_return_empty_on_syntax_error(module_dir: pathlib.Path) -> None:
    _write(module_dir, "existing.py", SHARED_HELPER_SOURCE)
    new_file = module_dir / "broken.py"
    issues = check_duplicate_function_body_across_files("def broken(\n", str(new_file))
    assert issues == [], f"Unparseable content must return empty, got: {issues}"


def test_should_skip_unparseable_sibling(module_dir: pathlib.Path) -> None:
    _write(module_dir, "broken_sibling.py", "def broken(\n")
    _write(module_dir, "good_sibling.py", SHARED_HELPER_SOURCE)
    new_file = module_dir / "new.py"
    issues = check_duplicate_function_body_across_files(SHARED_HELPER_SOURCE, str(new_file))
    assert any("good_sibling.py" in each_issue for each_issue in issues), (
        f"A broken sibling must be skipped without hiding a real match, got: {issues}"
    )


def test_should_not_flag_method_inside_class(module_dir: pathlib.Path) -> None:
    class_source = (
        "class Worker:\n"
        "    def run(self, left: int, right: int) -> int:\n"
        "        total = left + right\n"
        "        scaled = total * 4\n"
        "        return scaled\n"
    )
    _write(module_dir, "existing.py", class_source)
    new_file = module_dir / "new.py"
    issues = check_duplicate_function_body_across_files(class_source, str(new_file))
    assert issues == [], f"Only module-scope functions are compared, not methods, got: {issues}"


_UNRELATED_LEADING_FUNCTION = (
    "def unrelated_helper(left: int, right: int) -> int:\n"
    "    summed = left + right\n"
    "    tripled = summed * 3\n"
    "    return tripled\n"
)


def test_should_not_flag_when_edit_leaves_duplicate_outside_changed_lines(
    module_dir: pathlib.Path,
) -> None:
    _write(module_dir, "existing.py", SHARED_HELPER_SOURCE)
    new_file = module_dir / "new_blocker.py"
    post_edit_content = _UNRELATED_LEADING_FUNCTION + "\n\n" + SHARED_HELPER_SOURCE
    changed_lines_outside_duplicate = {1, 2, 3, 4}
    issues = check_duplicate_function_body_across_files(
        post_edit_content,
        str(new_file),
        all_changed_lines=changed_lines_outside_duplicate,
    )
    assert issues == [], (
        "An Edit that never touches the duplicated function must not block, "
        f"got: {issues}"
    )


def test_should_flag_when_edit_changed_lines_intersect_duplicate(
    module_dir: pathlib.Path,
) -> None:
    _write(module_dir, "existing.py", SHARED_HELPER_SOURCE)
    new_file = module_dir / "new_blocker.py"
    post_edit_content = _UNRELATED_LEADING_FUNCTION + "\n\n" + SHARED_HELPER_SOURCE
    duplicate_definition_line = post_edit_content.splitlines().index(
        "def strip_code_and_quotes(text: str) -> str:"
    ) + 1
    changed_lines_inside_duplicate = {duplicate_definition_line + 1}
    issues = check_duplicate_function_body_across_files(
        post_edit_content,
        str(new_file),
        all_changed_lines=changed_lines_inside_duplicate,
    )
    assert any("strip_code_and_quotes" in each_issue for each_issue in issues), (
        "An Edit whose changed lines touch the copied helper must still flag, "
        f"got: {issues}"
    )


def test_should_flag_whole_file_write_when_changed_lines_is_none(
    module_dir: pathlib.Path,
) -> None:
    _write(module_dir, "existing.py", SHARED_HELPER_SOURCE)
    new_file = module_dir / "new_blocker.py"
    issues = check_duplicate_function_body_across_files(
        SHARED_HELPER_SOURCE,
        str(new_file),
        all_changed_lines=None,
    )
    assert any("strip_code_and_quotes" in each_issue for each_issue in issues), (
        "A whole-file Write treats every line as in scope and must flag, "
        f"got: {issues}"
    )


def test_should_scan_explicit_sibling_directory_for_relative_path(
    module_dir: pathlib.Path,
) -> None:
    _write(module_dir, "existing_blocker.py", SHARED_HELPER_SOURCE)
    issues = check_duplicate_function_body_across_files(
        SHARED_HELPER_SOURCE,
        "package/new_blocker.py",
        sibling_directory=module_dir,
    )
    assert any("strip_code_and_quotes" in each_issue for each_issue in issues), (
        "When given an explicit sibling directory, the check must scan it for a "
        f"relative file_path rather than the path's CWD-relative parent, got: {issues}"
    )
    assert any("existing_blocker.py" in each_issue for each_issue in issues), (
        f"Expected the sibling source location named, got: {issues}"
    )


def test_should_ignore_cwd_when_explicit_sibling_directory_given(
    module_dir: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(module_dir, "existing_blocker.py", SHARED_HELPER_SOURCE)
    monkeypatch.chdir(module_dir.parent)
    issues = check_duplicate_function_body_across_files(
        SHARED_HELPER_SOURCE,
        "package/new_blocker.py",
        sibling_directory=module_dir,
    )
    assert any("strip_code_and_quotes" in each_issue for each_issue in issues), (
        "An explicit sibling directory must anchor the scan independent of the "
        f"process working directory, got: {issues}"
    )


def test_should_return_every_violation_when_scope_deferred_to_caller(
    module_dir: pathlib.Path,
) -> None:
    _write(module_dir, "existing.py", SHARED_HELPER_SOURCE)
    new_file = module_dir / "new_blocker.py"
    post_edit_content = _UNRELATED_LEADING_FUNCTION + "\n\n" + SHARED_HELPER_SOURCE
    changed_lines_outside_duplicate = {1, 2, 3, 4}
    issues = check_duplicate_function_body_across_files(
        post_edit_content,
        str(new_file),
        all_changed_lines=changed_lines_outside_duplicate,
        defer_scope_to_caller=True,
    )
    assert any("strip_code_and_quotes" in each_issue for each_issue in issues), (
        "The commit/push gate scopes by added line, so the check must return "
        f"every violation when scope is deferred, got: {issues}"
    )


def test_should_carry_a_parseable_span_for_the_commit_gate_scoper(
    module_dir: pathlib.Path,
) -> None:
    _write(module_dir, "existing.py", SHARED_HELPER_SOURCE)
    new_file = module_dir / "new_blocker.py"
    post_edit_content = _UNRELATED_LEADING_FUNCTION + "\n\n" + SHARED_HELPER_SOURCE
    duplicate_definition_line = post_edit_content.splitlines().index(
        "def strip_code_and_quotes(text: str) -> str:"
    ) + 1
    issues = check_duplicate_function_body_across_files(
        post_edit_content,
        str(new_file),
        all_changed_lines=None,
        defer_scope_to_caller=True,
    )
    matching_issues = [
        each_issue for each_issue in issues if "strip_code_and_quotes" in each_issue
    ]
    assert matching_issues, f"expected a duplicate-body issue, got: {issues}"
    expected_fragment = f"(duplicate body span at line {duplicate_definition_line}, spanning 5 lines)"
    assert expected_fragment in matching_issues[0], (
        "The commit gate's scope splitter parses the copied function's span from "
        f"the message, so the message must carry it, got: {matching_issues[0]}"
    )
