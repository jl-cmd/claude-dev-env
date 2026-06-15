"""Orphan-CSS-class check: class attributes in markup with no matching selector."""

import ast
import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from code_rules_shared import (  # noqa: E402
    is_test_file,
)

from hooks_constants.orphan_css_class_constants import (  # noqa: E402
    CLASS_ATTRIBUTE_PATTERN,
    CSS_CLASS_SELECTOR_PATTERN,
    MAX_ORPHAN_CSS_CLASS_ISSUES,
    MAX_SIBLING_MODULES_SCANNED,
    ORPHAN_CSS_CLASS_MESSAGE_SUFFIX,
    PYTHON_MODULE_GLOB,
    STYLE_BLOCK_PATTERN,
)


def _string_literals_with_lines(tree: ast.Module) -> list[tuple[str, int]]:
    """Return every string-constant value in the tree paired with its line number.

    Args:
        tree: The parsed module to walk.

    Returns:
        A list of ``(string_value, line_number)`` pairs, one per string constant.
    """
    literals: list[tuple[str, int]] = []
    for each_node in ast.walk(tree):
        if isinstance(each_node, ast.Constant) and isinstance(each_node.value, str):
            literals.append((each_node.value, each_node.lineno))
    return literals


def _class_names_in_attribute(attribute_text: str) -> list[str]:
    """Return the individual class names in a single ``class="..."`` attribute.

    Args:
        attribute_text: The whitespace-separated class list from one attribute.

    Returns:
        Each non-empty class token, in order.
    """
    return [each_token for each_token in attribute_text.split() if each_token]


def _class_references_with_lines(
    all_string_literals: list[tuple[str, int]],
) -> list[tuple[str, int]]:
    """Return every class name referenced in a ``class="..."`` attribute.

    Args:
        all_string_literals: The ``(literal_text, line_number)`` constants to scan.

    Returns:
        A list of ``(class_name, line_number)`` pairs, one per referenced class.
    """
    references: list[tuple[str, int]] = []
    for each_text, each_line in all_string_literals:
        for each_match in CLASS_ATTRIBUTE_PATTERN.finditer(each_text):
            for each_class_name in _class_names_in_attribute(each_match.group(1)):
                references.append((each_class_name, each_line))
    return references


def _defined_class_selectors(all_string_literals: list[tuple[str, int]]) -> set[str]:
    """Return every CSS class name defined by a selector inside a ``<style>`` block.

    Args:
        all_string_literals: The ``(literal_text, line_number)`` constants to scan.

    Returns:
        The set of class names that carry a matching ``.<class>`` selector.
    """
    defined: set[str] = set()
    for each_text, _ in all_string_literals:
        for each_style_match in STYLE_BLOCK_PATTERN.finditer(each_text):
            for each_selector in CSS_CLASS_SELECTOR_PATTERN.finditer(
                each_style_match.group(1)
            ):
                defined.add(each_selector.group(1))
    return defined


def _sibling_module_paths(file_path: str) -> list[Path]:
    """Return the importable sibling Python modules near *file_path*.

    Scans the file's own directory and its immediate child directories, since a
    markup module commonly imports its ``<style>`` constant from a companion
    package directory beside it. The scan is bounded so a large tree never
    stalls a write.

    Args:
        file_path: The absolute path of the file under validation.

    Returns:
        The sibling ``.py`` paths to read for cross-module selector resolution,
        excluding the file itself, capped at the scan budget.
    """
    target = Path(file_path)
    base_directory = target.parent
    if not base_directory.is_dir():
        return []
    siblings: list[Path] = []
    for each_path in sorted(base_directory.rglob(PYTHON_MODULE_GLOB)):
        if each_path.resolve() == target.resolve():
            continue
        siblings.append(each_path)
        if len(siblings) >= MAX_SIBLING_MODULES_SCANNED:
            break
    return siblings


def _selectors_from_sibling_modules(file_path: str) -> set[str]:
    """Return CSS class selectors defined in ``<style>`` blocks of sibling modules.

    Args:
        file_path: The absolute path of the file under validation.

    Returns:
        The union of class names whose selectors appear in any readable sibling
        module's string literals.
    """
    selectors: set[str] = set()
    for each_sibling in _sibling_module_paths(file_path):
        try:
            sibling_source = each_sibling.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        try:
            sibling_tree = ast.parse(sibling_source)
        except SyntaxError:
            continue
        selectors |= _defined_class_selectors(_string_literals_with_lines(sibling_tree))
    return selectors


def check_orphan_css_classes(content: str, file_path: str) -> list[str]:
    """Flag ``class="..."`` markup whose class has no matching CSS selector.

    A module that emits HTML names each class it references with a matching
    ``.<class>`` selector, either in a ``<style>`` block in the same file or in
    a companion module beside it. A referenced class with no selector anywhere
    is a dead attribute (or a missing rule), so this flags it. The check only
    fires for a file that itself emits markup, and only after a ``<style>``
    block exists in the file or a sibling — a file with markup but no style
    source nearby is left alone, since its stylesheet lives outside the scan.
    Test files are exempt, since a fixture may carry intentional orphan markup.

    Args:
        content: The new or whole-file content being written.
        file_path: The destination path of the write or edit.

    Returns:
        One issue per orphan class reference, capped at the issue budget.
    """
    if is_test_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    all_string_literals = _string_literals_with_lines(tree)
    class_references = _class_references_with_lines(all_string_literals)
    if not class_references:
        return []
    defined_selectors = _defined_class_selectors(all_string_literals)
    defined_selectors |= _selectors_from_sibling_modules(file_path)
    if not defined_selectors:
        return []
    issues: list[str] = []
    reported_classes: set[str] = set()
    for each_class_name, each_line in class_references:
        if each_class_name in defined_selectors:
            continue
        if each_class_name in reported_classes:
            continue
        reported_classes.add(each_class_name)
        issues.append(
            f"Line {each_line}: CSS class {each_class_name!r} used in markup"
            f" has no matching '.{each_class_name}' selector - "
            f"{ORPHAN_CSS_CLASS_MESSAGE_SUFFIX}"
        )
        if len(issues) >= MAX_ORPHAN_CSS_CLASS_ISSUES:
            break
    return issues
